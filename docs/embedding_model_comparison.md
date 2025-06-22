# Embedding Model Comparison for BiotechScanner RAG Pipeline

## Key Considerations for Our Use Case

1. **Domain**: Biotech/pharmaceutical SEC filings with heavy scientific/medical terminology
2. **Scale**: ~40,000 filings → ~4-8M chunks to embed
3. **Requirements**: 
   - High accuracy on financial + scientific terms
   - Reasonable speed for initial indexing
   - Moderate embedding dimensions for storage
   - Good performance on both keyword and semantic search

## Model Options Analysis

### 1. General-Purpose Models (Good Starting Points)

#### all-MiniLM-L6-v2
- **Dimensions**: 384
- **Speed**: Very fast (5000 sentences/sec on GPU)
- **Size**: 80MB
- **Pros**: Excellent speed/quality tradeoff, well-tested
- **Cons**: May miss nuanced biotech terminology
- **Use case**: Great for prototyping and may be sufficient

#### all-mpnet-base-v2
- **Dimensions**: 768
- **Speed**: Fast (2800 sentences/sec on GPU)
- **Size**: 420MB
- **Pros**: Best general-purpose quality, good baseline
- **Cons**: Larger embeddings = more storage
- **Use case**: If MiniLM doesn't capture enough nuance

#### bge-small-en-v1.5
- **Dimensions**: 384
- **Speed**: Very fast
- **Size**: 133MB
- **Pros**: Strong performance, optimized for retrieval
- **Cons**: Less tested on scientific content
- **Use case**: Alternative to MiniLM with similar performance

### 2. Domain-Specific Models (Better for Biotech)

#### BiomedBERT-base
- **Dimensions**: 768
- **Speed**: Moderate (1500 sentences/sec)
- **Size**: 420MB
- **Pros**: Trained on PubMed + PMC articles, understands medical terms
- **Cons**: Not specifically trained for retrieval tasks
- **Use case**: Good for medical/scientific accuracy

#### SciBERT
- **Dimensions**: 768
- **Speed**: Moderate
- **Size**: 440MB
- **Pros**: Trained on scientific papers, good for technical content
- **Cons**: May not handle financial terms as well
- **Use case**: Strong scientific understanding

#### S-PubMedBert-MS-MARCO
- **Dimensions**: 768
- **Speed**: Moderate
- **Size**: 420MB
- **Pros**: Biomedical + trained for retrieval tasks
- **Cons**: Larger model, slower
- **Use case**: Best of both worlds for our domain

### 3. Specialized Financial Models

#### FinBERT
- **Dimensions**: 768
- **Speed**: Moderate
- **Size**: 440MB
- **Pros**: Understands financial terminology
- **Cons**: May miss scientific/medical nuances
- **Use case**: If financial accuracy is priority

### 4. Latest Generation Models

#### gte-small
- **Dimensions**: 384
- **Speed**: Fast
- **Size**: 130MB
- **Pros**: Recent model with strong benchmarks
- **Cons**: Less community testing
- **Use case**: Modern alternative to MiniLM

#### e5-small-v2
- **Dimensions**: 384
- **Speed**: Fast
- **Size**: 133MB
- **Pros**: Excellent retrieval performance
- **Cons**: Requires specific prompt format
- **Use case**: If following exact prompt templates

## Hybrid Approach (Recommended)

Given our specific needs, I recommend a hybrid approach:

1. **Start with all-MiniLM-L6-v2** for rapid prototyping
2. **Test with S-PubMedBert-MS-MARCO** for comparison
3. **Consider ensemble approach**: 
   - Use domain model for medical/drug terms
   - Use general model for financial/business sections

## Benchmark Plan

```python
# We should benchmark on our actual data:
test_queries = [
    "Phase 3 trial results for oncology drugs",
    "Cash runway and burn rate",
    "FDA approval timeline PDUFA date",
    "Adverse events in clinical trials",
    "Revenue from drug sales"
]

test_chunks = [
    # Extract real chunks from SEC filings
    # Mix of clinical, financial, and regulatory content
]
```

## Storage Impact

| Model | Dimensions | Storage for 8M vectors | Query Speed |
|-------|------------|----------------------|-------------|
| all-MiniLM-L6-v2 | 384 | 12.3 GB | Very Fast |
| S-PubMedBert | 768 | 24.6 GB | Moderate |
| all-mpnet-base-v2 | 768 | 24.6 GB | Fast |
| bge-small-en | 384 | 12.3 GB | Very Fast |

## Implementation Recommendation

```python
# Start with this configuration:
from sentence_transformers import SentenceTransformer

# Option 1: Fast general-purpose
model = SentenceTransformer('all-MiniLM-L6-v2')

# Option 2: Domain-specific (after testing)
# model = SentenceTransformer('pritamdeka/S-PubMedBert-MS-MARCO')

# Option 3: Ensemble approach
class EnsembleEmbedder:
    def __init__(self):
        self.general_model = SentenceTransformer('all-MiniLM-L6-v2')
        self.bio_model = SentenceTransformer('pritamdeka/S-PubMedBert-MS-MARCO')
        
    def encode(self, texts, is_medical=False):
        if is_medical:
            return self.bio_model.encode(texts)
        return self.general_model.encode(texts)
```

## Next Steps

1. Start with all-MiniLM-L6-v2 for initial implementation
2. Create benchmark dataset from actual SEC filings
3. Test retrieval quality with different models
4. Consider fine-tuning on our specific domain if needed