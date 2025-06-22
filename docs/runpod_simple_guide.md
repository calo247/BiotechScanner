# RunPod Simple Setup Guide

## What You Actually Need

1. **Deploy RunPod GPU** (RTX 4090 recommended)
2. **Clone your repo on RunPod**
3. **Copy your database**
4. **Re-download SEC filings** 
5. **Run indexing**

## Step by Step

### 1. Deploy RunPod
- Go to runpod.io
- Deploy RTX 4090 pod
- Get SSH details

### 2. On RunPod - Setup
```bash
cd /workspace
git clone https://github.com/yourusername/BiotechScanner.git
cd BiotechScanner

# Setup Python environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Install GPU versions
pip uninstall -y torch faiss-cpu
pip install torch --index-url https://download.pytorch.org/whl/cu118
pip install faiss-gpu
```

### 3. Copy Database (from your local machine)
```bash
scp -P [PORT] data/database.db root@[RUNPOD_IP]:/workspace/BiotechScanner/data/
scp -P [PORT] .env root@[RUNPOD_IP]:/workspace/BiotechScanner/
```

### 4. On RunPod - Download SEC Filings
```bash
cd /workspace/BiotechScanner
source venv/bin/activate

# Re-download SEC filings (fast on RunPod)
python3 scripts/runpod_download_sec_filings.py --top-n 50
```

### 5. Run Indexing
```bash
# Test first
python3 scripts/test_gpu_indexing.py

# Then index
python3 scripts/runpod_index_all.py
```

### 6. Download Results
```bash
# From local machine
scp -r -P [PORT] root@[RUNPOD_IP]:/workspace/BiotechScanner/data/faiss/ data/
```

That's it! No need for tar files or complex scripts.