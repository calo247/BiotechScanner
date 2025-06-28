"""
Main RAG search interface for SEC documents.
Combines document processing, embeddings, and FAISS search.
"""
from typing import List, Dict, Optional, Union
from datetime import datetime
import logging
from pathlib import Path
import numpy as np

from .document_processor import SECDocumentProcessor, create_filing_chunks
from .embeddings import EmbeddingModel, HybridEmbedder
from .faiss_index import FAISSIndex
from ..database.database import get_db_session
from ..database.models import SECFiling, Company

logger = logging.getLogger(__name__)


class RAGSearchEngine:
    """Main interface for RAG-based SEC document search."""
    
    def __init__(self, model_type: str = 'general-fast', 
                 use_hybrid: bool = False,
                 index_path: str = "data/faiss",
                 use_pq: bool = True,
                 pq_bits: int = 8):
        """
        Initialize RAG search engine.
        
        Args:
            model_type: Type of embedding model to use
            use_hybrid: Use hybrid embedder for mixed content
            index_path: Path to store FAISS index
            use_pq: Whether to use Product Quantization for compression
            pq_bits: Bits per subquantizer (4 or 8, lower = more compression)
        """
        # Initialize components
        if use_hybrid:
            self.embedder = HybridEmbedder()
            self.embedding_dim = 384  # Assuming general-fast for hybrid
        else:
            self.embedder = EmbeddingModel(model_type)
            self.embedding_dim = self.embedder.embedding_dim
        
        self.index = FAISSIndex(self.embedding_dim, index_path, use_pq=use_pq, pq_bits=pq_bits)
        self.processor = SECDocumentProcessor()
        
        # Database session
        self.db_session = get_db_session()
    
    def index_filing(self, filing: SECFiling) -> int:
        """
        Index a single SEC filing.
        
        Args:
            filing: SECFiling database object
            
        Returns:
            Number of chunks indexed
        """
        if not filing.file_path or not Path(filing.file_path).exists():
            logger.warning(f"Filing {filing.accession_number} has no file or file not found")
            return 0
        
        try:
            # Create metadata for chunks
            metadata = {
                'filing_id': filing.id,
                'company_id': filing.company_id,
                'filing_type': filing.filing_type,
                'filing_date': filing.filing_date.isoformat() if filing.filing_date else None,
                'accession_number': filing.accession_number,
                'file_path': filing.file_path  # Add file path for on-demand loading
            }
            
            # Process filing into chunks
            chunks = create_filing_chunks(filing.file_path, metadata)
            
            if not chunks:
                logger.warning(f"No chunks created for filing {filing.accession_number}")
                return 0
            
            # Generate embeddings
            embeddings = self.embedder.encode_chunks(chunks)
            
            # Add to index
            chunk_ids = self.index.add_embeddings(embeddings, chunks)
            
            # Save index periodically
            if self.index.index.ntotal % 10000 == 0:
                self.index.save_index()
            
            logger.info(f"Indexed {len(chunks)} chunks from filing {filing.accession_number}")
            return len(chunks)
            
        except Exception as e:
            logger.error(f"Error indexing filing {filing.accession_number}: {e}")
            return 0
    
    def index_company_filings(self, company_id: int, 
                            filing_types: Optional[List[str]] = None,
                            limit: Optional[int] = None) -> Dict:
        """
        Index all filings for a company.
        
        Args:
            company_id: Company ID to index
            filing_types: Optional list of filing types to index
            limit: Maximum number of filings to index
            
        Returns:
            Statistics about indexing
        """
        # Get company
        company = self.db_session.query(Company).filter_by(id=company_id).first()
        if not company:
            raise ValueError(f"Company {company_id} not found")
        
        # Query filings
        query = self.db_session.query(SECFiling).filter_by(company_id=company_id)
        
        if filing_types:
            query = query.filter(SECFiling.filing_type.in_(filing_types))
        
        query = query.order_by(SECFiling.filing_date.desc())
        
        if limit:
            query = query.limit(limit)
        
        filings = query.all()
        
        logger.info(f"Indexing {len(filings)} filings for {company.ticker}")
        
        # Index each filing
        stats = {
            'company': company.ticker,
            'total_filings': len(filings),
            'indexed_filings': 0,
            'total_chunks': 0,
            'failed_filings': []
        }
        
        for filing in filings:
            chunks_indexed = self.index_filing(filing)
            
            if chunks_indexed > 0:
                stats['indexed_filings'] += 1
                stats['total_chunks'] += chunks_indexed
            else:
                stats['failed_filings'].append(filing.accession_number)
        
        # Save index after batch
        self.index.save_index()
        
        return stats
    
    def search(self, query: str, 
               company_id: Optional[int] = None,
               filing_types: Optional[List[str]] = None,
               k: int = 10,
               rerank: bool = True) -> List[Dict]:
        """
        Search for relevant document chunks.
        
        Args:
            query: Search query
            company_id: Optional company filter
            filing_types: Optional filing type filter
            k: Number of results to return
            rerank: Whether to rerank results
            
        Returns:
            List of search results with metadata
        """
        # Generate query embedding
        if isinstance(self.embedder, HybridEmbedder):
            # For hybrid, detect if query is biomedical
            is_bio = self.embedder._is_biomedical_content(query)
            if is_bio and self.embedder.bio_model is None:
                self.embedder.bio_model = EmbeddingModel('biomedical')
            
            model_to_use = self.embedder.bio_model if is_bio else self.embedder.general_model
            query_embedding = model_to_use.encode_query(query)
        else:
            query_embedding = self.embedder.encode_query(query)
        
        # Search in FAISS
        results = self.index.search(
            query_embedding,
            k=k * 3 if rerank else k,  # Get more results if reranking
            filter_company_id=company_id
        )
        
        # Filter by filing type if specified
        if filing_types:
            results = [r for r in results if r.get('filing_type') in filing_types]
        
        # Enhance results with additional metadata and load text on-demand
        enhanced_results = []
        for result in results:
            # Load the chunk text on-demand
            result['text'] = self.load_chunk_text(result)
            
            # Get filing info
            filing = self.db_session.query(SECFiling).filter_by(
                id=result['filing_id']
            ).first()
            
            if filing:
                result['filing_url'] = filing.filing_url
                result['company_ticker'] = filing.company.ticker
                result['company_name'] = filing.company.name
            
            enhanced_results.append(result)
        
        # Rerank if requested
        if rerank and len(enhanced_results) > k:
            enhanced_results = self._rerank_results(query, enhanced_results, k)
        
        return enhanced_results[:k]
    
    def _rerank_results(self, query: str, results: List[Dict], k: int) -> List[Dict]:
        """
        Rerank results using cross-encoder or more sophisticated scoring.
        For now, we'll use a simple keyword-based reranking.
        """
        query_words = set(query.lower().split())
        
        for result in results:
            text_lower = result['text'].lower()
            
            # Count query word occurrences
            word_score = sum(1 for word in query_words if word in text_lower)
            
            # Boost for exact phrase match
            phrase_score = 10 if query.lower() in text_lower else 0
            
            # Combine with original score (lower is better for L2 distance)
            # Convert to similarity score (higher is better)
            similarity_score = 1 / (1 + result['score'])
            
            result['rerank_score'] = (
                similarity_score * 0.5 +  # 50% embedding similarity
                (word_score / len(query_words)) * 0.3 +  # 30% word overlap
                phrase_score * 0.2  # 20% exact phrase
            )
        
        # Sort by rerank score (descending)
        results.sort(key=lambda x: x['rerank_score'], reverse=True)
        
        return results
    
    def load_chunk_text(self, result: Dict) -> str:
        """
        Load text for a chunk from the filing on-demand.
        
        Args:
            result: Search result dictionary with file_path and char positions
            
        Returns:
            Text content of the chunk
        """
        file_path = result.get('file_path')
        char_start = result.get('char_start', 0)
        char_end = result.get('char_end')
        
        if not file_path:
            return "[Text not available - missing file path]"
        
        try:
            # Load the filing
            full_text = self.processor.load_filing(file_path)
            
            # Extract the chunk text
            if char_end:
                chunk_text = full_text[char_start:char_end]
            else:
                # Fallback - take a reasonable chunk from start position
                chunk_text = full_text[char_start:char_start + 2000]
            
            # Clean the text
            chunk_text = self.processor.clean_text(chunk_text)
            
            return chunk_text.strip()
            
        except Exception as e:
            logger.error(f"Error loading chunk text from {file_path}: {e}")
            return f"[Error loading text: {str(e)}]"
    
    def get_context_window(self, result: Dict, window_size: int = 1000) -> str:
        """
        Get expanded context around a search result.
        
        Args:
            result: Search result dictionary
            window_size: Characters to include before/after
            
        Returns:
            Expanded text context
        """
        filing = self.db_session.query(SECFiling).filter_by(
            id=result['filing_id']
        ).first()
        
        if not filing or not filing.file_path:
            return result['text']
        
        try:
            # Load full filing
            full_text = self.processor.load_filing(filing.file_path)
            
            # Get character positions
            start = max(0, result.get('char_start', 0) - window_size)
            end = min(len(full_text), result.get('char_end', len(full_text)) + window_size)
            
            # Extract context
            context = full_text[start:end]
            
            # Clean up
            context = self.processor.clean_text(context)
            
            # Add markers
            if start > 0:
                context = "..." + context
            if end < len(full_text):
                context = context + "..."
            
            return context
            
        except Exception as e:
            logger.error(f"Error getting context: {e}")
            return result['text']
    
    def find_similar_chunks(self, chunk_id: int, k: int = 5) -> List[Dict]:
        """Find chunks similar to a given chunk."""
        # Get chunk metadata
        metadata = self.index.metadata.get(chunk_id)
        if not metadata:
            return []
        
        # Get chunk embedding from index
        idx = metadata['idx']
        chunk_embedding = self.index.index.reconstruct(int(idx))
        
        # Search for similar
        results = self.index.search(chunk_embedding, k=k+1)
        
        # Remove self from results
        results = [r for r in results if r['chunk_id'] != chunk_id]
        
        return results[:k]
    
    def get_stats(self) -> Dict:
        """Get search engine statistics."""
        stats = self.index.get_stats()
        
        # Add model info
        if isinstance(self.embedder, HybridEmbedder):
            stats['embedding_model'] = 'hybrid'
        else:
            stats['embedding_model'] = self.embedder.get_model_info()
        
        return stats
    
    def search_by_ticker(self, query: str, ticker: str, k: int = 10,
                        filing_types: Optional[List[str]] = None,
                        rerank: bool = False) -> List[Dict]:
        """
        Search within a specific company's filings using ticker symbol.
        
        Args:
            query: Search query text
            ticker: Company ticker symbol (e.g., 'MRNA')
            k: Number of results to return
            filing_types: Optional list of filing types to filter
            rerank: Whether to rerank results
            
        Returns:
            List of search results
            
        Example:
            results = engine.search_by_ticker("clinical trial", "MRNA", k=5)
        """
        # Look up company by ticker
        company = self.db_session.query(Company).filter_by(
            ticker=ticker.upper()
        ).first()
        
        if not company:
            logger.warning(f"Company '{ticker}' not found in database")
            return []
        
        # Use existing search method with company_id filter
        return self.search(
            query=query,
            company_id=company.id,
            k=k,
            filing_types=filing_types,
            rerank=rerank
        )
    
    def close(self):
        """Clean up resources."""
        self.index.save_index()
        self.db_session.close()