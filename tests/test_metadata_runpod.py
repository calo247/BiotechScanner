#!/usr/bin/env python3
"""
Test script to check metadata.pkl integrity on RunPod.
Copy this script to RunPod and run it in the BiotechScanner directory.
"""
import pickle
import os
from pathlib import Path

def test_metadata():
    """Test if metadata.pkl can be loaded properly."""
    metadata_path = Path("data/faiss/metadata.pkl")
    
    print("="*60)
    print("METADATA.PKL INTEGRITY TEST")
    print("="*60)
    
    # 1. Check if file exists
    if not metadata_path.exists():
        print(f"ERROR: {metadata_path} does not exist!")
        return False
    
    # 2. Check file size
    file_size = metadata_path.stat().st_size
    print(f"\n1. File Information:")
    print(f"   Path: {metadata_path}")
    print(f"   Size: {file_size:,} bytes ({file_size/1024/1024:.1f} MB)")
    
    # 3. Try to load the file
    print(f"\n2. Loading metadata.pkl...")
    try:
        with open(metadata_path, 'rb') as f:
            metadata = pickle.load(f)
        print(f"   ✓ SUCCESS: Loaded metadata.pkl")
        print(f"   - Total entries: {len(metadata):,}")
        
        # 4. Check structure of a few entries
        print(f"\n3. Checking metadata structure:")
        sample_keys = list(metadata.keys())[:5]
        for i, key in enumerate(sample_keys):
            entry = metadata[key]
            print(f"\n   Entry {i+1} (chunk_id: {key}):")
            for field, value in entry.items():
                if field == 'text':
                    print(f"     - {field}: {'PRESENT' if value else 'EMPTY'} ({len(value) if value else 0} chars)")
                elif field == 'file_path':
                    print(f"     - {field}: {value}")
                else:
                    print(f"     - {field}: {value}")
        
        # 5. Check if entries have file_path (new format) or text (old format)
        print(f"\n4. Checking format (text vs file_path):")
        has_text = 0
        has_file_path = 0
        has_both = 0
        has_neither = 0
        
        # Sample 1000 entries
        sample_size = min(1000, len(metadata))
        for key in list(metadata.keys())[:sample_size]:
            entry = metadata[key]
            has_t = 'text' in entry
            has_f = 'file_path' in entry
            
            if has_t and has_f:
                has_both += 1
            elif has_t:
                has_text += 1
            elif has_f:
                has_file_path += 1
            else:
                has_neither += 1
        
        print(f"   Sample of {sample_size} entries:")
        print(f"   - Has text field only: {has_text}")
        print(f"   - Has file_path only: {has_file_path}")
        print(f"   - Has both: {has_both}")
        print(f"   - Has neither: {has_neither}")
        
        # 6. Memory usage estimate
        print(f"\n5. Memory usage estimate:")
        if has_text > has_file_path:
            avg_text_len = sum(len(metadata[k].get('text', '')) for k in list(metadata.keys())[:100]) / 100
            estimated_memory = (avg_text_len * len(metadata)) / 1024 / 1024
            print(f"   - Format: OLD (storing full text)")
            print(f"   - Avg text length (100 samples): {avg_text_len:.0f} chars")
            print(f"   - Estimated text memory: {estimated_memory:.0f} MB")
        else:
            print(f"   - Format: NEW (storing file paths)")
            print(f"   - Memory efficient format detected")
        
        print(f"\n✓ METADATA FILE IS VALID AND COMPLETE")
        return True
        
    except EOFError as e:
        print(f"   ✗ ERROR: EOFError - File is truncated!")
        print(f"   The file appears to be incomplete.")
        
        # Try to see how much can be read
        print(f"\n   Attempting partial read to find truncation point...")
        with open(metadata_path, 'rb') as f:
            data = f.read()
            # Check last bytes
            print(f"   - File ends with: {repr(data[-20:])}")
            if not data.endswith(b'.'):
                print(f"   - Missing pickle STOP opcode")
        return False
        
    except Exception as e:
        print(f"   ✗ ERROR: {type(e).__name__}: {e}")
        return False
    
    
def test_related_files():
    """Also test the related FAISS files."""
    print(f"\n\n{'='*60}")
    print("RELATED FILES TEST")
    print("='*60")
    
    files_to_check = [
        "data/faiss/sec_filings.index",
        "data/faiss/id_map.json",
        "data/faiss/metadata.pkl"
    ]
    
    for file_path in files_to_check:
        if os.path.exists(file_path):
            size = os.path.getsize(file_path)
            print(f"✓ {file_path}: {size:,} bytes ({size/1024/1024:.1f} MB)")
        else:
            print(f"✗ {file_path}: NOT FOUND")


if __name__ == "__main__":
    print("Testing metadata.pkl on RunPod...\n")
    
    # Test metadata
    metadata_ok = test_metadata()
    
    # Test related files
    test_related_files()
    
    print(f"\n\nTEST COMPLETE")
    print("="*60)
    
    if metadata_ok:
        print("✓ Metadata file is GOOD - safe to download")
        print("\nTo download to local machine:")
        print("rsync -avz --progress runpod:/path/to/BiotechScanner/data/faiss/metadata.pkl ./data/faiss/")
    else:
        print("✗ Metadata file is CORRUPTED - needs to be recreated")
        print("\nThe index needs to be rebuilt with the new format.")