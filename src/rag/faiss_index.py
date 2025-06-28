"""
FAISS index management for SEC document embeddings.
"""
import faiss
import numpy as np
import pickle
import json
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Any
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class FAISSIndex:
    """Manage FAISS index for document embeddings."""
    
    def __init__(self, embedding_dim: int = 384, index_path: str = "data/faiss", 
                 use_pq: bool = True, pq_bits: int = 8):
        """
        Initialize FAISS index.
        
        Args:
            embedding_dim: Dimension of embeddings
            index_path: Directory to store index files
            use_pq: Whether to use Product Quantization for compression
            pq_bits: Bits per subquantizer (4 or 8, lower = more compression)
        """
        self.embedding_dim = embedding_dim
        self.index_path = Path(index_path)
        self.index_path.mkdir(parents=True, exist_ok=True)
        self.use_pq = use_pq
        self.pq_bits = pq_bits
        
        # File paths
        self.index_file = self.index_path / "sec_filings.index"
        self.metadata_file = self.index_path / "metadata.pkl"
        self.id_map_file = self.index_path / "id_map.json"
        
        # Initialize or load index
        self.index = None
        self.metadata = {}
        self.id_to_idx = {}  # Map chunk IDs to FAISS indices
        self.next_id = 0
        
        self._load_or_create_index()
    
    def _load_or_create_index(self):
        """Load existing index or create new one."""
        if self.index_file.exists() and self.metadata_file.exists():
            self._load_index()
        else:
            self._create_index()
    
    def _create_index(self):
        """Create new FAISS index with Product Quantization for memory efficiency."""
        # Using IVF index for better performance at scale
        # nlist = number of clusters (rule of thumb: sqrt(expected_vectors))
        nlist = 1000  # Good for up to 1M vectors
        
        # Create quantizer
        quantizer = faiss.IndexFlatL2(self.embedding_dim)
        
        if self.use_pq:
            # Use IndexIVFPQ for memory efficiency
            # For 384-dim vectors (all-MiniLM-L6-v2), use m=48 (384/48=8 dimensions per subquantizer)
            # For 768-dim vectors (S-PubMedBert), use m=96 (768/96=8 dimensions per subquantizer)
            if self.embedding_dim == 384:
                m = 48  # number of subquantizers
            elif self.embedding_dim == 768:
                m = 96
            else:
                m = min(self.embedding_dim // 8, 64)  # Ensure divisibility
            
            bits = self.pq_bits  # bits per subquantizer
            
            # Create PQ-compressed index
            self.index = faiss.IndexIVFPQ(quantizer, self.embedding_dim, nlist, m, bits)
            
            logger.info(f"Created PQ-compressed FAISS index: dim={self.embedding_dim}, "
                       f"nlist={nlist}, m={m}, bits={bits}")
        else:
            # Create standard IVF index without compression
            self.index = faiss.IndexIVFFlat(quantizer, self.embedding_dim, nlist)
            logger.info(f"Created standard FAISS index: dim={self.embedding_dim}, nlist={nlist}")
    
    def _load_index(self):
        """Load existing index from disk."""
        try:
            self.index = faiss.read_index(str(self.index_file))
            
            with open(self.metadata_file, 'rb') as f:
                self.metadata = pickle.load(f)
            
            if self.id_map_file.exists():
                with open(self.id_map_file, 'r') as f:
                    data = json.load(f)
                    self.id_to_idx = {int(k): v for k, v in data['id_to_idx'].items()}
                    self.next_id = data['next_id']
            
            logger.info(f"Loaded FAISS index with {self.index.ntotal} vectors")
            
        except Exception as e:
            logger.error(f"Error loading index: {e}")
            self._create_index()
    
    def save_index(self):
        """Save index and metadata to disk."""
        try:
            # Check if we have pending embeddings that couldn't be added
            if hasattr(self, '_pending_embeddings') and self._pending_embeddings:
                total_pending = sum(len(e) for e in self._pending_embeddings)
                logger.warning(f"Cannot save index - {total_pending} vectors pending training. "
                             f"Need more data before index can be trained and saved.")
                return
            
            # Train index if needed (for IVF indices)
            if hasattr(self.index, 'is_trained') and not self.index.is_trained:
                logger.warning("Index not trained, skipping save")
                return
            
            # Save FAISS index
            faiss.write_index(self.index, str(self.index_file))
            
            # Save metadata
            with open(self.metadata_file, 'wb') as f:
                pickle.dump(self.metadata, f)
            
            # Save ID mapping
            with open(self.id_map_file, 'w') as f:
                json.dump({
                    'id_to_idx': self.id_to_idx,
                    'next_id': self.next_id
                }, f)
            
            logger.info(f"Saved index with {self.index.ntotal} vectors")
            
        except Exception as e:
            logger.error(f"Error saving index: {e}")
    
    def add_embeddings(self, embeddings: np.ndarray, chunks: List[Dict]) -> List[int]:
        """
        Add embeddings to index with metadata.
        
        Args:
            embeddings: Numpy array of embeddings (n_chunks x embedding_dim)
            chunks: List of chunk dictionaries with metadata
            
        Returns:
            List of assigned chunk IDs
        """
        if len(embeddings) != len(chunks):
            raise ValueError("Number of embeddings must match number of chunks")
        
        # Check if we need to accumulate more data before training
        if hasattr(self.index, 'is_trained') and not self.index.is_trained:
            # Initialize pending storage if needed
            if not hasattr(self, '_pending_embeddings'):
                self._pending_embeddings = []
                self._pending_chunks = []
            
            # Add to pending
            self._pending_embeddings.append(embeddings)
            self._pending_chunks.extend(chunks)
            
            # Calculate minimum training points needed
            # For IVF: 40 * nlist, for PQ: 256 * number of subquantizers
            if self.use_pq:
                m = 48 if self.embedding_dim == 384 else 96
                min_train_points = max(40 * 1000, 256 * m)  # ~40k minimum
            else:
                min_train_points = 40 * 1000  # 40k for IVF
            
            # Check if we have enough data
            total_pending = sum(len(e) for e in self._pending_embeddings)
            
            if total_pending < min_train_points:
                logger.info(f"Accumulating vectors for training: {total_pending}/{min_train_points}")
                # Return empty list for now - we'll assign IDs when we actually add to index
                return []
            
            # We have enough data - train and add all pending
            logger.info(f"Training FAISS index with {total_pending} vectors...")
            
            # Combine all pending embeddings
            all_embeddings = np.vstack(self._pending_embeddings)
            all_chunks = self._pending_chunks
            
            # Train the index
            self.index.train(all_embeddings.astype('float32'))
            logger.info("Index training completed")
            
            # Clear pending
            self._pending_embeddings = None
            self._pending_chunks = None
            
            # Process all accumulated chunks
            chunk_ids = []
            current_idx = 0
            
            for chunk in all_chunks:
                chunk_id = self.next_id
                self.next_id += 1
                
                # Store metadata without text
                self.metadata[chunk_id] = {
                    'idx': current_idx,
                    'file_path': chunk.get('file_path'),
                    'section': chunk.get('section', 'UNKNOWN'),
                    'filing_id': chunk.get('filing_id'),
                    'company_id': chunk.get('company_id'),
                    'filing_type': chunk.get('filing_type'),
                    'filing_date': chunk.get('filing_date'),
                    'char_start': chunk.get('char_start'),
                    'char_end': chunk.get('char_end'),
                    'indexed_at': datetime.utcnow().isoformat()
                }
                
                self.id_to_idx[chunk_id] = current_idx
                chunk_ids.append(chunk_id)
                current_idx += 1
            
            # Add all embeddings to index
            self.index.add(all_embeddings.astype('float32'))
            logger.info(f"Added {len(all_embeddings)} embeddings to trained index")
            
            return chunk_ids
        
        # Assign IDs and store metadata
        chunk_ids = []
        current_idx = self.index.ntotal
        
        for i, chunk in enumerate(chunks):
            chunk_id = self.next_id
            self.next_id += 1
            
            # Store metadata - WITHOUT full text to save memory
            self.metadata[chunk_id] = {
                'idx': current_idx + i,
                # 'text': chunk['text'],  # REMOVED to save memory - load on demand instead
                'file_path': chunk.get('file_path'),  # Path to compressed filing
                'section': chunk.get('section', 'UNKNOWN'),
                'filing_id': chunk.get('filing_id'),
                'company_id': chunk.get('company_id'),
                'filing_type': chunk.get('filing_type'),
                'filing_date': chunk.get('filing_date'),
                'char_start': chunk.get('char_start'),
                'char_end': chunk.get('char_end'),
                'indexed_at': datetime.utcnow().isoformat()
            }
            
            self.id_to_idx[chunk_id] = current_idx + i
            chunk_ids.append(chunk_id)
        
        # Add to FAISS index
        self.index.add(embeddings.astype('float32'))
        
        logger.info(f"Added {len(embeddings)} embeddings to index (total: {self.index.ntotal})")
        
        return chunk_ids
    
    def search(self, query_embedding: np.ndarray, k: int = 10, 
               filter_company_id: Optional[int] = None,
               filter_filing_type: Optional[str] = None,
               filter_date_after: Optional[datetime] = None) -> List[Dict]:
        """
        Search for similar embeddings with optional filtering.
        
        Args:
            query_embedding: Query embedding vector
            k: Number of results to return
            filter_company_id: Only return results from this company
            filter_filing_type: Only return results from this filing type
            filter_date_after: Only return filings after this date
            
        Returns:
            List of results with scores and metadata
        """
        if self.index.ntotal == 0:
            return []
        
        # Search for more results than needed to account for filtering
        search_k = min(k * 10, self.index.ntotal)
        
        # Ensure query embedding is the right shape and type
        query_embedding = query_embedding.reshape(1, -1).astype('float32')
        
        # Search
        distances, indices = self.index.search(query_embedding, search_k)
        
        # Convert to results with metadata
        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx == -1:  # FAISS returns -1 for empty results
                continue
            
            # Find chunk ID from index
            chunk_id = None
            for cid, cidx in self.id_to_idx.items():
                if cidx == idx:
                    chunk_id = cid
                    break
            
            if chunk_id is None:
                continue
            
            metadata = self.metadata.get(chunk_id)
            if not metadata:
                continue
            
            # Apply filters
            if filter_company_id and metadata.get('company_id') != filter_company_id:
                continue
            
            if filter_filing_type and metadata.get('filing_type') != filter_filing_type:
                continue
            
            if filter_date_after:
                filing_date_str = metadata.get('filing_date')
                if filing_date_str:
                    filing_date = datetime.fromisoformat(filing_date_str.replace('Z', '+00:00'))
                    if filing_date < filter_date_after:
                        continue
            
            results.append({
                'chunk_id': chunk_id,
                'score': float(dist),  # Lower is better for L2 distance
                # 'text': metadata['text'],  # Text will be loaded on demand
                'file_path': metadata.get('file_path'),
                'char_start': metadata.get('char_start'),
                'char_end': metadata.get('char_end'),
                'section': metadata['section'],
                'filing_id': metadata['filing_id'],
                'company_id': metadata['company_id'],
                'filing_type': metadata['filing_type'],
                'filing_date': metadata['filing_date']
            })
            
            if len(results) >= k:
                break
        
        return results
    
    def remove_company_filings(self, company_id: int):
        """Remove all filings for a specific company (for re-indexing)."""
        # Note: FAISS doesn't support efficient deletion
        # For production, we'd need to rebuild the index
        chunks_to_remove = []
        
        for chunk_id, metadata in self.metadata.items():
            if metadata.get('company_id') == company_id:
                chunks_to_remove.append(chunk_id)
        
        for chunk_id in chunks_to_remove:
            del self.metadata[chunk_id]
            del self.id_to_idx[chunk_id]
        
        logger.info(f"Marked {len(chunks_to_remove)} chunks for removal from company {company_id}")
        
        # In production, we'd need to rebuild the index periodically
        
    def get_stats(self) -> Dict[str, Any]:
        """Get index statistics."""
        stats = {
            'total_vectors': self.index.ntotal,
            'total_chunks': len(self.metadata),
            'embedding_dim': self.embedding_dim,
            'index_type': type(self.index).__name__,
            'is_trained': getattr(self.index, 'is_trained', True)
        }
        
        # Get company and filing type distribution
        company_counts = {}
        filing_type_counts = {}
        
        for metadata in self.metadata.values():
            company_id = metadata.get('company_id')
            filing_type = metadata.get('filing_type')
            
            if company_id:
                company_counts[company_id] = company_counts.get(company_id, 0) + 1
            
            if filing_type:
                filing_type_counts[filing_type] = filing_type_counts.get(filing_type, 0) + 1
        
        stats['companies_indexed'] = len(company_counts)
        stats['filing_types'] = filing_type_counts
        
        return stats