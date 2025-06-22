"""
Document processing utilities for SEC filings.
Handles text extraction, chunking, and preprocessing.
"""
import re
import gzip
from typing import List, Dict, Tuple, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class SECDocumentProcessor:
    """Process SEC filings for RAG pipeline."""
    
    # Common section headers in SEC filings
    SEC_SECTIONS = [
        "BUSINESS",
        "RISK FACTORS",
        "MANAGEMENT'S DISCUSSION AND ANALYSIS",
        "FINANCIAL STATEMENTS",
        "CLINICAL TRIALS",
        "PRODUCT PIPELINE",
        "INTELLECTUAL PROPERTY",
        "COMPETITION",
        "REGULATORY",
        "ITEM 1A",
        "ITEM 7",
        "PART I",
        "PART II",
    ]
    
    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 50):
        """
        Initialize document processor.
        
        Args:
            chunk_size: Target size for chunks in tokens (rough estimate: 1 token ≈ 4 chars)
            chunk_overlap: Number of tokens to overlap between chunks
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.chunk_char_size = chunk_size * 4  # Rough approximation
        self.overlap_char_size = chunk_overlap * 4
    
    def load_filing(self, file_path: str) -> str:
        """Load and decompress SEC filing from disk."""
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"Filing not found: {file_path}")
        
        try:
            with gzip.open(path, 'rt', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            return content
        except Exception as e:
            logger.error(f"Error loading filing {file_path}: {e}")
            raise
    
    def clean_text(self, text: str) -> str:
        """Clean SEC filing text."""
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove page numbers and headers
        text = re.sub(r'Page \d+ of \d+', '', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Remove HTML entities if any remain
        text = re.sub(r'&[a-zA-Z]+;', ' ', text)
        
        # Fix common OCR/extraction issues
        text = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', text)  # Add space between camelCase
        
        return text.strip()
    
    def identify_sections(self, text: str) -> List[Tuple[str, int, int]]:
        """
        Identify major sections in the document.
        
        Returns:
            List of (section_name, start_pos, end_pos)
        """
        sections = []
        
        # Create regex pattern for section headers
        section_pattern = r'(?:^|\n)\s*(' + '|'.join(self.SEC_SECTIONS) + r')[\s:\.\n]'
        
        matches = list(re.finditer(section_pattern, text, re.IGNORECASE | re.MULTILINE))
        
        for i, match in enumerate(matches):
            section_name = match.group(1).strip()
            start_pos = match.start()
            
            # End position is either next section or end of document
            end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            
            sections.append((section_name, start_pos, end_pos))
        
        # If no sections found, treat entire document as one section
        if not sections:
            sections.append(("FULL_DOCUMENT", 0, len(text)))
        
        return sections
    
    def chunk_text(self, text: str, metadata: Dict = None) -> List[Dict]:
        """
        Chunk text into overlapping segments with metadata.
        
        Args:
            text: Text to chunk
            metadata: Additional metadata to attach to each chunk
            
        Returns:
            List of chunk dictionaries with text and metadata
        """
        if metadata is None:
            metadata = {}
        
        # Clean the text first
        text = self.clean_text(text)
        
        # Identify sections
        sections = self.identify_sections(text)
        
        chunks = []
        chunk_id = 0
        
        for section_name, section_start, section_end in sections:
            section_text = text[section_start:section_end]
            
            # Skip very short sections
            if len(section_text.strip()) < 100:
                continue
            
            # Chunk within sections to preserve context
            pos = 0
            while pos < len(section_text):
                # Find chunk boundaries at sentence/paragraph breaks if possible
                chunk_end = min(pos + self.chunk_char_size, len(section_text))
                
                # Try to end at a sentence boundary
                if chunk_end < len(section_text):
                    # Look for sentence end markers
                    sentence_ends = ['. ', '.\n', '? ', '?\n', '! ', '!\n']
                    for marker in sentence_ends:
                        last_marker = section_text.rfind(marker, pos + self.chunk_char_size // 2, chunk_end)
                        if last_marker != -1:
                            chunk_end = last_marker + len(marker)
                            break
                
                chunk_text = section_text[pos:chunk_end].strip()
                
                if chunk_text:
                    chunk_data = {
                        'text': chunk_text,
                        'chunk_id': chunk_id,
                        'section': section_name,
                        'char_start': section_start + pos,
                        'char_end': section_start + chunk_end,
                        **metadata
                    }
                    chunks.append(chunk_data)
                    chunk_id += 1
                
                # Move position with overlap
                pos = chunk_end - self.overlap_char_size
                if pos >= len(section_text) - self.overlap_char_size:
                    break
        
        return chunks
    
    def extract_key_sentences(self, text: str, keywords: List[str]) -> List[str]:
        """Extract sentences containing specific keywords."""
        sentences = re.split(r'[.!?]\s+', text)
        key_sentences = []
        
        for sentence in sentences:
            sentence_lower = sentence.lower()
            if any(keyword.lower() in sentence_lower for keyword in keywords):
                key_sentences.append(sentence.strip())
        
        return key_sentences


def create_filing_chunks(filing_path: str, filing_metadata: Dict) -> List[Dict]:
    """
    Convenience function to process a single filing.
    
    Args:
        filing_path: Path to compressed filing
        filing_metadata: Metadata about the filing (company_id, filing_type, date, etc.)
        
    Returns:
        List of chunks ready for embedding
    """
    processor = SECDocumentProcessor()
    
    try:
        # Load filing
        text = processor.load_filing(filing_path)
        
        # Create chunks with metadata
        chunks = processor.chunk_text(text, filing_metadata)
        
        logger.info(f"Created {len(chunks)} chunks from {filing_path}")
        return chunks
        
    except Exception as e:
        logger.error(f"Error processing filing {filing_path}: {e}")
        return []