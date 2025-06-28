#!/usr/bin/env python3
"""
Inspect the corrupted pickle file.
"""
import pickle
import struct

def inspect_pickle():
    """Try to understand the pickle file structure."""
    with open("data/faiss/metadata.pkl", "rb") as f:
        # Read header
        data = f.read(1000)
        
        print("Pickle file inspection:")
        print(f"First 50 bytes (hex): {data[:50].hex()}")
        print(f"First 50 bytes (repr): {repr(data[:50])}")
        
        # Check for pickle protocol
        if data[0:2] == b'\x80\x04':
            print("\nDetected pickle protocol 4")
        elif data[0:2] == b'\x80\x03':
            print("\nDetected pickle protocol 3")
        
        # Try to find the end of file
        f.seek(-1000, 2)  # Go to 1KB before end
        end_data = f.read()
        print(f"\nLast 50 bytes (hex): {end_data[-50:].hex()}")
        print(f"Last 50 bytes (repr): {repr(end_data[-50:])}")
        
        # Check if file ends properly
        if end_data.endswith(b'.'):
            print("\nFile ends with STOP opcode (good)")
        else:
            print("\nFile does NOT end with STOP opcode (truncated)")
        
        # Try to manually unpickle a small portion
        f.seek(0)
        unpickler = pickle.Unpickler(f)
        
        try:
            # Try to read just the first object
            print("\nTrying to read first object...")
            first = unpickler.load()
            print(f"Successfully read first object of type: {type(first)}")
        except Exception as e:
            print(f"Failed to read first object: {e}")


if __name__ == "__main__":
    inspect_pickle()