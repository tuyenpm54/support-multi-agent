"""
Tests for Vector Search Service

Tests vector similarity search functionality including:
- Semantic search with pgvector
- Confidence scoring
- Issue classification
- Database operations
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
import uuid

from src.core.vector_search import VectorSearchService, get_vector_search_service
from src.core.embeddings import EmbeddingService
from src.models.session import SearchResult, ClassificationResult


class TestVectorSearchService:
    """Test suite for VectorSearchService."""
    
    @pytest.fixture
    async def mock_embedding_service(self):
        """Create a mock embedding service."""
        mock_service = AsyncMock(spec=EmbeddingService)
        # Return a 1536-dimensional mock embedding
        mock_service.generate_embedding.return_value = [0.1] * 1536
        return mock_service
    
    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session."""
        mock_session = AsyncMock()
        # Mock query result
        mock_row = MagicMock()
        mock_row.issue_id = uuid.uuid4()
        mock_row.title = "Login Issue"
        mock_row.description = "User cannot login to the application"
        mock_row.category = "Authentication"
        mock_row.severity = "Medium"
        mock_row.symptoms = {"symptom": "Login failed"}
        mock_row.diagnostic_questions = ["What error do you see?"]
        mock_row.tools = ["check_user_permissions"]
        mock_row.similarity = 0.85
        mock_row.created_at = datetime.now()
        mock_row.updated_at = datetime.now()
        
        mock_result = AsyncMock()
        mock_result.fetchall.return_value = [mock_row]
        mock_session.execute.return_value = mock_result
        
        return mock_session
    
    @pytest.fixture
    def vector_search_service(self, mock_embedding_service):
        """Create a vector search service with mocked dependencies."""
        service = VectorSearchService()
        service.embedding_service = mock_embedding_service
        service.engine = MagicMock()
        service.session_factory = MagicMock()
        service.session_factory.return_value.__aenter__.return_value = mock_db_session
        return service
    
    @pytest.mark.asyncio
    async def test_initialize_service_success(self):
        """Test successful service initialization."""
        service = VectorSearchService()
        
        with patch('src.core.vector_search.get_embedding_service') as mock_get_embedding:
            with patch('src.core.vector_search.create_async_engine') as mock_engine:
                with patch('src.core.vector_search.sessionmaker') as mock_sessionmaker:
                    # Setup mocks
                    mock_embedding_service = AsyncMock()
                    mock_get_embedding.return_value = mock_embedding_service
                    
                    mock_engine_instance = MagicMock()
                    mock_engine.return_value = mock_engine_instance
                    
                    mock_session_factory = MagicMock()
                    mock_sessionmaker.return_value = mock_session_factory
                    
                    # Mock database connection test
                    mock_session = AsyncMock()
                    mock_session_factory.return_value.__aenter__.return_value = mock_session
                    mock_session.execute.side_effect = [
                        AsyncMock(fetchone=AsyncMock(return_value={"pgvector": True})),
                        AsyncMock(fetchone=AsyncMock(return_value={"embedding": "vector"}))
                    ]
                    
                    await service.initialize()
                    
                    assert service.embedding_service is not None
                    assert service.engine is not None
                    assert service.session_factory is not None
    
    @pytest.mark.asyncio
    async def test_search_similar_issues(self, vector_search_service, mock_embedding_service):
        """Test searching for similar issues."""
        query_text = "User cannot login to the application"
        
        # Mock database session
        mock_session = AsyncMock()
        vector_search_service.session_factory.return_value.__aenter__.return_value = mock_session
        
        # Mock search results
        mock_row = MagicMock()
        mock_row.issue_id = uuid.uuid4()
        mock_row.title = "Login Issue"
        mock_row.description = "User cannot login due to authentication problems"
        mock_row.category = "Authentication"
        mock_row.severity = "Medium"
        mock_row.symptoms = {"symptom": "Login failed"}
        mock_row.diagnostic_questions = ["What error do you see?"]
        mock_row.tools = ["check_user_permissions"]
        mock_row.similarity = 0.85
        mock_row.created_at = datetime.now()
        mock_row.updated_at = datetime.now()
        
        mock_result = AsyncMock()
        mock_result.fetchall.return_value = [mock_row]
        mock_session.execute.return_value = mock_result
        
        results = await vector_search_service.search_similar_issues(query_text)
        
        assert len(results) == 1
        assert isinstance(results[0], SearchResult)
        assert results[0].title == "Login Issue"
        assert results[0].category == "Authentication"
        assert results[0].similarity_score == 0.85
        assert results[0].confidence_score > 0
        
        # Verify embedding was generated
        mock_embedding_service.generate_embedding.assert_called_once_with(query_text)
    
    @pytest.mark.asyncio
    async def test_search_with_filters(self, vector_search_service):
        """Test searching with category and severity filters."""
        query_text = "Performance issues"
        category_filter = ["Performance"]
        severity_filter = ["High", "Critical"]
        
        mock_session = AsyncMock()
        vector_search_service.session_factory.return_value.__aenter__.return_value = mock_session
        mock_session.execute.return_value.fetchall.return_value = []
        
        results = await vector_search_service.search_similar_issues(
            query_text=query_text,
            category_filter=category_filter,
            severity_filter=severity_filter
        )
        
        assert isinstance(results, list)
        # Verify filters were passed to the query
        mock_session.execute.assert_called_once()
        call_args = mock_session.execute.call_args
        assert "categories" in call_args[0][1]
        assert "severities" in call_args[0][1]
    
    @pytest.mark.asyncio
    async def test_classify_issue_high_confidence(self, vector_search_service):
        """Test issue classification with high confidence match."""
        query_text = "I cannot login to my account"
        
        mock_session = AsyncMock()
        vector_search_service.session_factory.return_value.__aenter__.return_value = mock_session
        
        # Mock high-confidence search result
        mock_row = MagicMock()
        mock_row.issue_id = uuid.uuid4()
        mock_row.title = "Authentication Failure"
        mock_row.description = "User cannot login due to invalid credentials"
        mock_row.category = "Authentication"
        mock_row.severity = "Medium"
        mock_row.symptoms = {"error": "Invalid credentials"}
        mock_row.diagnostic_questions = ["What error message do you see?"]
        mock_row.tools = ["check_user_permissions"]
        mock_row.similarity = 0.92
        mock_row.created_at = datetime.now()
        mock_row.updated_at = datetime.now()
        
        mock_result = AsyncMock()
        mock_result.fetchall.return_value = [mock_row]
        mock_session.execute.return_value = mock_result
        
        result = await vector_search_service.classify_issue(query_text, min_confidence=0.8)
        
        assert isinstance(result, ClassificationResult)
        assert result.classified == True
        assert result.confidence >= 0.8
        assert result.suggested_category == "Authentication"
        assert result.suggested_severity == "Medium"
        assert result.matched_issue_id is not None
        assert result.diagnostic_questions is not None
    
    @pytest.mark.asyncio
    async def test_classify_issue_low_confidence(self, vector_search_service):
        """Test issue classification with low confidence - should not classify."""
        query_text = "Something is not working properly"
        
        mock_session = AsyncMock()
        vector_search_service.session_factory.return_value.__aenter__.return_value = mock_session
        mock_session.execute.return_value.fetchall.return_value = []
        
        result = await vector_search_service.classify_issue(query_text, min_confidence=0.8)
        
        assert isinstance(result, ClassificationResult)
        assert result.classified == False
        assert result.confidence == 0.0
        assert result.suggested_category == "Unknown"
        assert result.matched_issue_id is None
    
    def test_calculate_confidence_score(self, vector_search_service):
        """Test confidence score calculation."""
        similarity = 0.85
        recency = datetime.now()
        severity = "High"
        
        confidence = vector_search_service._calculate_confidence_score(
            similarity, recency, severity
        )
        
        assert 0 <= confidence <= 1
        assert confidence > similarity  # Should be boosted by recency and severity
        
        # Test with old issue
        old_recency = datetime(2020, 1, 1)
        old_confidence = vector_search_service._calculate_confidence_score(
            similarity, old_recency, severity
        )
        assert old_confidence < confidence  # Old issues should have lower confidence
    
    def test_get_recommended_tools(self, vector_search_service):
        """Test getting recommended tools by category."""
        auth_tools = vector_search_service._get_recommended_tools("Authentication")
        assert "check_user_permissions" in auth_tools
        assert "query_database" in auth_tools
        
        perf_tools = vector_search_service._get_recommended_tools("Performance")
        assert "run_diagnostics" in perf_tools
        assert "check_system_status" in perf_tools
        
        unknown_tools = vector_search_service._get_recommended_tools("Unknown")
        assert "search_knowledge_base" in unknown_tools
        assert "query_database" in unknown_tools
    
    @pytest.mark.asyncio
    async def test_add_issue_to_database(self, vector_search_service):
        """Test adding a new issue to the database."""
        mock_session = AsyncMock()
        vector_search_service.session_factory.return_value.__aenter__.return_value = mock_session
        
        # Mock the insert result
        mock_result = AsyncMock()
        test_uuid = uuid.uuid4()
        mock_result.scalar.return_value = test_uuid
        mock_session.execute.return_value = mock_result
        
        issue_id = await vector_search_service.add_issue_to_database(
            title="New Issue",
            description="This is a new issue description",
            category="General",
            severity="Medium",
            symptoms={"test": "symptom"}
        )
        
        assert issue_id == str(test_uuid)
        mock_session.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_issue_embedding(self, vector_search_service):
        """Test updating embedding for existing issue."""
        mock_session = AsyncMock()
        vector_search_service.session_factory.return_value.__aenter__.return_value = mock_session
        
        # Mock update result
        mock_result = AsyncMock()
        mock_result.rowcount = 1
        mock_session.execute.return_value = mock_result
        
        success = await vector_search_service.update_issue_embedding(
            issue_id="test-issue-id",
            description="Updated description"
        )
        
        assert success == True
        mock_session.commit.assert_called_once()
    
    def test_get_search_metrics(self, vector_search_service):
        """Test getting search performance metrics."""
        # Add some test metrics
        vector_search_service.total_searches = 10
        vector_search_service.search_times = [0.1, 0.2, 0.15, 0.12]
        vector_search_service.average_similarity_scores = [0.8, 0.75, 0.82, 0.79]
        
        metrics = vector_search_service.get_search_metrics()
        
        assert metrics["total_searches"] == 10
        assert metrics["average_search_time_seconds"] == sum([0.1, 0.2, 0.15, 0.12]) / 4
        assert metrics["average_similarity_score"] == sum([0.8, 0.75, 0.82, 0.79]) / 4
        assert metrics["embedding_dimensions"] == 1536
        assert "default_similarity_threshold" in metrics
        assert "default_max_results" in metrics
    
    @pytest.mark.asyncio
    async def test_database_connection_failure(self):
        """Test handling of database connection failures."""
        service = VectorSearchService()
        
        with patch('src.core.vector_search.get_embedding_service') as mock_get_embedding:
            mock_embedding_service = AsyncMock()
            mock_get_embedding.return_value = mock_embedding_service
            
            with patch('src.core.vector_search.create_async_engine') as mock_engine:
                # Mock database failure
                mock_engine.side_effect = Exception("Database connection failed")
                
                with pytest.raises(Exception, match="Database connection failed"):
                    await service.initialize()
    
    @pytest.mark.asyncio
    async def test_embedding_service_failure(self):
        """Test handling of embedding service failures."""
        service = VectorSearchService()
        service.embedding_service = AsyncMock()
        service.embedding_service.generate_embedding.side_effect = Exception("Embedding failed")
        
        with pytest.raises(Exception, match="Embedding failed"):
            await service.search_similar_issues("test query")
    
    @pytest.mark.asyncio
    async def test_global_service_functions(self):
        """Test global service functions."""
        with patch('src.core.vector_search.vector_search_service') as mock_service:
            mock_service.engine = None
            mock_service.initialize = AsyncMock()
            
            service = await get_vector_search_service()
            mock_service.initialize.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_initialization_function(self):
        """Test the initialization function."""
        with patch('src.core.vector_search.vector_search_service') as mock_service:
            mock_service.initialize = AsyncMock()
            
            result = await initialize_vector_search()
            assert result is not None
            mock_service.initialize.assert_called_once()


# Integration tests
class TestVectorSearchIntegration:
    """Integration tests for vector search service."""
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_end_to_end_search_workflow(self):
        """Test the complete search workflow with real dependencies."""
        # This would test with real database and embedding service
        # Skip for now as it requires setup
        pytest.skip("Integration test requires database setup")
    
    @pytest.mark.asyncio 
    @pytest.mark.integration
    async def test_performance_under_load(self):
        """Test search performance under concurrent load."""
        # Load testing with multiple concurrent searches
        pytest.skip("Performance test requires database setup")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])