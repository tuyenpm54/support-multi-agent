"""
Integration tests for the multi-agent support system.
"""

import pytest
import asyncio
from unittest.mock import patch, AsyncMock

from src.core.llm import LLMManager, initialize_llm
from src.core.embeddings import EmbeddingService, get_embedding_service
from src.core.config import settings


class TestLLMIntegration:
    """Test LLM service integration."""
    
    @pytest.mark.asyncio
    async def test_llm_manager_initialization(self):
        """Test LLM manager can be initialized."""
        with patch('src.core.llm.settings') as mock_settings:
            mock_settings.openai_api_key = "test-openai-key"
            mock_settings.anthropic_api_key = "test-anthropic-key"
            
            with patch('src.core.llm.OpenAIClient') as mock_openai, \
                 patch('src.core.llm.AnthropicClient') as mock_anthropic:
                
                # Mock clients
                mock_openai_client = Mock()
                mock_anthropic_client = Mock()
                mock_openai_client.validate_api_key = AsyncMock(return_value=True)
                mock_anthropic_client.validate_api_key = AsyncMock(return_value=True)
                
                mock_openai.return_value = mock_openai_client
                mock_anthropic.return_value = mock_anthropic_client
                
                # Test initialization
                manager = await initialize_llm()
                
                assert manager is not None
                assert len(manager.clients) >= 1
    
    @pytest.mark.asyncio
    async def test_embedding_service_initialization(self):
        """Test embedding service can be initialized."""
        with patch('src.core.llm.initialize_llm') as mock_init:
            mock_manager = Mock()
            mock_init.return_value = mock_manager
            
            service = await get_embedding_service()
            
            assert service is not None
            assert service.llm_manager == mock_manager


class TestSystemHealth:
    """Test system health and connectivity."""
    
    @pytest.mark.asyncio
    async def test_configuration_validation(self):
        """Test configuration is properly set up."""
        # Check required configuration fields exist
        assert hasattr(settings, 'llm_provider')
        assert hasattr(settings, 'openai_api_key')
        assert hasattr(settings, 'anthropic_api_key')
        assert hasattr(settings, 'embedding_model')
        assert hasattr(settings, 'embedding_dimensions')
        
        # Check configuration values
        assert settings.embedding_dimensions == 1536
        assert settings.embedding_model == "text-embedding-3-small"
        assert settings.llm_provider in ["openai", "anthropic"]
    
    def test_required_dependencies_import(self):
        """Test that all required dependencies can be imported."""
        try:
            import httpx
            import numpy as np
            import asyncio
            from tenacity import retry
            from pydantic import BaseModel
            assert True  # All imports successful
        except ImportError as e:
            pytest.fail(f"Required dependency missing: {e}")


if __name__ == "__main__":
    pytest.main([__file__])