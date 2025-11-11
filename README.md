# Multi-Agent Customer Support System

A scalable AI-powered customer support system using multi-agent architecture to handle domain-specific issues without requiring domain knowledge from LLMs.

## Architecture Overview

The system consists of:
- **Orchestrator Agent**: Central coordinator managing workflow and state
- **Classifier Agent**: Semantic search and issue pattern matching
- **Required Info Agent**: Information gathering and entity resolution
- **Validate Agent**: Issue verification through tool execution
- **Fix Agent**: Automated issue resolution with rollback capability

## Quick Start

1. **Setup Environment**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys and configuration
   ```

2. **Install Dependencies**
   ```bash
   make install
   ```

3. **Initialize Database**
   ```bash
   make init-db
   ```

4. **Run Development Server**
   ```bash
   make dev
   ```

## Project Structure

```
support-multi-agent/
├── src/                          # Source code
│   ├── agents/                  # Agent implementations
│   │   ├── __init__.py
│   │   ├── base.py              # Base agent interface
│   │   ├── orchestrator.py      # Central orchestrator
│   │   ├── classifier.py        # Issue classification
│   │   ├── required_info.py     # Information gathering
│   │   ├── validate.py          # Issue validation
│   │   └── fix.py               # Issue fixing
│   ├── api/                     # REST API and WebSocket
│   │   ├── __init__.py
│   │   ├── app.py               # FastAPI application
│   │   ├── auth.py              # Authentication middleware
│   │   ├── routes/              # API endpoints
│   │   └── websocket.py         # WebSocket handlers
│   ├── core/                    # Core functionality
│   │   ├── __init__.py
│   │   ├── config.py            # Configuration management
│   │   ├── database.py          # Database connections
│   │   ├── cache.py             # Redis caching
│   │   ├── llm.py               # LLM client interface
│   │   ├── state_manager.py     # Session state management
│   │   └── tools.py             # Tool execution engine
│   ├── models/                  # Data models
│   │   ├── __init__.py
│   │   ├── session.py           # Session state model
│   │   ├── issue.py             # Issue pattern model
│   │   ├── conversation.py      # Conversation model
│   │   └── tool_registry.py     # Tool registry model
│   ├── tools/                   # Domain-specific tools
│   │   ├── __init__.py
│   │   ├── base_tool.py         # Base tool interface
│   │   ├── lookup_tools.py      # Lookup tools
│   │   ├── check_tools.py       # Validation tools
│   │   └── fix_tools.py         # Fix tools
│   └── utils/                   # Utilities
│       ├── __init__.py
│       ├── logging.py           # Structured logging
│       ├── monitoring.py        # Metrics collection
│       └── encryption.py        # Data encryption
├── tests/                       # Test suite
│   ├── unit/                    # Unit tests
│   ├── integration/             # Integration tests
│   └── e2e/                     # End-to-end tests
├── deployment/                  # Deployment configurations
│   ├── docker/                  # Docker configurations
│   ├── k8s/                     # Kubernetes manifests
│   └── terraform/               # Infrastructure as code
├── scripts/                     # Utility scripts
├── docs/                        # Documentation
└── Makefile                     # Development commands
```

## Development

### Running Tests
```bash
make test                    # Run all tests
make test-unit              # Run unit tests only
make test-integration       # Run integration tests
```

### Code Quality
```bash
make lint                   # Run linting
make format                 # Format code
make type-check            # Type checking
```

### Database Operations
```bash
make init-db               # Initialize database with schema
make migrate-db            # Run database migrations
make seed-db               # Seed database with sample data
make reset-db              # Reset database (dev only)
```

## Configuration

Key environment variables (see `.env.example`):

```bash
# Database
DATABASE_URL=postgresql://localhost:5432/support_system
REDIS_URL=redis://localhost:6379

# LLM Configuration
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=your_api_key
OPENAI_API_KEY=your_openai_key

# Security
JWT_SECRET=your_jwt_secret
ENCRYPTION_KEY=your_encryption_key

# Monitoring
JAEGER_ENDPOINT=http://localhost:14268
PROMETHEUS_ENDPOINT=http://localhost:9090
```

## API Documentation

Once running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **WebSocket**: ws://localhost:8000/ws

## Architecture Details

See `/docs/architecture.md` for comprehensive technical documentation.

## License

MIT License - see LICENSE file for details.