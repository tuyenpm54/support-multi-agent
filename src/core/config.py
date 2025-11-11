from pydantic_settings import BaseSettings
from typing import List, Optional
import os


class Settings(BaseSettings):
    # Application
    environment: str = "development"
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8000
    
    # API
    api_v1_str: str = "/api/v1"
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:8000"]
    
    # Database
    database_url: str = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/support_system")
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    # LLM Configuration
    llm_provider: str = "anthropic"
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    
    # Security
    jwt_secret: str = os.getenv("JWT_SECRET", "your_super_secret_jwt_key_minimum_32_characters")
    encryption_key: str = os.getenv("ENCRYPTION_KEY", "your_encryption_key_32_characters_long")
    
    # Monitoring
    jaeger_endpoint: str = os.getenv("JAEGER_ENDPOINT", "http://localhost:14268")
    prometheus_endpoint: str = os.getenv("PROMETHEUS_ENDPOINT", "http://localhost:9090")
    log_level: str = "INFO"
    
    # Agent Configuration
    classifier_confidence_threshold: float = 0.75
    max_classification_candidates: int = 5
    validation_max_tools: int = 5
    fix_max_tools: int = 5
    max_conversation_turns: int = 3
    
    # Rate Limiting
    rate_limit_requests: int = 100
    rate_limit_window: int = 60
    
    # Session Management
    session_ttl: int = 3600  # 1 hour
    max_concurrent_sessions: int = 1000
    
    # Tool Configuration
    tool_timeout_seconds: int = 30
    tool_retry_count: int = 3
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()