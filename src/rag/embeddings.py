"""
Embedding generation for SEC documents using sentence-transformers.
"""
import numpy as np
from typing import List, Dict, Optional, Union, Tuple
from sentence_transformers import SentenceTransformer
import torch
import logging
from tqdm import tqdm
import gc

logger = logging.getLogger(__name__)


class EmbeddingModel:
    """Manage embedding generation for documents."""
    
    # Model recommendations based on our analysis
    MODEL_OPTIONS = {
        'general-fast': 'sentence-transformers/all-MiniLM-L6-v2',  # 384 dims, very fast
        'general-best': 'sentence-transformers/all-mpnet-base-v2',  # 768 dims, high quality
        'biomedical': 'pritamdeka/S-PubMedBert-MS-MARCO',  # 768 dims, medical domain
        'retrieval-optimized': 'BAAI/bge-small-en-v1.5',  # 384 dims, optimized for search
    }
    
    def __init__(self, model_name: str = 'general-fast', device: Optional[str] = None):
        """
        Initialize embedding model.
        
        Args:
            model_name: Either a key from MODEL_OPTIONS or a full model name
            device: Device to use ('cuda', 'cpu', or None for auto-detect)
        """
        # Resolve model name
        if model_name in self.MODEL_OPTIONS:
            self.model_name = self.MODEL_OPTIONS[model_name]
            logger.info(f"Using {model_name} model: {self.model_name}")
        else:
            self.model_name = model_name
            logger.info(f"Using custom model: {self.model_name}")
        
        # Set device
        if device is None:
            self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        else:
            self.device = device
        
        logger.info(f"Using device: {self.device}")
        
        # Load model
        self.model = SentenceTransformer(self.model_name, device=self.device)
        self.embedding_dim = self.model.get_sentence_embedding_dimension()
        
        # Set optimal batch size based on device
        if self.device == 'cuda':
            self.batch_size = 32
        else:
            self.batch_size = 8
    
    def encode_texts(self, texts: List[str], show_progress: bool = True,
                     normalize: bool = True) -> np.ndarray:
        """
        Generate embeddings for a list of texts.
        
        Args:
            texts: List of text strings to embed
            show_progress: Show progress bar
            normalize: Normalize embeddings to unit length
            
        Returns:
            Numpy array of embeddings (n_texts x embedding_dim)
        """
        if not texts:
            return np.array([])
        
        # Configure encoding parameters
        encode_kwargs = {
            'batch_size': self.batch_size,
            'show_progress_bar': show_progress,
            'normalize_embeddings': normalize,
            'convert_to_numpy': True
        }
        
        try:
            embeddings = self.model.encode(texts, **encode_kwargs)
            return embeddings
            
        except Exception as e:
            logger.error(f"Error encoding texts: {e}")
            raise
    
    def encode_chunks(self, chunks: List[Dict], text_key: str = 'text') -> np.ndarray:
        """
        Generate embeddings for document chunks.
        
        Args:
            chunks: List of chunk dictionaries
            text_key: Key in dictionary containing text
            
        Returns:
            Numpy array of embeddings
        """
        texts = [chunk[text_key] for chunk in chunks]
        return self.encode_texts(texts)
    
    def encode_query(self, query: str, prefix: Optional[str] = None) -> np.ndarray:
        """
        Encode a search query.
        
        Args:
            query: Search query text
            prefix: Optional prefix for the query (some models require this)
            
        Returns:
            Query embedding
        """
        # Some models like E5 require specific prefixes
        if prefix:
            query = prefix + query
        elif 'e5' in self.model_name.lower():
            query = "query: " + query
        
        embedding = self.model.encode(
            [query],
            normalize_embeddings=True,
            convert_to_numpy=True
        )
        
        return embedding[0]
    
    def compute_similarity(self, query_embedding: np.ndarray, 
                          document_embeddings: np.ndarray) -> np.ndarray:
        """
        Compute similarity scores between query and documents.
        
        Args:
            query_embedding: Query embedding vector
            document_embeddings: Matrix of document embeddings
            
        Returns:
            Array of similarity scores
        """
        # Ensure proper shapes
        query_embedding = query_embedding.reshape(1, -1)
        
        # Compute cosine similarity (assuming normalized embeddings)
        similarities = np.dot(document_embeddings, query_embedding.T).flatten()
        
        return similarities
    
    def get_model_info(self) -> Dict:
        """Get information about the current model."""
        return {
            'model_name': self.model_name,
            'embedding_dim': self.embedding_dim,
            'device': self.device,
            'max_seq_length': self.model.max_seq_length,
            'batch_size': self.batch_size
        }


class HybridEmbedder:
    """
    Hybrid embedder that can use different models for different content types.
    Useful for handling both financial and biomedical content.
    """
    
    def __init__(self, device: Optional[str] = None):
        """Initialize hybrid embedder with multiple models."""
        self.device = device or ('cuda' if torch.cuda.is_available() else 'cpu')
        
        # Initialize models
        self.general_model = EmbeddingModel('general-fast', device=self.device)
        self.bio_model = None  # Lazy load when needed
        
        # Keywords to identify biomedical content
        self.bio_keywords = [
            'clinical trial', 'phase', 'efficacy', 'adverse event', 
            'patient', 'treatment', 'therapy', 'drug', 'indication',
            'fda', 'endpoint', 'placebo', 'randomized', 'dose'
        ]
    
    def _is_biomedical_content(self, text: str) -> bool:
        """Determine if text is primarily biomedical."""
        text_lower = text.lower()
        bio_count = sum(1 for keyword in self.bio_keywords if keyword in text_lower)
        return bio_count >= 3
    
    def encode_texts(self, texts: List[str], auto_detect: bool = True) -> np.ndarray:
        """
        Encode texts using appropriate model.
        
        Args:
            texts: List of texts to encode
            auto_detect: Automatically detect content type
            
        Returns:
            Embeddings array
        """
        if not auto_detect:
            return self.general_model.encode_texts(texts)
        
        # Separate texts by content type
        bio_indices = []
        general_indices = []
        
        for i, text in enumerate(texts):
            if self._is_biomedical_content(text):
                bio_indices.append(i)
            else:
                general_indices.append(i)
        
        # If no biomedical content, use general model only
        if not bio_indices:
            return self.general_model.encode_texts(texts)
        
        # Initialize bio model if needed
        if self.bio_model is None:
            logger.info("Loading biomedical model for hybrid encoding...")
            self.bio_model = EmbeddingModel('biomedical', device=self.device)
        
        # Ensure both models have same dimensions
        if self.general_model.embedding_dim != self.bio_model.embedding_dim:
            logger.warning("Models have different dimensions, using general model only")
            return self.general_model.encode_texts(texts)
        
        # Encode with appropriate models
        embeddings = np.zeros((len(texts), self.general_model.embedding_dim))
        
        if general_indices:
            general_texts = [texts[i] for i in general_indices]
            general_embeddings = self.general_model.encode_texts(general_texts, show_progress=False)
            for idx, i in enumerate(general_indices):
                embeddings[i] = general_embeddings[idx]
        
        if bio_indices:
            bio_texts = [texts[i] for i in bio_indices]
            bio_embeddings = self.bio_model.encode_texts(bio_texts, show_progress=False)
            for idx, i in enumerate(bio_indices):
                embeddings[i] = bio_embeddings[idx]
        
        logger.info(f"Hybrid encoding: {len(bio_indices)} biomedical, {len(general_indices)} general")
        
        return embeddings


def batch_encode_filings(chunks: List[Dict], model: Union[EmbeddingModel, HybridEmbedder],
                        batch_size: int = 1000) -> List[Tuple[np.ndarray, List[Dict]]]:
    """
    Encode large numbers of chunks in batches to manage memory.
    
    Args:
        chunks: All chunks to encode
        model: Embedding model to use
        batch_size: Number of chunks per batch
        
    Yields:
        Tuples of (embeddings, chunk_batch)
    """
    total_batches = (len(chunks) + batch_size - 1) // batch_size
    
    for i in tqdm(range(0, len(chunks), batch_size), desc="Encoding batches", total=total_batches):
        batch = chunks[i:i + batch_size]
        texts = [chunk['text'] for chunk in batch]
        
        # Encode batch
        embeddings = model.encode_texts(texts, show_progress=False)
        
        yield embeddings, batch
        
        # Force garbage collection to free memory
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()