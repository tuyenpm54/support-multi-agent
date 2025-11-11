# Development Guide

This guide provides instructions for setting up and developing the Multi-Agent Support System.

## Prerequisites

- Python 3.8+
- PostgreSQL 12+ with pgvector extension
- Redis 6+
- Node.js 16+ (for frontend development, optional)

## Quick Start

### 1. Environment Setup

```bash
# Clone the repository
git clone <repository-url>
cd support-multi-agent

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
make install
```

### 2. Environment Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your configuration
# Required:
# - DATABASE_URL: PostgreSQL connection string
# - REDIS_URL: Redis connection string
# - ANTHROPIC_API_KEY: For LLM integration
```

### 3. Database Setup

```bash
# Initialize database schema
make init-db

# Or run manually
python scripts/init_db.py
```

### 4. Start Development Server

```bash
# Start the API server
make dev

# Or manually
uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

### 5. Verify Installation

- Health check: `http://localhost:8000/health`
- API documentation: `http://localhost:8000/docs`
- Metrics: `http://localhost:8000/metrics`

## Development Workflow

### Project Structure

```
support-multi-agent/
├── src/
│   ├── agents/          # Agent implementations
│   ├── api/            # FastAPI application and routes
│   ├── core/           # Core services (config, state management, coordination)
│   └── models/         # Data models and schemas
├── tests/              # Test files
├── scripts/            # Utility scripts
├── migrations/         # Database migrations
└── document/           # Documentation (PRD, architecture)
```

### Adding New Agents

1. Create agent class in `src/agents/`:
```python
from src.agents.base import BaseAgent

class MyAgent(BaseAgent):
    def __init__(self):
        super().__init__("MyAgent")
    
    async def execute(self, session_state, **kwargs):
        # Agent implementation
        return {"success": True, "message": "Completed"}
```

2. Register agent in orchestrator:
```python
orchestrator.register_agent(AgentPhase.MY_PHASE, MyAgent())
```

3. Add tests in `tests/`

### Database Changes

1. Create migration file in `migrations/`
2. Update `scripts/init_db.py` if needed
3. Test changes: `make test-db`

### Running Tests

```bash
# Run all tests
make test

# Run specific test file
pytest tests/test_orchestrator.py

# Run with coverage
make test-coverage
```

## API Development

### Adding New Endpoints

1. Create router in `src/api/routers/`
2. Add to main app in `src/api/app.py`
3. Add Pydantic models for request/response
4. Add tests

### WebSocket Development

The system supports WebSocket connections for real-time communication:

- Endpoint: `ws://localhost:8000/ws/{session_id}`
- Message format: JSON with `message`, `type`, and optional `metadata`

## Key Components

### Orchestrator Agent

The central coordinator that manages the workflow:
- State machine implementation
- Agent coordination
- Error handling and retry logic
- Integration with coordination flow

### Session Management

Redis-based session state with local caching:
- Session CRUD operations
- Timeline event tracking
- Conversation history
- Automatic cleanup

### Coordination Flow

Rule-based coordination system:
- Configurable transition rules
- Event-driven architecture
- Performance metrics
- Timeout handling

### State Models

Pydantic-based data models:
- Type safety and validation
- JSON serialization
- Database ORM compatibility

## Configuration

### Environment Variables

Key configuration options in `.env`:

```bash
# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/support_db
REDIS_URL=redis://localhost:6379/0

# LLM Providers
ANTHROPIC_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here

# Application
DEBUG=true
LOG_LEVEL=INFO
HOST=0.0.0.0
PORT=8000

# Agent Configuration
CLASSIFIER_CONFIDENCE_THRESHOLD=0.75
MAX_CLASSIFICATION_CANDIDATES=5
VALIDATION_MAX_TOOLS=5
FIX_MAX_TOOLS=5
MAX_CONVERSATION_TURNS=3

# Session Management
SESSION_TTL=3600
MAX_CONCURRENT_SESSIONS=1000
```

### Logging

Configure logging levels and outputs:
- Python standard logging
- Structured JSON output (production)
- Debug mode with verbose output

## Performance Monitoring

### Metrics Available

- Phase transition times
- Agent success/failure rates
- Session throughput
- Error rates by phase
- Escalation frequency

### Monitoring Tools

- OpenTelemetry integration (planned)
- Prometheus metrics (configured)
- Custom dashboard endpoints

## Testing

### Test Categories

1. **Unit Tests**: Individual component testing
2. **Integration Tests**: Component interaction testing
3. **API Tests**: Endpoint testing
4. **Workflow Tests**: End-to-end workflow testing

### Mock Services

Use mocks for external dependencies:
- Database operations
- External APIs
- Agent implementations

## Deployment

### Docker Development

```bash
# Build development image
docker build -f Dockerfile.dev -t support-system:dev .

# Run with compose
docker-compose -f docker-compose.dev.yml up
```

### Production Deployment

1. Set production environment variables
2. Run database migrations
3. Configure monitoring and logging
4. Set up load balancing
5. Configure SSL/TLS

## Troubleshooting

### Common Issues

1. **Database Connection**: Check PostgreSQL and pgvector extension
2. **Redis Connection**: Verify Redis is running and accessible
3. **API Key Issues**: Validate ANTHROPIC_API_KEY in environment
4. **Port Conflicts**: Change PORT in configuration if needed

### Debug Mode

Enable debug mode for detailed logging:
```bash
DEBUG=true make dev
```

### Health Checks

Monitor system health:
- `/health` - Overall system status
- `/metrics` - Performance metrics
- Redis and PostgreSQL connectivity

## Contributing

1. Fork repository
2. Create feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit pull request

### Code Style

- Follow PEP 8
- Use type hints
- Add docstrings
- Keep functions focused and testable

## Architecture Decisions

### Technology Choices

- **FastAPI**: Modern async web framework with automatic documentation
- **Redis**: Fast session storage with built-in expiration
- **PostgreSQL + pgvector**: Vector similarity search for issue matching
- **Pydantic**: Data validation and serialization
- **AsyncIO**: Non-blocking I/O for scalability

### Design Patterns

- **State Machine**: Workflow management with clear state transitions
- **Agent Pattern**: Modular, specialized agents for different tasks
- **Event-Driven**: Coordination through events and rules
- **Repository Pattern**: Data access abstraction

## Next Steps

1. Implement specialized agents (Classifier, RequiredInfo, Validate, Fix)
2. Add LLM integration for natural language processing
3. Implement tool execution engine
4. Add comprehensive monitoring and alerting
5. Develop frontend interface
6. Add authentication and authorization
7. Implement knowledge extraction flow