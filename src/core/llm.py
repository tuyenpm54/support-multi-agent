"""
LLM Client Integration Module

Provides unified interface for multiple LLM providers (OpenAI, Anthropic)
with fallback mechanisms and retry logic.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from enum import Enum
import httpx

# Make tenacity optional
try:
    from tenacity import retry, stop_after_attempt, wait_exponential
    HAS_TENACITY = True
except ImportError:
    HAS_TENACITY = False
    
    # Fallback retry decorator
    def retry(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    
    def stop_after_attempt(n):
        return n
    
    def wait_exponential(*args, **kwargs):
        return 1

# Use simple config to avoid Pydantic dependency
try:
    from src.core.config import settings
except ImportError:
    from src.core.simple_config import settings


class LLMProvider(Enum):
    """Supported LLM providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class LLMResponse:
    """Standardized LLM response format."""
    
    def __init__(self, content: str, provider: LLMProvider, metadata: Dict[str, Any] = None):
        self.content = content
        self.provider = provider
        self.metadata = metadata or {}
        self.tokens_used = metadata.get("tokens_used", 0) if metadata else 0
        self.model = metadata.get("model", "unknown")


class BaseLLMClient(ABC):
    """Abstract base class for LLM clients."""
    
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model
        self.logger = logging.getLogger(__name__)
    
    @abstractmethod
    async def generate_text(self, prompt: str, **kwargs) -> LLMResponse:
        """Generate text completion."""
        pass
    
    @abstractmethod
    async def generate_embedding(self, text: str) -> List[float]:
        """Generate text embedding."""
        pass
    
    @abstractmethod
    async def validate_api_key(self) -> bool:
        """Validate API key is working."""
        pass


class OpenAIClient(BaseLLMClient):
    """OpenAI API client."""
    
    def __init__(self, api_key: str, model: str = None, embedding_model: str = None):
        super().__init__(api_key, model or settings.openai_model)
        self.embedding_model = embedding_model or settings.embedding_model
        self.base_url = "https://api.openai.com/v1"
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=60.0
        )
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def generate_text(self, prompt: str, **kwargs) -> LLMResponse:
        """Generate text completion using OpenAI."""
        try:
            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": kwargs.get("max_tokens", 1000),
                "temperature": kwargs.get("temperature", 0.3),
                "top_p": kwargs.get("top_p", 1.0),
                "frequency_penalty": kwargs.get("frequency_penalty", 0.0),
                "presence_penalty": kwargs.get("presence_penalty", 0.0)
            }
            
            print(f"🔥 OPENAI API CALL: {self.base_url}/chat/completions")
            print(f"🔥 Model: {self.model}")
            print(f"🔥 API Key starts with: {self.api_key[:10]}...")
            response = await self.client.post("/chat/completions", json=payload)
            print(f"🔥 Response status: {response.status_code}")
            response.raise_for_status()
            
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            tokens_used = data["usage"]["total_tokens"]
            print(f"🔥 Tokens used: {tokens_used} (prompt: {data['usage']['prompt_tokens']}, completion: {data['usage']['completion_tokens']})")
            
            return LLMResponse(
                content=content,
                provider=LLMProvider.OPENAI,
                metadata={
                    "model": self.model,
                    "tokens_used": tokens_used,
                    "prompt_tokens": data["usage"]["prompt_tokens"],
                    "completion_tokens": data["usage"]["completion_tokens"]
                }
            )
            
        except Exception as e:
            self.logger.error(f"OpenAI text generation error: {str(e)}")
            raise
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding using OpenAI."""
        try:
            payload = {
                "model": self.embedding_model,
                "input": text
            }
            
            response = await self.client.post("/embeddings", json=payload)
            response.raise_for_status()
            
            data = response.json()
            embedding = data["data"][0]["embedding"]
            tokens_used = data["usage"]["total_tokens"]
            
            self.logger.debug(f"Generated embedding with {len(embedding)} dimensions, tokens: {tokens_used}")
            return embedding
            
        except Exception as e:
            self.logger.error(f"OpenAI embedding generation error: {str(e)}")
            raise
    
    async def validate_api_key(self) -> bool:
        """Validate OpenAI API key."""
        try:
            response = await self.client.get("/models")
            return response.status_code == 200
        except Exception:
            return False
    
    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()


class AnthropicClient(BaseLLMClient):
    """Anthropic API client."""
    
    def __init__(self, api_key: str, model: str = None):
        super().__init__(api_key, model or settings.anthropic_model)
        self.base_url = "https://api.anthropic.com/v1"
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            timeout=60.0
        )
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def generate_text(self, prompt: str, **kwargs) -> LLMResponse:
        """Generate text completion using Anthropic."""
        try:
            payload = {
                "model": self.model,
                "max_tokens": kwargs.get("max_tokens", 1000),
                "messages": [{"role": "user", "content": prompt}],
                "temperature": kwargs.get("temperature", 0.7),
                "top_p": kwargs.get("top_p", 1.0),
                "top_k": kwargs.get("top_k", -1)
            }
            
            response = await self.client.post("/messages", json=payload)
            response.raise_for_status()
            
            data = response.json()
            content = data["content"][0]["text"]
            tokens_used = data["usage"]["input_tokens"] + data["usage"]["output_tokens"]
            
            return LLMResponse(
                content=content,
                provider=LLMProvider.ANTHROPIC,
                metadata={
                    "model": self.model,
                    "tokens_used": tokens_used,
                    "input_tokens": data["usage"]["input_tokens"],
                    "output_tokens": data["usage"]["output_tokens"]
                }
            )
            
        except Exception as e:
            self.logger.error(f"Anthropic text generation error: {str(e)}")
            raise
    
    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding using Anthropic.
        
        Note: Anthropic doesn't provide embedding API, so we fallback to OpenAI.
        """
        raise NotImplementedError("Anthropic doesn't provide embedding API. Use OpenAI for embeddings.")
    
    async def validate_api_key(self) -> bool:
        """Validate Anthropic API key."""
        try:
            # Simple test with minimal request
            payload = {
                "model": self.model,
                "max_tokens": 10,
                "messages": [{"role": "user", "content": "test"}]
            }
            response = await self.client.post("/messages", json=payload)
            return response.status_code == 200
        except Exception:
            return False
    
    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()


class LLMManager:
    """Unified LLM manager with fallback and load balancing."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.clients: Dict[LLMProvider, BaseLLMClient] = {}
        self.primary_provider = LLMProvider.OPENAI
        self.fallback_provider = LLMProvider.ANTHROPIC
        self.embedding_provider = LLMProvider.OPENAI  # Only OpenAI supports embeddings
        self._initialize_clients()
    
    def _initialize_clients(self):
        """Initialize LLM clients based on configuration."""
        # Initialize OpenAI client
        if settings.openai_api_key:
            try:
                self.clients[LLMProvider.OPENAI] = OpenAIClient(
                    api_key=settings.openai_api_key,
                    model=settings.openai_model,
                    embedding_model=settings.embedding_model
                )
                self.logger.info("OpenAI client initialized")
            except Exception as e:
                self.logger.error(f"Failed to initialize OpenAI client: {str(e)}")
        
        # Initialize Anthropic client
        if settings.anthropic_api_key:
            try:
                self.clients[LLMProvider.ANTHROPIC] = AnthropicClient(
                    api_key=settings.anthropic_api_key,
                    model=settings.anthropic_model
                )
                self.logger.info("Anthropic client initialized")
            except Exception as e:
                self.logger.error(f"Failed to initialize Anthropic client: {str(e)}")
    
    async def generate_text(self, prompt: str, **kwargs) -> LLMResponse:
        """Generate text with fallback support."""
        providers_to_try = [self.primary_provider]
        if self.fallback_provider != self.primary_provider:
            providers_to_try.append(self.fallback_provider)
        
        last_error = None
        
        for provider in providers_to_try:
            if provider not in self.clients:
                self.logger.warning(f"Provider {provider.value} not available")
                continue
            
            try:
                client = self.clients[provider]
                response = await client.generate_text(prompt, **kwargs)
                self.logger.debug(f"Text generated using {provider.value}")
                return response
                
            except Exception as e:
                last_error = e
                self.logger.warning(f"Failed to generate text with {provider.value}: {str(e)}")
                continue
        
        self.logger.error("All LLM providers failed for text generation")
        raise last_error or Exception("No LLM providers available")
    
    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding using the configured provider."""
        provider = self.embedding_provider
        
        if provider not in self.clients:
            raise Exception(f"Embedding provider {provider.value} not available")
        
        try:
            client = self.clients[provider]
            embedding = await client.generate_embedding(text)
            self.logger.debug(f"Embedding generated using {provider.value}")
            return embedding
            
        except Exception as e:
            self.logger.error(f"Failed to generate embedding with {provider.value}: {str(e)}")
            raise
    
    async def validate_all_clients(self) -> Dict[LLMProvider, bool]:
        """Validate all configured clients."""
        results = {}
        
        for provider, client in self.clients.items():
            try:
                is_valid = await client.validate_api_key()
                results[provider] = is_valid
                self.logger.info(f"Provider {provider.value} validation: {'✓' if is_valid else '✗'}")
            except Exception as e:
                results[provider] = False
                self.logger.error(f"Provider {provider.value} validation error: {str(e)}")
        
        return results
    
    def get_provider_status(self) -> Dict[str, Any]:
        """Get status of all providers."""
        return {
            "configured_providers": list(self.clients.keys()),
            "primary_provider": self.primary_provider.value,
            "fallback_provider": self.fallback_provider.value,
            "embedding_provider": self.embedding_provider.value,
            "available_clients": len(self.clients)
        }
    
    async def close_all(self):
        """Close all client connections."""
        for client in self.clients.values():
            if hasattr(client, 'close'):
                try:
                    await client.close()
                except Exception as e:
                    self.logger.error(f"Error closing client: {str(e)}")


# Global LLM manager instance
llm_manager = LLMManager()


async def get_llm_manager() -> LLMManager:
    """Get the global LLM manager instance."""
    return llm_manager


async def initialize_llm():
    """Initialize LLM manager and validate clients."""
    try:
        validation_results = await llm_manager.validate_all_clients()
        
        if not any(validation_results.values()):
            raise Exception("No valid LLM providers available")
        
        logger = logging.getLogger(__name__)
        logger.info(f"LLM manager initialized. Valid providers: {[p.value for p, v in validation_results.items() if v]}")
        
        return llm_manager
        
    except Exception as e:
        logging.getLogger(__name__).error(f"Failed to initialize LLM manager: {str(e)}")
        raise