# Multi-Agent Support System Database Architecture

## Overview
The system uses a clean, focused database architecture where **active issues are managed in Redis sessions** and the **PostgreSQL issues table serves as the knowledge base for semantic search/classification**.

## Core Tables

### 1. `issues` - Knowledge Base for Classifier
**Purpose**: Semantic search and issue classification with vector embeddings
**Usage**: Used by Classifier Agent to find similar known issues

**Key Columns**:
- `embedding` - Vector (1536 dimensions) for semantic similarity search
- `title`, `description` - Issue details
- `category`, `severity` - Classification metadata
- `keywords` - Text array for keyword matching
- `diagnostic_questions` - Structured troubleshooting questions
- `tools` - Required tools/solutions
- `embedding_text` - Text used for generating embeddings

**Current Data**: 27 issues including:
- Vietnamese cost price troubleshooting problems (12 atomic + 10 solutions)
- General system issues (5 legacy records)

### 2. Supporting Tables

#### `conversation_archive`
- Stores complete conversation history for analysis and learning
- Enables post-resolution analysis and improvement

#### `session_manager` (Redis-based)
- **Active conversation state** (not in PostgreSQL!)
- Current user problems being solved
- Agent coordination state
- Timeline events and progress tracking

#### `tool_registry`
- Available tools for agents
- Categories: database, auth, system, external, workflow, monitoring
- Tool configuration and permissions

## Data Flow Architecture

```
Customer Input
    ↓
Classifier Agent
    ↓
Issues Knowledge Base (semantic search) ← PostgreSQL issues table
    ↓
Similar Issues Found (Vector similarity + keyword matching)
    ↓
Session Context Created ← Redis (SessionManager)
    ↓
Multi-Agent Coordination (RequiredInfo → Validate → Fix agents)
    ↓
Resolution & Learning
```

## Search Capabilities

### Hybrid Search Function
```sql
search_issues_hybrid(
    query_text,
    query_embedding (optional),
    min_similarity,
    limit_count,
    category_filter
)
```

**Features**:
- **Vector Search**: When embedding provided, uses cosine similarity
- **Keyword Fallback**: When no embedding, uses text matching
- **Category Filtering**: Can filter by issue categories
- **Confidence Scoring**: Returns similarity and confidence metrics

## Session Management Pattern

**Correct Pattern**:
```python
# Active issue tracked in session
session = await session_manager.get_session(session_id)
session.current_problem = {
    "title": "Customer's current issue",
    "category": "detected_category", 
    "agent_results": {...}
}
```

**Incorrect Pattern** (removed):
```sql
-- NO separate active_issues table needed
INSERT INTO active_issues (...)  -- Redundant!
```

## Benefits of This Architecture

1. **Performance**: Semantic search optimized in PostgreSQL with pgvector
2. **Scalability**: Redis handles session state with TTL and auto-cleanup
3. **Separation of Concerns**: 
   - Knowledge base (persistent, indexed, searchable)
   - Active sessions (temporary, Redis-based, performant)
4. **Clean Data Model**: No redundant tables or sync issues
5. **Multi-language Support**: Vietnamese content fully indexed and searchable

## Key Functions

### Semantic Search
- `search_similar_issues_vector()` - Pure vector similarity
- `search_issues_hybrid()` - Vector + keyword hybrid search

### Session Management
- `SessionManager.update_session()` - Redis-based state
- `SessionManager.add_timeline_event()` - Audit trail
- `SessionManager.add_conversation_message()` - Chat history

This architecture ensures **fast semantic classification** while keeping **active conversation state** properly separated and performant.