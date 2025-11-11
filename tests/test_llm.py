"""
Tests for LLM integration and embedding services.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from typing import List

from src.core.llm import LLMProvider, LLMResponse, LLMManager, OpenAIClient, AnthropicClient
from src.core.embeddings import EmbeddingService
from src.core.config import settings


class TestLLMResponse:
    """Test LLM response model."""
    
    def test_llm_response_creation(self):
        """Test LLM response object creation."""
        response = LLMResponse(
            content="Test response",
            provider=LLMProvider.OPENAI,
            metadata={"tokens_used": 100, "model": "gpt-3.5-turbo"}
        )
        
        assert response.content == "Test response"
        assert response.provider == LLMProvider.OPENAI
        assert response.tokens_used == 100
        assert response.model == "gpt-3.5-turbo"
    
    def test_llm_response_empty_metadata(self):
        """Test LLM response with empty metadata."""
        response = LLMResponse(
            content="Test response",
            provider=LLMProvider.ANTHROPIC
        )
        
        assert response.tokens_used == 0
        assert response.model == "unknown"


class TestOpenAIClient:
    """Test OpenAI client implementation."""
    
    @pytest.fixture
    def mock_client(self):
        """Create a mock OpenAI client."""
        with patch('src.core.llm.httpx.AsyncClient') as mock_httpx:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.raise_for_status = Mock()
            
            mock_client = Mock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_httpx.return_value = mock_client
            
            client = OpenAIClient("test-api-key")
            return client, mock_client, mock_response
    
    @pytest.mark.asyncio
    async def test_generate_text_success(self, mock_client):
        """Test successful text generation."""
        client, mock_http_client, mock_response = mock_client
        
        # Mock API response
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Generated text"}}],
            "usage": {
                "total_tokens": 50,
                "prompt_tokens": 10,
                "completion_tokens": 40
            }
        }
        
        response = await client.generate_text("Test prompt")
        
        assert response.content == "Generated text"
        assert response.provider == LLMProvider.OPENAI
        assert response.tokens_used == 50
        assert response.model == "gpt-3.5-turbo"
        
        # Verify API call
        mock_http_client.post.assert_called_once()
        call_args = mock_http_client.post.call_args
        assert "/chat/completions" in str(call_args)
    
    @pytest.mark.asyncio
    async def test_generate_embedding_success(self, mock_client):
        """Test successful embedding generation."""
        client, mock_http_client, mock_response = mock_client
        
        # Mock embedding response
        test_embedding = [0.1] * 1536
        mock_response.json.return_value = {
            "data": [{"embedding": test_embedding}],
            "usage": {"total_tokens": 10}
        }
        
        embedding = await client.generate_embedding("Test text")
        
        assert embedding == test_embedding
        assert len(embedding) == 1536
        
        # Verify API call
        mock_http_client.post.assert_called_once()
        call_args = mock_http_client.post.call_args
        assert "/embeddings" in str(call_args)
    
    @pytest.mark.asyncio
    async def test_api_validation_success(self, mock_client):
        """Test successful API key validation."""
        client, mock_http_client, mock_response = mock_client
        
        is_valid = await client.validate_api_key()
        
        assert is_valid == True
        mock_http_client.get.assert_called_once_with("/models")


class TestAnthropicClient:
    """Test Anthropic client implementation."""
    
    @pytest.fixture
    def mock_client(self):
        """Create a mock Anthropic client."""
        with patch('src.core.llm.httpx.AsyncClient') as mock_httpx:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.raise_for_status = Mock()
            
            mock_client = Mock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_httpx.return_value = mock_client
            
            client = AnthropicClient("test-api-key")
            return client, mock_client, mock_response
    
    @pytest.mark.asyncio
    async def test_generate_text_success(self, mock_client):
        """Test successful text generation."""
        client, mock_http_client, mock_response = mock_client
        
        # Mock API response
        mock_response.json.return_value = {
            "content": [{"text": "Generated response"}],
            "usage": {
                "input_tokens": 10,
                "output_tokens": 30
            }
        }
        
        response = await client.generate_text("Test prompt")
        
        assert response.content == "Generated response"
        assert response.provider == LLMProvider.ANTHROPIC
        assert response.tokens_used == 40  # 10 + 30
        assert response.model == "claude-3-haiku-20240307"
    
    @pytest.mark.asyncio
    async def test_embedding_not_implemented(self, mock_client):
        """Test that embedding generation raises NotImplementedError."""
        client, _, _ = mock_client
        
        with pytest.raises(NotImplementedError):
            await client.generate_embedding("Test text")


class TestLLMManager:
    """Test LLM manager with fallback support."""
    
    @pytest.fixture
    def mock_llm_manager(self):
        """Create a mock LLM manager."""
        with patch('src.core.llm.settings') as mock_settings:
            mock_settings.openai_api_key = "test-openai-key"
            mock_settings.anthropic_api_key = "test-anthropic-key"
            
            with patch('src.core.llm.OpenAIClient') as mock_openai, \
                 patch('src.core.llm.AnthropicClient') as mock_anthropic:
                
                mock_openai_client = Mock()
                mock_anthropic_client = Mock()
                
                # Mock validate_api_key to return True
                mock_openai_client.validate_api_key = AsyncMock(return_value=True)
                mock_anthropic_client.validate_api_key = AsyncMock(return_value=True)
                
                # Mock generate_text
                mock_response = LLMResponse("Test response", LLMProvider.OPENAI)
                mock_openai_client.generate_text = AsyncMock(return_value=mock_response)
                
                mock_openai.return_value = mock_openai_client
                mock_anthropic.return_value = mock_anthropic_client
                
                manager = LLMManager()
                return manager, mock_openai_client, mock_anthropic_client
    
    def test_initialization(self, mock_llm_manager):
        """Test LLM manager initialization."""
        manager, _, _ = mock_llm_manager
        assert LLMProvider.OPENAI in manager.clients
        assert LLMProvider.ANTHROPIC in manager.clients
        assert manager.primary_provider == LLMProvider.OPENAI
        assert manager.embedding_provider == LLMProvider.OPENAI
    
    @pytest.mark.asyncio
    async def test_generate_text_success(self, mock_llm_manager):
        """Test successful text generation."""
        manager, mock_openai, _ = mock_llm_manager
        
        response = await manager.generate_text("Test prompt")
        
        assert response.content == "Test response"
        assert response.provider == LLMProvider.OPENAI
        mock_openai.generate_text.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_generate_text_fallback(self, mock_llm_manager):
        """Test text generation with fallback."""
        manager, mock_openai, mock_anthropic = mock_llm_manager
        
        # Mock primary provider to fail
        mock_openai.generate_text = AsyncMock(side_effect=Exception("Primary failed"))
        
        # Mock fallback to succeed
        fallback_response = LLMResponse("Fallback response", LLMProvider.ANTHROPIC)
        mock_anthropic.generate_text = AsyncMock(return_value=fallback_response)
        
        response = await manager.generate_text("Test prompt")
        
        assert response.content == "Fallback response"
        assert response.provider == LLMProvider.ANTHROPIC
    
    @pytest.mark.asyncio
    async def test_validate_clients(self, mock_llm_manager):
        """Test client validation."""
        manager, mock_openai, mock_anthropic = mock_llm_manager
        
        results = await manager.validate_all_clients()
        
        assert results[LLMProvider.OPENAI] == True
        assert results[LLMProvider.ANTHROPIC] == True
        mock_openai.validate_api_key.assert_called_once()
        mock_anthropic.validate_api_key.assert_called_once()


class TestEmbeddingService:
    """Test embedding service functionality."""
    
    @pytest.fixture
    def mock_embedding_service(self):
        """Create a mock embedding service."""
        service = EmbeddingService()
        
        # Mock LLM manager
        mock_llm_manager = Mock()
        test_embedding = [0.1] * 1536
        mock_llm_manager.generate_embedding = AsyncMock(return_value=test_embedding)
        
        service.llm_manager = mock_llm_manager
        return service, mock_llm_manager, test_embedding
    
    def test_cache_key_generation(self, mock_embedding_service):
        """Test cache key generation."""
        service, _, _ = mock_embedding_service
        
        key1 = service._get_cache_key("test text")
        key2 = service._get_cache_key("test text")
        key3 = service._get_cache_key("different text")
        
        assert key1 == key2
        assert key1 != key3
        assert len(key1) == 32  # MD5 hash length
    
    @pytest.mark.asyncio
    async def test_generate_embedding_with_cache(self, mock_embedding_service):
        """Test embedding generation with caching."""
        service, mock_llm_manager, test_embedding = mock_embedding_service
        
        # First call should use LLM
        embedding1 = await service.generate_embedding("test text")
        assert embedding1 == test_embedding
        assert mock_llm_manager.generate_embedding.call_count == 1
        
        # Second call should use cache
        embedding2 = await service.generate_embedding("test text")
        assert embedding2 == test_embedding
        assert mock_llm_manager.generate_embedding.call_count == 1  # No additional call
    
    @pytest.mark.asyncio
    async def test_similarity_calculation(self, mock_embedding_service):
        """Test similarity calculation."""
        service, _, _ = mock_embedding_service
        
        # Identical vectors should have similarity 1.0
        vec1 = [0.1] * 1536
        vec2 = [0.1] * 1536
        
        similarity = service.calculate_similarity(vec1, vec2)
        assert abs(similarity - 1.0) < 1e-6
        
        # Orthogonal vectors should have similarity 0.0
        vec3 = [1.0] + [0.0] * 1535
        vec4 = [0.0] + [1.0] + [0.0] * 1534
        
        similarity = service.calculate_similarity(vec3, vec4)
        assert abs(similarity - 0.0) < 1e-6
    
    def test_cache_stats(self, mock_embedding_service):
        """Test cache statistics."""
        service, _, _ = mock_embedding_service
        
        # Initially empty
        stats = service.get_cache_stats()
        assert stats["cache_hits"] == 0
        assert stats["cache_misses"] == 0
        assert stats["hit_rate"] == 0.0
        
        # Add some cache hits/misses
        service.cache_hits = 8
        service.cache_misses = 2
        
        stats = service.get_cache_stats()
        assert stats["cache_hits"] == 8
        assert stats["cache_misses"] == 2
        assert stats["hit_rate"] == 0.8
    
    @pytest.mark.asyncio
    async def test_batch_embeddings(self, mock_embedding_service):
        """Test batch embedding generation."""
        service, mock_llm_manager, test_embedding = mock_embedding_service
        
        texts = ["text1", "text2", "text3"]
        embeddings = await service.generate_batch_embeddings(texts)
        
        assert len(embeddings) == 3
        assert all(emb == test_embedding for emb in embeddings)
        
        # Should have made 3 calls to LLM (no cache hits initially)
        assert mock_llm_manager.generate_embedding.call_count == 3


class TestIntegration:
    """Integration tests for LLM and embedding services."""
    
    @pytest.mark.asyncio
    async def test_end_to_end_embedding_workflow(self):
        """Test complete embedding workflow."""
        # This would be a real integration test with actual API calls
        # Skip by default to avoid API costs
        pytest.skip("Integration test - requires actual API keys")
    
    @pytest.mark.asyncio
    async def test_service_initialization(self):
        """Test service initialization with mock config."""
        with patch('src.core.llm.settings') as mock_settings:
            mock_settings.openai_api_key = "test-key"
            mock_settings.anthropic_api_key = ""
            
            with patch('src.core.llm.OpenAIClient') as mock_openai:
                mock_openai_client = Mock()
                mock_openai_client.validate_api_key = AsyncMock(return_value=True)
                mock_openai.return_value = mock_openai_client
                
                from src.core.llm import initialize_llm
                
                manager = await initialize_llm()
                assert manager is not None


if __name__ == "__main__":
    pytest.main([__file__])