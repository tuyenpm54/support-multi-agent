# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Task Management Workflow

ALWAYS follow this workflow when performing tasks:

1. **Check tasks.md first** - Review current task status before starting any work
2. **Check plan.md** - Understand strategic context when unsure what to do
3. **Update task.md** - Add new tasks with "🚧 In Progress" status before starting implementation
4. **Commit changes** - Commit each completed task with clear commit message
5. **Update task.md** - Change task status to "✅ Completed" with completion date

## Development Commands

### Environment Setup
```bash
make install          # Install all dependencies and pre-commit hooks
```

### Development Server
```bash
make dev              # Start FastAPI development server (http://localhost:8000)
```

### Database Operations
```bash
make init-db          # Initialize database with schema and sample data
make reset-db         # Drop/recreate database (dev only)
make migrate-db       # Run database migrations
```

### Testing
```bash
make test             # Run all tests
make test-unit        # Run unit tests only
make test-integration # Run integration tests only
pytest tests/test_orchestrator.py  # Run specific test file
```

### Code Quality
```bash
make lint             # Run linting (flake8, mypy, black check, isort check)
make format           # Format code (black, isort)
make type-check       # Run type checking (mypy)
```

### Cleanup
```bash
make clean            # Remove Python cache files and build artifacts
```

## Core Architecture

### Multi-Agent System Flow
The system implements a state machine workflow: `CLASSIFY → REQUIRED_INFO → VALIDATE → FIX → COMPLETE/ESCALATE`

### Key Components

#### OrchestratorAgent (`src/agents/orchestrator.py`)
- Central coordinator managing the entire workflow
- Maintains agent registry and executes phase transitions
- Integrates with CoordinationManager for event-driven coordination
- Handles error recovery, retry logic, and escalation

#### CoordinationFlow (`src/core/coordination.py`)
- Event-driven coordination system with configurable rules
- Manages workflow metrics and session lifecycle
- Implements timeout handling and performance monitoring
- Rules can trigger phase transitions based on events and conditions

#### SessionManager (`src/core/state_manager.py`)
- Redis-based session state persistence with local caching
- Manages conversation history and timeline events
- Handles session CRUD operations with automatic cleanup
- 5-minute local cache TTL for performance

#### State Models (`src/models/session.py`)
- Pydantic-based models for type safety and validation
- SessionState tracks current phase and agent results
- TimelineEvent captures workflow actions with duration tracking
- Agent-specific result models (ClassificationResult, ValidationResult, etc.)

### API Architecture

#### FastAPI Application (`src/api/app.py`)
- Main application with WebSocket support for real-time communication
- Includes health checks, metrics endpoints, and error handling
- Integrates with orchestrator for session management

#### Router Structure (`src/api/routers/`)
- `sessions.py`: Session CRUD operations and timeline access
- `conversations.py`: Message handling and conversation status
- `agents.py`: Agent status and workflow metrics

### Database Schema

#### Issues Table
- Stores known issues with pgvector embeddings for semantic search
- Includes symptoms, diagnostic questions, and tool requirements
- Vector similarity search via `search_similar_issues()` function

#### Tool Registry
- Available tools for agents with configuration and permissions
- Categories: database, auth, system, external, workflow, monitoring

#### Session Data
- Conversation archive for historical analysis and learning
- Rollback tokens for safe operation recovery
- Complete audit trail via timeline events

## Development Patterns

### Adding New Agents
1. Extend `BaseAgent` from `src/agents/base.py`
2. Implement `execute()` method returning agent results
3. Register in orchestrator: `orchestrator.register_agent(AgentPhase.PHASE, agent)`
4. Add state transition logic in orchestrator's `state_transitions`
5. Add tests in `tests/` directory

### Coordination Rules
Add custom coordination rules via `CoordinationRule`:
```python
rule = CoordinationRule(
    trigger_event=CoordinationEvent.AGENT_COMPLETE,
    source_phase=AgentPhase.CLASSIFY,
    condition=lambda data: data.get("confidence", 0) > 0.9,
    target_phase=AgentPhase.VALIDATE,
    priority=8
)
orchestrator.coordination_manager.add_coordination_rule(rule)
```

### Session State Management
- Use `session_manager.update_session(session_id, updates)` for state changes
- Add timeline events for audit: `session_manager.add_timeline_event()`
- Store conversation messages: `session_manager.add_conversation_message()`

### Error Handling
- Return error details in agent result dictionaries
- Use orchestrator's retry logic for transient failures
- Escalate to human when retry limits exceeded
- Log errors with appropriate levels and context

## Performance Considerations

### Caching Strategy
- Session states cached locally for 5 minutes
- Redis handles persistent storage and cross-process sharing
- Cache invalidated on session updates

### Async Operations
- All I/O operations use async/await patterns
- Parallel processing for independent operations
- Connection pooling for database and Redis connections

### Vector Search
- pgvector for semantic similarity matching
- IVFFlat index for performance
- 1536-dimensional embeddings (OpenAI default)

## Configuration

Key environment variables in `.env`:
- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string  
- `ANTHROPIC_API_KEY`: LLM integration
- `SESSION_TTL`: Session expiration (default: 3600s)
- `CLASSIFIER_CONFIDENCE_THRESHOLD`: Classification minimum confidence

## Project Structure Notes

- Tests organized by type: `tests/unit/`, `tests/integration/`
- Database migrations in `migrations/` with numeric prefixes
- Utility scripts in `scripts/` for database operations
- Documentation in `document/` includes PRD, architecture, planning, and tasks
- Development configuration in `.env.example` template

## Phase Status

- **Phase 1**: Foundation & Framework - ✅ COMPLETED
- **Phase 2**: Core Agent Implementation - 🚧 READY TO START
- **Phase 3**: Advanced Features & Optimization - 🔜 PLANNED
- **Phase 4**: Production Readiness & Scaling - 🔜 PLANNED

Current focus should be on implementing the four specialized agents (Classifier, RequiredInfo, Validate, Fix) according to the plan.md specifications.