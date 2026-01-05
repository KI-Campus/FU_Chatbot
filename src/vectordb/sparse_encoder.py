"""
Sparse Vector Encoder for Hybrid Retrieval (BM25-style).

This encoder creates sparse vectors for keyword-based retrieval,
complementing dense semantic vectors for hybrid search in Qdrant.
"""

from collections import Counter
from typing import Dict, List

from qdrant_client.models import SparseVector


class BM25SparseEncoder:
    """BM25-style sparse encoder for hybrid retrieval.
    
    Creates sparse vectors based on token frequencies, similar to BM25/TF-IDF.
    Uses simple tokenization for efficiency and compatibility with Qdrant.
    """
    
    def __init__(self, vocab_size: int = 30000):
        """Initialize the sparse encoder.
        
        Args:
            vocab_size: Maximum vocabulary size for hashing tokens
        """
        self.vocab_size = vocab_size
        
    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenization: lowercase, split on whitespace and punctuation.
        
        Args:
            text: Input text to tokenize
            
        Returns:
            List of tokens
        """
        import re
        
        # Lowercase and remove special characters except spaces
        text = text.lower()
        # Split on whitespace and punctuation
        tokens = re.findall(r'\b\w+\b', text)
        
        return tokens
    
    def _token_to_id(self, token: str) -> int:
        """Convert token to integer ID using hash function.
        
        Args:
            token: Token string
            
        Returns:
            Integer ID within vocab_size range
        """
        return hash(token) % self.vocab_size
    
    def encode(self, text: str) -> SparseVector:
        """Encode text into sparse vector with TF-based weights.
        
        Args:
            text: Input text to encode
            
        Returns:
            SparseVector with token IDs as indices and TF scores as values
        """
        # Tokenize
        tokens = self._tokenize(text)
        
        if not tokens:
            # Return empty sparse vector
            return SparseVector(indices=[], values=[])
        
        # Count token frequencies (TF)
        token_counts = Counter(tokens)
        
        # Convert to token IDs
        token_ids_with_counts = {}
        for token, count in token_counts.items():
            token_id = self._token_to_id(token)
            # If hash collision, sum the counts
            token_ids_with_counts[token_id] = token_ids_with_counts.get(token_id, 0) + count
        
        # Normalize by document length (simple TF normalization)
        doc_length = len(tokens)
        
        # Create sparse vector
        indices = []
        values = []
        
        for token_id, count in sorted(token_ids_with_counts.items()):
            indices.append(token_id)
            # Simple TF score: count / doc_length
            # Could be enhanced with IDF, but for simplicity we use TF
            tf_score = count / doc_length
            values.append(tf_score)
        
        return SparseVector(indices=indices, values=values)
    
    def encode_queries(self, queries: List[str]) -> List[SparseVector]:
        """Encode multiple queries.
        
        Args:
            queries: List of query strings
            
        Returns:
            List of SparseVectors
        """
        return [self.encode(query) for query in queries]


if __name__ == "__main__":
    # Test the encoder
    encoder = BM25SparseEncoder()
    
    test_texts = [
        "Deep Learning is a subset of Machine Learning",
        "What is Deep Learning?",
        "Künstliche Intelligenz und Machine Learning auf dem KI-Campus"
    ]
    
    for text in test_texts:
        sparse_vec = encoder.encode(text)
        print(f"\nText: {text}")
        print(f"Sparse Vector: {len(sparse_vec.indices)} non-zero dimensions")
        print(f"Sample indices: {sparse_vec.indices[:5]}")
        print(f"Sample values: {sparse_vec.values[:5]}")
