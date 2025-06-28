#!/usr/bin/env python3
"""
Check FAISS index file integrity.
"""
import pickle
import json
import faiss
import sys
from pathlib import Path

def check_faiss_files():
    """Check if FAISS index files can be loaded properly."""
    base_path = Path("data/faiss")
    
    # 1. Check JSON file
    print("1. Checking id_map.json...")
    try:
        with open(base_path / "id_map.json", 'r') as f:
            id_map_data = json.load(f)
            print(f"   ✓ Successfully loaded id_map.json")
            print(f"   - Contains {len(id_map_data.get('id_to_idx', {}))} mappings")
            print(f"   - Next ID: {id_map_data.get('next_id', 'N/A')}")
    except Exception as e:
        print(f"   ✗ Error loading id_map.json: {e}")
    
    # 2. Check FAISS index
    print("\n2. Checking sec_filings.index...")
    try:
        index = faiss.read_index(str(base_path / "sec_filings.index"))
        print(f"   ✓ Successfully loaded FAISS index")
        print(f"   - Index type: {type(index).__name__}")
        print(f"   - Total vectors: {index.ntotal:,}")
        print(f"   - Dimension: {index.d}")
        print(f"   - Is trained: {getattr(index, 'is_trained', 'N/A')}")
    except Exception as e:
        print(f"   ✗ Error loading FAISS index: {e}")
    
    # 3. Check metadata pickle file
    print("\n3. Checking metadata.pkl...")
    print("   (This is where the error occurs)")
    
    # Try different approaches to debug
    try:
        # First, check if file is empty
        file_size = (base_path / "metadata.pkl").stat().st_size
        print(f"   - File size: {file_size:,} bytes")
        
        # Try to load with explicit protocol
        with open(base_path / "metadata.pkl", 'rb') as f:
            # Read first few bytes to check if it's a valid pickle
            header = f.read(10)
            f.seek(0)
            print(f"   - File header (hex): {header.hex()}")
            
            # Try loading
            try:
                metadata = pickle.load(f)
                print(f"   ✓ Successfully loaded metadata.pkl")
                print(f"   - Contains {len(metadata)} entries")
                
                # Sample a few entries
                if metadata:
                    sample_key = list(metadata.keys())[0]
                    print(f"   - Sample entry keys: {list(metadata[sample_key].keys())}")
            except EOFError:
                print("   ✗ EOFError: File appears to be truncated or empty")
                # Try to see how much we can read
                f.seek(0)
                data = f.read()
                print(f"   - Actual file content length: {len(data)} bytes")
                
                # Check if it's all zeros or has actual data
                non_zero = sum(1 for b in data[:1000] if b != 0)
                print(f"   - Non-zero bytes in first 1KB: {non_zero}")
                
    except Exception as e:
        print(f"   ✗ Error checking metadata.pkl: {e}")
    
    # 4. Try alternative pickle loading methods
    print("\n4. Trying alternative loading methods...")
    try:
        # Try loading with different protocols
        for protocol in [None, 0, 1, 2, 3, 4, 5]:
            try:
                with open(base_path / "metadata.pkl", 'rb') as f:
                    if protocol is None:
                        metadata = pickle.load(f)
                    else:
                        metadata = pickle.load(f, encoding='latin1')
                print(f"   ✓ Successfully loaded with protocol {protocol}")
                break
            except:
                continue
    except:
        print("   ✗ Could not load with any protocol")
    
    # 5. Check file consistency
    print("\n5. Checking consistency between files...")
    try:
        # Load id_map
        with open(base_path / "id_map.json", 'r') as f:
            id_map_data = json.load(f)
            max_idx = max(id_map_data['id_to_idx'].values()) if id_map_data['id_to_idx'] else -1
        
        # Load index
        index = faiss.read_index(str(base_path / "sec_filings.index"))
        
        print(f"   - Max index in id_map: {max_idx}")
        print(f"   - Vectors in FAISS: {index.ntotal}")
        print(f"   - Consistent: {'Yes' if max_idx < index.ntotal else 'No'}")
        
    except Exception as e:
        print(f"   ✗ Error checking consistency: {e}")


if __name__ == "__main__":
    check_faiss_files()