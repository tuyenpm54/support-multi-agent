"""
Vector Similarity Search Service

Handles semantic search using pgvector with confidence scoring and ranking
for issue classification and matching.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from datetime import datetime
import asyncpg
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

from src.core.config import settings
from src.core.embeddings import get_embedding_service, EmbeddingService
from src.models.session import ClassificationResult, SearchResult


class VectorSearchService:
    """Service for vector similarity search using pgvector."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.embedding_service: Optional[EmbeddingService] = None
        self.engine = None
        self.session_factory = None
        self.embedding_dimensions = 1536  # OpenAI text-embedding-3-small
        
        # Search configuration
        self.default_similarity_threshold = 0.7
        self.default_max_results = 5
        self.confidence_scale_factor = 0.3  # Scale factor for confidence calculation
        
        # Performance metrics
        self.total_searches = 0
        self.search_times: List[float] = []
        self.average_similarity_scores: List[float] = []
    
    async def initialize(self):
        """Initialize the vector search service."""
        try:
            # Initialize embedding service
            self.embedding_service = await get_embedding_service()
            
            # Initialize database connection
            database_url = settings.database_url
            if not database_url:
                raise ValueError("DATABASE_URL not configured")
            
            # Create async engine
            self.engine = create_async_engine(
                database_url.replace("postgresql://", "postgresql+asyncpg://"),
                echo=False,
                pool_pre_ping=True,
                pool_recycle=3600
            )
            
            # Create session factory
            self.session_factory = sessionmaker(
                self.engine, class_=AsyncSession, expire_on_commit=False
            )
            
            # Test database connection and pgvector extension
            await self._test_database_connection()
            
            self.logger.info("Vector search service initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize vector search service: {str(e)}")
            raise
    
    async def _test_database_connection(self):
        """Test database connection and pgvector extension."""
        try:
            async with self.session_factory() as session:
                # Test pgvector extension
                result = await session.execute(text("SELECT * FROM pg_extension WHERE extname = 'pgvector'"))
                if not result.fetchone():
                    raise Exception("pgvector extension not found")
                
                # Test issues table exists
                result = await session.execute(text("""
                    SELECT column_name, data_type 
                    FROM information_schema.columns 
                    WHERE table_name = 'issues' AND column_name = 'embedding'
                """))
                if not result.fetchone():
                    raise Exception("issues table with embedding column not found")
                
                self.logger.info("Database connection and pgvector extension verified")
                
        except Exception as e:
            self.logger.error(f"Database connection test failed: {str(e)}")
            raise
    
    async def search_similar_issues(self, 
                                  query_text: str,
                                  similarity_threshold: Optional[float] = None,
                                  max_results: Optional[int] = None,
                                  category_filter: Optional[List[str]] = None,
                                  severity_filter: Optional[List[str]] = None) -> List[SearchResult]:
        """
        Search for similar issues using vector similarity.
        
        Args:
            query_text: Text to search for
            similarity_threshold: Minimum similarity threshold (0-1)
            max_results: Maximum number of results to return
            category_filter: Filter by issue categories
            severity_filter: Filter by issue severity levels
            
        Returns:
            List of search results with similarity scores and confidence
        """
        if not self.embedding_service:
            raise Exception("Vector search service not initialized")
        
        start_time = datetime.now()
        
        try:
            # Generate embedding for query text
            query_embedding = await self.embedding_service.generate_embedding(query_text)
            
            # Set defaults
            threshold = similarity_threshold or self.default_similarity_threshold
            limit = max_results or self.default_max_results
            
            # Prepare parameters
            params = {
                "embedding": query_embedding,
                "threshold": threshold,
                "limit": limit
            }
            
            if category_filter:
                params["categories"] = category_filter
            
            if severity_filter:
                params["severities"] = severity_filter
            
            # Execute search
            async with self.session_factory() as session:
                # Build the base query
                query_parts = [
                    """
                    SELECT 
                        issue_id,
                        title,
                        description,
                        category,
                        severity,
                        symptoms,
                        diagnostic_questions,
                        tools,
                        1 - (embedding <=> :embedding) as similarity,
                        created_at,
                        updated_at
                    FROM issues
                    WHERE 1 - (embedding <=> :embedding) > :threshold
                    """
                ]
                
                # Add filters
                if category_filter:
                    query_parts.append("AND category = ANY(:categories)")
                
                if severity_filter:
                    query_parts.append("AND severity = ANY(:severities)")
                
                query_parts.append("ORDER BY similarity DESC LIMIT :limit")
                
                final_query = text(" ".join(query_parts))
                
                result = await session.execute(final_query, params)
                rows = result.fetchall()
            
            # Process results and calculate confidence scores
            search_results = []
            for row in rows:
                # Calculate confidence based on similarity and other factors
                confidence = self._calculate_confidence_score(
                    similarity=row.similarity,
                    recency=row.created_at,
                    severity=row.severity
                )
                
                search_result = SearchResult(
                    issue_id=str(row.issue_id),
                    title=row.title,
                    description=row.description,
                    category=row.category,
                    severity=row.severity,
                    symptoms=row.symptoms,
                    diagnostic_questions=row.diagnostic_questions,
                    tools=row.tools,
                    similarity_score=float(row.similarity),
                    confidence_score=confidence,
                    created_at=row.created_at,
                    updated_at=row.updated_at
                )
                search_results.append(search_result)
            
            # Update metrics
            search_time = (datetime.now() - start_time).total_seconds()
            self.total_searches += 1
            self.search_times.append(search_time)
            
            if search_results:
                avg_similarity = sum(r.similarity_score for r in search_results) / len(search_results)
                self.average_similarity_scores.append(avg_similarity)
            
            self.logger.info(f"Found {len(search_results)} similar issues in {search_time:.3f}s")
            
            return search_results
            
        except Exception as e:
            self.logger.error(f"Vector search failed: {str(e)}")
            raise
    
    def _calculate_confidence_score(self, 
                                  similarity: float,
                                  recency: datetime,
                                  severity: str) -> float:
        """
        Calculate confidence score based on multiple factors.
        
        Args:
            similarity: Vector similarity score (0-1)
            recency: When the issue was created
            severity: Issue severity level
            
        Returns:
            Confidence score (0-1)
        """
        # Base confidence from similarity
        base_confidence = similarity
        
        # Recency boost (more recent issues get higher confidence)
        days_old = (datetime.now() - recency).days
        recency_boost = max(0, 1 - (days_old / 90))  # Decay over 90 days
        
        # Severity weighting
        severity_weights = {
            "Critical": 1.2,
            "High": 1.1,
            "Medium": 1.0,
            "Low": 0.9
        }
        severity_weight = severity_weights.get(severity, 1.0)
        
        # Calculate final confidence
        confidence = base_confidence * (1 + self.confidence_scale_factor * recency_boost) * severity_weight
        
        # Ensure confidence is in valid range [0, 1]
        confidence = min(1.0, max(0.0, confidence))
        
        return confidence
    
    async def classify_issue(self, 
                           query_text: str,
                           min_confidence: float = 0.6) -> ClassificationResult:
        """
        Classify an issue by finding the best match from known issues.
        
        Args:
            query_text: Issue description to classify
            min_confidence: Minimum confidence threshold for classification
            
        Returns:
            Classification result with best match and confidence
        """
        try:
            # Search for similar issues
            results = await self.search_similar_issues(
                query_text=query_text,
                similarity_threshold=0.3,  # Lower threshold for classification
                max_results=10
            )
            
            if not results:
                return ClassificationResult(
                    classified=False,
                    confidence=0.0,
                    suggested_category="Unknown",
                    suggested_severity="Medium",
                    matched_issue_id=None,
                    diagnostic_questions=["Please provide more details about your issue."],
                    potential_causes=[],
                    recommended_tools=[]
                )
            
            # Get the best match
            best_match = results[0]
            
            # Check if confidence meets threshold
            is_classified = best_match.confidence_score >= min_confidence
            
            # Extract diagnostic questions if available
            diagnostic_questions = best_match.diagnostic_questions or [
                "Can you provide more details about when this issue occurs?",
                "What steps have you already taken to try to resolve this?",
                "Is this affecting other users or just you?"
            ]
            
            # Determine recommended tools based on category
            recommended_tools = self._get_recommended_tools(best_match.category)
            
            return ClassificationResult(
                classified=is_classified,
                confidence=best_match.confidence_score,
                suggested_category=best_match.category,
                suggested_severity=best_match.severity,
                matched_issue_id=best_match.issue_id,
                matched_title=best_match.title,
                matched_description=best_match.description,
                similarity_score=best_match.similarity_score,
                diagnostic_questions=diagnostic_questions,
                potential_causes=[best_match.symptoms] if best_match.symptoms else [],
                recommended_tools=recommended_tools,
                created_at=datetime.now()
            )
            
        except Exception as e:
            self.logger.error(f"Issue classification failed: {str(e)}")
            raise
    
    def _get_recommended_tools(self, category: str) -> List[str]:
        """Get recommended tools based on issue category."""
        category_tools = {
            "Authentication": ["check_user_permissions", "query_database"],
            "Performance": ["run_diagnostics", "check_system_status"],
            "Data": ["query_database", "search_knowledge_base"],
            "Integration": ["check_system_status", "query_database"],
            "Authorization": ["check_user_permissions", "query_database"],
            "Network": ["check_system_status", "run_diagnostics"],
            "Database": ["query_database", "run_diagnostics"],
            "UI/UX": ["search_knowledge_base"]
        }
        
        return category_tools.get(category, ["search_knowledge_base", "query_database"])
    
    async def add_issue_to_database(self,
                                   title: str,
                                   description: str,
                                   category: str,
                                   severity: str,
                                   symptoms: Dict[str, Any],
                                   diagnostic_questions: List[str] = None,
                                   tools: List[str] = None) -> str:
        """
        Add a new issue to the database with embedding.
        
        Args:
            title: Issue title
            description: Issue description
            category: Issue category
            severity: Issue severity
            symptoms: Issue symptoms (JSON)
            diagnostic_questions: List of diagnostic questions
            tools: List of recommended tools
            
        Returns:
            ID of the created issue
        """
        if not self.embedding_service:
            raise Exception("Vector search service not initialized")
        
        try:
            # Generate embedding for the issue description
            embedding_text = f"{title}. {description}"
            embedding = await self.embedding_service.generate_embedding(embedding_text)
            
            async with self.session_factory() as session:
                # Insert new issue
                result = await session.execute(text("""
                    INSERT INTO issues (title, description, category, severity, symptoms, 
                                     diagnostic_questions, tools, embedding)
                    VALUES (:title, :description, :category, :severity, :symptoms,
                           :diagnostic_questions, :tools, :embedding)
                    RETURNING issue_id
                """), {
                    "title": title,
                    "description": description,
                    "category": category,
                    "severity": severity,
                    "symptoms": symptoms,
                    "diagnostic_questions": diagnostic_questions or [],
                    "tools": tools or [],
                    "embedding": embedding
                })
                
                issue_id = result.scalar()
                await session.commit()
            
            self.logger.info(f"Added new issue to database: {issue_id}")
            return str(issue_id)
            
        except Exception as e:
            self.logger.error(f"Failed to add issue to database: {str(e)}")
            raise
    
    async def update_issue_embedding(self, issue_id: str, description: str) -> bool:
        """
        Update embedding for an existing issue.
        
        Args:
            issue_id: ID of the issue to update
            description: New description to generate embedding from
            
        Returns:
            True if update was successful
        """
        if not self.embedding_service:
            raise Exception("Vector search service not initialized")
        
        try:
            # Generate new embedding
            embedding = await self.embedding_service.generate_embedding(description)
            
            async with self.session_factory() as session:
                result = await session.execute(text("""
                    UPDATE issues 
                    SET embedding = :embedding, description = :description, updated_at = NOW()
                    WHERE issue_id = :issue_id
                """), {
                    "issue_id": issue_id,
                    "embedding": embedding,
                    "description": description
                })
                
                await session.commit()
            
            self.logger.info(f"Updated embedding for issue: {issue_id}")
            return result.rowcount > 0
            
        except Exception as e:
            self.logger.error(f"Failed to update issue embedding: {str(e)}")
            return False
    
    def get_search_metrics(self) -> Dict[str, Any]:
        """Get search performance metrics."""
        avg_search_time = sum(self.search_times) / len(self.search_times) if self.search_times else 0
        avg_similarity = sum(self.average_similarity_scores) / len(self.average_similarity_scores) if self.average_similarity_scores else 0
        
        return {
            "total_searches": self.total_searches,
            "average_search_time_seconds": avg_search_time,
            "average_similarity_score": avg_similarity,
            "embedding_dimensions": self.embedding_dimensions,
            "default_similarity_threshold": self.default_similarity_threshold,
            "default_max_results": self.default_max_results
        }
    
    async def close(self):
        """Close database connections."""
        if self.engine:
            await self.engine.dispose()
            self.logger.info("Database connections closed")


# Global vector search service instance
vector_search_service = VectorSearchService()


async def get_vector_search_service() -> VectorSearchService:
    """Get the global vector search service instance."""
    if not vector_search_service.engine:
        await vector_search_service.initialize()
    return vector_search_service


async def initialize_vector_search():
    """Initialize vector search service and validate connections."""
    try:
        await vector_search_service.initialize()
        
        # Test basic functionality
        logger = logging.getLogger(__name__)
        logger.info("Vector search service initialized successfully")
        
        return vector_search_service
        
    except Exception as e:
        logging.getLogger(__name__).error(f"Failed to initialize vector search service: {str(e)}")
        raise