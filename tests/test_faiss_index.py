#!/usr/bin/env python3
"""
Test the new FAISS index with PQ compression.
"""
import sys
from pathlib import Path
import logging
import pickle
import numpy as np

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from src.rag.rag_search import RAGSearchEngine
from src.rag.faiss_index import FAISSIndex

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_index_stats():
    """Test loading the index and checking stats."""
    logger.info("Testing FAISS index statistics...")
    
    try:
        # Load the index
        engine = RAGSearchEngine()
        stats = engine.get_stats()
        
        logger.info("\nIndex Statistics:")
        logger.info(f"  Total vectors: {stats['total_vectors']:,}")
        logger.info(f"  Total chunks: {stats['total_chunks']:,}")
        logger.info(f"  Embedding dimension: {stats['embedding_dim']}")
        logger.info(f"  Index type: {stats['index_type']}")
        logger.info(f"  Is trained: {stats['is_trained']}")
        logger.info(f"  Companies indexed: {stats['companies_indexed']}")
        logger.info(f"  Embedding model: {stats['embedding_model']}")
        
        # Check filing types
        if 'filing_types' in stats:
            logger.info("\nFiling type distribution:")
            for ftype, count in stats['filing_types'].items():
                logger.info(f"    {ftype}: {count:,}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error loading index: {e}")
        return False


def test_memory_usage():
    """Check memory usage of the index."""
    logger.info("\nChecking memory usage...")
    
    try:
        import psutil
        import os
        
        # Get process memory before loading
        process = psutil.Process(os.getpid())
        mem_before = process.memory_info().rss / 1024 / 1024  # MB
        logger.info(f"Memory before loading: {mem_before:.2f} MB")
        
        # Load index
        engine = RAGSearchEngine()
        
        # Get memory after loading
        mem_after = process.memory_info().rss / 1024 / 1024  # MB
        logger.info(f"Memory after loading: {mem_after:.2f} MB")
        logger.info(f"Index memory usage: {mem_after - mem_before:.2f} MB")
        
        # Check metadata file size
        metadata_file = Path("data/faiss/metadata.pkl")
        if metadata_file.exists():
            metadata_size = metadata_file.stat().st_size / 1024 / 1024
            logger.info(f"Metadata file size: {metadata_size:.2f} MB")
            
            # Load and check metadata
            with open(metadata_file, 'rb') as f:
                metadata = pickle.load(f)
                
            # Check if any entries have 'text' field
            has_text = any('text' in v for v in metadata.values())
            logger.info(f"Metadata contains text: {has_text}")
            
            # Check if entries have file_path
            has_file_path = all('file_path' in v for v in list(metadata.values())[:10])
            logger.info(f"Metadata contains file_path: {has_file_path}")
        
        return True
        
    except ImportError:
        logger.warning("psutil not installed, skipping memory test")
        return True
    except Exception as e:
        logger.error(f"Error checking memory: {e}")
        return False


def test_search_functionality():
    """Test search functionality."""
    logger.info("\nTesting search functionality...")
    
    try:
        engine = RAGSearchEngine()
        
        # Test queries
        test_queries = [
            "Phase 3 clinical trial results",
            "FDA approval PDUFA date",
            "cash burn rate runway",
            "adverse events safety profile"
        ]
        
        for query in test_queries:
            logger.info(f"\nSearching for: '{query}'")
            
            try:
                results = engine.search(query, k=3)
                
                if not results:
                    logger.warning("  No results found")
                    continue
                
                for i, result in enumerate(results):
                    logger.info(f"\n  Result {i+1}:")
                    logger.info(f"    Score: {result.get('score', 'N/A'):.4f}")
                    logger.info(f"    Company: {result.get('company_ticker', 'N/A')}")
                    logger.info(f"    Filing: {result.get('filing_type', 'N/A')} - {result.get('filing_date', 'N/A')}")
                    logger.info(f"    Section: {result.get('section', 'N/A')}")
                    
                    # Check if text was loaded
                    text = result.get('text', '')
                    if text:
                        logger.info(f"    Text preview: {text[:100]}...")
                    else:
                        logger.warning("    No text loaded!")
                    
                    # Check file path
                    if 'file_path' in result:
                        logger.info(f"    File path: {result['file_path']}")
                    
            except Exception as e:
                logger.error(f"  Error searching: {e}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error in search test: {e}")
        return False


def test_index_structure():
    """Test the internal structure of the index."""
    logger.info("\nTesting index internal structure...")
    
    try:
        # Load index directly
        index = FAISSIndex()
        
        # Check index type
        index_type = type(index.index).__name__
        logger.info(f"Index type: {index_type}")
        
        # For IVFPQ, check parameters
        if 'IVFPQ' in index_type:
            logger.info("PQ compression is active!")
            if hasattr(index.index, 'pq'):
                logger.info(f"  PQ m (subquantizers): {index.index.pq.M}")
                logger.info(f"  PQ nbits: {index.index.pq.nbits}")
                logger.info(f"  PQ total codes: {index.index.pq.ksub}")
        
        # Check training status
        if hasattr(index.index, 'is_trained'):
            logger.info(f"Index is trained: {index.index.is_trained}")
        
        # Check number of vectors
        logger.info(f"Total vectors in index: {index.index.ntotal:,}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error checking index structure: {e}")
        return False


def main():
    """Run all tests."""
    logger.info("="*60)
    logger.info("Testing new FAISS index with PQ compression")
    logger.info("="*60)
    
    tests = [
        ("Index Stats", test_index_stats),
        ("Memory Usage", test_memory_usage),
        ("Index Structure", test_index_structure),
        ("Search Functionality", test_search_functionality)
    ]
    
    results = []
    for test_name, test_func in tests:
        logger.info(f"\n{'='*40}")
        logger.info(f"Running: {test_name}")
        logger.info(f"{'='*40}")
        
        success = test_func()
        results.append((test_name, success))
    
    # Summary
    logger.info("\n" + "="*60)
    logger.info("TEST SUMMARY")
    logger.info("="*60)
    
    for test_name, success in results:
        status = "PASSED" if success else "FAILED"
        logger.info(f"{test_name}: {status}")
    
    all_passed = all(success for _, success in results)
    
    if all_passed:
        logger.info("\nAll tests passed! ✓")
    else:
        logger.info("\nSome tests failed! ✗")
    
    return 0 if all_passed else 1


if __name__ == '__main__':
    sys.exit(main())