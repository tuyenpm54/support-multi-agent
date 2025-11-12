"""
Simple Configuration Module - No external dependencies
"""

import os
from typing import Dict, Any, List, Optional


class SimpleSettings:
    """Simple settings class without Pydantic dependencies."""
    
    def __init__(self):
        # Database Configuration
        self.database_url = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/support_system")
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        
        # LLM Configuration
        self.llm_provider = os.getenv("LLM_PROVIDER", "anthropic")  # Default provider
        self.llm_fallback_provider = os.getenv("LLM_FALLBACK_PROVIDER", "openai")
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY", "")
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "")
        
        # Model Configuration
        self.openai_model = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
        self.anthropic_model = os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307")
        self.embedding_model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
        self.embedding_dimensions = int(os.getenv("EMBEDDING_DIMENSIONS", "1536"))
        
        # LLM Settings
        self.llm_temperature = 0.7
        self.llm_max_tokens = 1000
        self.llm_timeout_seconds = 60
        self.llm_retry_attempts = 3
        self.llm_retry_delay = 1.0
        
        # Embedding Settings
        self.embedding_cache_ttl = 3600  # 1 hour
        self.embedding_batch_size = 5
        self.embedding_similarity_threshold = 0.7
        
        # Security
        self.jwt_secret = os.getenv("JWT_SECRET", "your_super_secret_jwt_key_minimum_32_characters")
        self.encryption_key = os.getenv("ENCRYPTION_KEY", "your_encryption_key_32_characters_long")
        
        # Application Configuration
        self.environment = os.getenv("ENVIRONMENT", "development")
        self.debug = os.getenv("DEBUG", "true").lower() == "true"
        self.host = os.getenv("HOST", "0.0.0.0")
        self.port = int(os.getenv("PORT", "8000"))
        
        # API Configuration
        self.api_v1_str = os.getenv("API_V1_STR", "/api/v1")
        cors_origins_str = os.getenv("CORS_ORIGINS", '["http://localhost:3000", "http://localhost:8000"]')
        try:
            import ast
            self.cors_origins = ast.literal_eval(cors_origins_str)
        except:
            self.cors_origins = ["http://localhost:3000", "http://localhost:8000"]
        
        # Monitoring
        self.jaeger_endpoint = os.getenv("JAEGER_ENDPOINT", "http://localhost:14268")
        self.prometheus_endpoint = os.getenv("PROMETHEUS_ENDPOINT", "http://localhost:9090")
        self.log_level = os.getenv("LOG_LEVEL", "INFO")
        
        # Vector Database
        self.classifier_confidence_threshold = float(os.getenv("CLASSIFIER_CONFIDENCE_THRESHOLD", "0.75"))
        self.max_classification_candidates = int(os.getenv("MAX_CLASSIFICATION_CANDIDATES", "5"))
        self.validation_max_tools = int(os.getenv("VALIDATION_MAX_TOOLS", "5"))
        self.fix_max_tools = int(os.getenv("FIX_MAX_TOOLS", "5"))
        self.max_conversation_turns = int(os.getenv("MAX_CONVERSATION_TURNS", "3"))
        
        # Rate Limiting
        self.rate_limit_requests = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
        self.rate_limit_window = int(os.getenv("RATE_LIMIT_WINDOW", "60"))
        
        # Session Management
        self.session_ttl = int(os.getenv("SESSION_TTL", "3600"))
        self.max_concurrent_sessions = int(os.getenv("MAX_CONCURRENT_SESSIONS", "1000"))


# Global settings instance
settings = SimpleSettings()