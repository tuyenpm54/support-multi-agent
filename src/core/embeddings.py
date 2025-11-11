"""
Embedding Generation and Management Service

Handles text embedding generation, caching, and vector operations
for semantic search and issue classification.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
import numpy as np
import pickle
import hashlib
from datetime import datetime, timedelta

from src.core.llm import get_llm_manager, LLMResponse
from src.core.config import settings


class EmbeddingService:
    """Service for generating and managing text embeddings."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.llm_manager = None
        self.embedding_cache: Dict[str, List[float]] = {}
        self.cache_ttl = 3600  # 1 hour
        self.cache_timestamps: Dict[str, datetime] = {}
        self.embedding_dimensions = 1536  # OpenAI text-embedding-3-small dimensions
        
        # Performance metrics
        self.cache_hits = 0
        self.cache_misses = 0
        self.total_embeddings = 0
        self.total_tokens = 0
    
    async def initialize(self):
        """Initialize the embedding service."""
        try:
            self.llm_manager = await get_llm_manager()
            self.logger.info("Embedding service initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize embedding service: {str(e)}")
            raise
    
    def _get_cache_key(self, text: str) -> str:
        """Generate cache key for text."""
        # Use hash of text to handle long texts efficiently
        return hashlib.md5(text.encode('utf-8')).hexdigest()
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cached embedding is still valid."""
        if cache_key not in self.cache_timestamps:
            return False
        
        age = datetime.now() - self.cache_timestamps[cache_key]
        return age.total_seconds() < self.cache_ttl
    
    async def generate_embedding(self, text: str, use_cache: bool = True) -> List[float]:
        """
        Generate embedding for text with caching support.
        
        Args:
            text: Text to embed
            use_cache: Whether to use cached embeddings
            
        Returns:
            List of embedding dimensions
        """
        if not self.llm_manager:
            raise Exception("Embedding service not initialized")
        
        cache_key = self._get_cache_key(text)
        
        # Check cache first
        if use_cache and cache_key in self.embedding_cache and self._is_cache_valid(cache_key):
            self.cache_hits += 1
            self.logger.debug(f"Cache hit for text (length: {len(text)})")
            return self.embedding_cache[cache_key]
        
        # Generate new embedding
        try:
            self.cache_misses += 1
            embedding = await self.llm_manager.generate_embedding(text)
            
            # Validate embedding dimensions
            if len(embedding) != self.embedding_dimensions:
                self.logger.warning(f"Unexpected embedding dimensions: {len(embedding)} (expected: {self.embedding_dimensions})")
            
            # Cache the result
            if use_cache:
                self.embedding_cache[cache_key] = embedding
                self.cache_timestamps[cache_key] = datetime.now()
            
            self.total_embeddings += 1
            self.logger.debug(f"Generated new embedding (dimensions: {len(embedding)})")
            
            return embedding
            
        except Exception as e:
            self.logger.error(f"Failed to generate embedding: {str(e)}")
            raise
    
    async def generate_batch_embeddings(self, texts: List[str], use_cache: bool = True) -> List[List[float]]:
        """
        Generate embeddings for multiple texts in parallel.
        
        Args:
            texts: List of texts to embed
            use_cache: Whether to use cached embeddings
            
        Returns:
            List of embedding vectors
        """
        if not texts:
            return []
        
        self.logger.info(f"Generating batch embeddings for {len(texts)} texts")
        
        # Check cache for all texts first
        uncached_texts = []
        uncached_indices = []
        embeddings = [None] * len(texts)
        
        for i, text in enumerate(texts):
            cache_key = self._get_cache_key(text)
            
            if use_cache and cache_key in self.embedding_cache and self._is_cache_valid(cache_key):
                embeddings[i] = self.embedding_cache[cache_key]
                self.cache_hits += 1
            else:
                uncached_texts.append(text)
                uncached_indices.append(i)
                self.cache_misses += 1
        
        # Generate embeddings for uncached texts in parallel
        if uncached_texts:
            try:
                # Limit concurrent requests to avoid rate limits
                semaphore = asyncio.Semaphore(5)
                
                async def generate_with_semaphore(text: str, index: int):
                    async with semaphore:
                        embedding = await self.generate_embedding(text, use_cache=False)
                        embeddings[index] = embedding
                        return embedding
                
                tasks = [
                    generate_with_semaphore(text, uncached_indices[i])
                    for i, text in enumerate(uncached_texts)
                ]
                
                await asyncio.gather(*tasks)
                
                # Cache the new embeddings
                for i, text in enumerate(uncached_texts):
                    cache_key = self._get_cache_key(text)
                    self.embedding_cache[cache_key] = embeddings[uncached_indices[i]]
                    self.cache_timestamps[cache_key] = datetime.now()
                
            except Exception as e:
                self.logger.error(f"Failed to generate batch embeddings: {str(e)}")
                raise
        
        self.logger.info(f"Batch embedding generation complete. Cache hits: {self.cache_hits}, misses: {self.cache_misses}")
        
        return embeddings
    
    def calculate_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """
        Calculate cosine similarity between two embeddings.
        
        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector
            
        Returns:
            Cosine similarity score (-1 to 1)
        """
        try:
            # Convert to numpy arrays for efficient calculation
            vec1 = np.array(embedding1, dtype=np.float32)
            vec2 = np.array(embedding2, dtype=np.float32)
            
            # Calculate cosine similarity
            dot_product = np.dot(vec1, vec2)
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            similarity = dot_product / (norm1 * norm2)
            
            # Ensure result is in valid range [-1, 1]
            return max(-1.0, min(1.0, float(similarity)))
            
        except Exception as e:
            self.logger.error(f"Error calculating similarity: {str(e)}")
            return 0.0
    
    def find_most_similar(self, query_embedding: List[float], 
                         candidate_embeddings: List[List[float]], 
                         threshold: float = 0.7) -> List[tuple]:
        """
        Find most similar embeddings to query embedding.
        
        Args:
            query_embedding: Query embedding vector
            candidate_embeddings: List of candidate embedding vectors
            threshold: Minimum similarity threshold
            
        Returns:
            List of tuples (index, similarity_score) sorted by similarity
        """
        similarities = []
        
        for i, candidate_embedding in enumerate(candidate_embeddings):
            similarity = self.calculate_similarity(query_embedding, candidate_embedding)
            if similarity >= threshold:
                similarities.append((i, similarity))
        
        # Sort by similarity (descending)
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        return similarities
    
    def cleanup_expired_cache(self):
        """Remove expired entries from cache."""
        current_time = datetime.now()
        expired_keys = []
        
        for cache_key, timestamp in self.cache_timestamps.items():
            age = current_time - timestamp
            if age.total_seconds() > self.cache_ttl:
                expired_keys.append(cache_key)
        
        for key in expired_keys:
            del self.embedding_cache[key]
            del self.cache_timestamps[key]
        
        if expired_keys:
            self.logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics."""
        total_requests = self.cache_hits + self.cache_misses
        hit_rate = (self.cache_hits / total_requests) if total_requests > 0 else 0
        
        return {
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "hit_rate": hit_rate,
            "cached_embeddings": len(self.embedding_cache),
            "total_embeddings_generated": self.total_embeddings,
            "cache_ttl_seconds": self.cache_ttl,
            "embedding_dimensions": self.embedding_dimensions
        }
    
    def clear_cache(self):
        """Clear all cached embeddings."""
        self.embedding_cache.clear()
        self.cache_timestamps.clear()
        self.logger.info("Embedding cache cleared")
    
    async def test_embedding_generation(self, test_text: str = "This is a test for embedding generation.") -> bool:
        """Test embedding generation functionality."""
        try:
            embedding = await self.generate_embedding(test_text)
            
            # Validate embedding
            if not embedding:
                self.logger.error("Empty embedding generated")
                return False
            
            if len(embedding) != self.embedding_dimensions:
                self.logger.error(f"Invalid embedding dimensions: {len(embedding)}")
                return False
            
            # Check if all values are valid numbers
            if not all(isinstance(x, (int, float)) and not np.isnan(x) for x in embedding):
                self.logger.error("Embedding contains invalid values")
                return False
            
            self.logger.info("Embedding generation test passed")
            return True
            
        except Exception as e:
            self.logger.error(f"Embedding generation test failed: {str(e)}")
            return False


# Global embedding service instance
embedding_service = EmbeddingService()


async def get_embedding_service() -> EmbeddingService:
    """Get the global embedding service instance."""
    if not embedding_service.llm_manager:
        await embedding_service.initialize()
    return embedding_service


# Utility function for simple embedding generation
async def embed_text(text: str) -> List[float]:
    """Convenience function to generate embedding for text."""
    service = await get_embedding_service()
    return await service.generate_embedding(text)