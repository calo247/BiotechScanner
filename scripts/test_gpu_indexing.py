#!/usr/bin/env python3
"""
Test GPU setup and benchmark embedding generation speed.
"""
import sys
import time
import torch
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from src.rag.embeddings import EmbeddingModel
from src.database.database import get_db_session
from src.database.models import Company


def test_gpu_setup():
    """Test GPU availability and performance."""
    print("=== GPU Setup Test ===")
    
    # Check PyTorch GPU
    print(f"\nPyTorch version: {torch.__version__}")
    print(f"CUDA available: {torch.cuda.is_available()}")
    
    if torch.cuda.is_available():
        print(f"GPU Device: {torch.cuda.get_device_name(0)}")
        print(f"GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
        
        # Test GPU computation
        print("\nTesting GPU computation...")
        x = torch.randn(1000, 1000).cuda()
        start = time.time()
        y = torch.matmul(x, x)
        torch.cuda.synchronize()
        elapsed = time.time() - start
        print(f"Matrix multiplication (1000x1000): {elapsed*1000:.1f}ms")
    else:
        print("WARNING: No GPU detected! Indexing will be slow.")
        return False
    
    return True


def benchmark_embeddings():
    """Benchmark embedding generation speed."""
    print("\n=== Embedding Benchmark ===")
    
    # Test different models
    models_to_test = [
        ('general-fast', 'all-MiniLM-L6-v2'),
        ('general-best', 'all-mpnet-base-v2'),
    ]
    
    # Sample texts
    sample_texts = [
        "The company reported strong Phase 3 clinical trial results for their lead drug candidate.",
        "Cash burn rate increased to $5M per quarter due to expanded clinical trials.",
        "FDA granted Fast Track designation for the treatment of acute kidney injury.",
        "The drug demonstrated a statistically significant improvement in overall survival.",
        "Management expects to complete patient enrollment by Q4 2025.",
    ] * 20  # 100 texts total
    
    for model_key, model_name in models_to_test:
        print(f"\nTesting {model_name}...")
        
        try:
            # Initialize model
            start = time.time()
            model = EmbeddingModel(model_key, device='cuda')
            init_time = time.time() - start
            print(f"  Model initialization: {init_time:.2f}s")
            print(f"  Embedding dimension: {model.embedding_dim}")
            
            # Warm-up
            _ = model.encode_texts(sample_texts[:5], show_progress=False)
            
            # Benchmark
            start = time.time()
            embeddings = model.encode_texts(sample_texts, show_progress=False)
            encode_time = time.time() - start
            
            texts_per_second = len(sample_texts) / encode_time
            print(f"  Encoding speed: {texts_per_second:.1f} texts/second")
            print(f"  Total time for {len(sample_texts)} texts: {encode_time:.2f}s")
            
            # Estimate for full indexing
            estimated_chunks = 4_000_000  # 4M chunks for all companies
            estimated_hours = estimated_chunks / texts_per_second / 3600
            print(f"  Estimated time for 4M chunks: {estimated_hours:.1f} hours")
            
        except Exception as e:
            print(f"  Error testing {model_name}: {e}")


def test_database_connection():
    """Test database connection and get stats."""
    print("\n=== Database Test ===")
    
    try:
        session = get_db_session()
        company_count = session.query(Company).count()
        print(f"Companies in database: {company_count}")
        
        # Get a few examples
        companies = session.query(Company).limit(5).all()
        print("\nSample companies:")
        for company in companies:
            print(f"  - {company.ticker}: {company.name}")
        
        session.close()
        return True
        
    except Exception as e:
        print(f"Database connection error: {e}")
        return False


def main():
    """Run all tests."""
    print("BiotechScanner GPU Indexing Test\n")
    
    # Test GPU
    gpu_ok = test_gpu_setup()
    if not gpu_ok:
        print("\nWARNING: GPU not available. Indexing will be very slow!")
        response = input("Continue anyway? (y/n): ")
        if response.lower() != 'y':
            return
    
    # Test embeddings
    benchmark_embeddings()
    
    # Test database
    db_ok = test_database_connection()
    if not db_ok:
        print("\nERROR: Database not accessible. Check your data files.")
        return
    
    print("\n=== All Tests Complete ===")
    print("\nReady to start indexing!")
    print("Run: python3 scripts/runpod_index_all.py")


if __name__ == '__main__':
    main()