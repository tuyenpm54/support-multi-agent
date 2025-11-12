"""
Simplified Vector Search Service - asyncpg implementation
"""

import asyncio
import logging
import os
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from datetime import datetime
import asyncpg
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

# Simple data classes to replace Pydantic models
@dataclass
class SearchResult:
    issue_id: str
    title: str
    description: str
    category: str
    severity: str
    symptoms: Dict[str, Any]
    diagnostic_questions: List[str]
    tools: List[str]
    similarity_score: float
    confidence_score: float
    created_at: datetime
    updated_at: datetime

@dataclass
class ClassificationResult:
    classified: bool
    confidence: float
    suggested_category: str
    suggested_severity: str
    matched_issue_id: Optional[str]
    matched_title: Optional[str] = None
    matched_description: Optional[str] = None
    similarity_score: float = 0.0
    diagnostic_questions: List[str] = None
    potential_causes: List[str] = None
    recommended_tools: List[str] = None
    created_at: datetime = None


class SimplifiedVectorSearchService:
    """Simplified vector search service using asyncpg directly."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.embedding_dimensions = 1536
        self.database_url = os.getenv("DATABASE_URL")
        
    async def search_similar_issues(self, 
                                  query_text: str,
                                  similarity_threshold: float = 0.3,
                                  max_results: int = 5,
                                  category_filter: Optional[List[str]] = None) -> List[SearchResult]:
        """Search for similar issues using database hybrid search function."""
        
        try:
            conn = await asyncpg.connect(self.database_url)
            
            # Use the hybrid search function from database
            category_filter_array = category_filter if category_filter else None
            
            query = """
                SELECT issue_id, title, description, category, severity,
                       symptoms, diagnostic_questions, tools, similarity, confidence,
                       search_method, created_at
                FROM search_issues_hybrid($1::text, NULL, $2::double precision, $3::integer, $4)
            """
            
            rows = await conn.fetch(
                query, query_text, similarity_threshold, max_results, category_filter_array
            )
            
            await conn.close()
            
            results = []
            for row in rows:
                result = SearchResult(
                    issue_id=str(row['issue_id']),
                    title=row['title'],
                    description=row['description'],
                    category=row['category'],
                    severity=row['severity'],
                    symptoms=row['symptoms'] or {},
                    diagnostic_questions=row['diagnostic_questions'] or [],
                    tools=row['tools'] or [],
                    similarity_score=float(row['similarity']),
                    confidence_score=float(row['confidence']),
                    created_at=row['created_at'],
                    updated_at=row['created_at']  # Use created_at for both fields
                )
                results.append(result)
            
            return results
            
        except Exception as e:
            self.logger.error(f"Vector search failed: {str(e)}")
            return []
    
    async def classify_issue(self, 
                           query_text: str,
                           min_confidence: float = 0.6) -> ClassificationResult:
        """Classify issue using vector search."""
        
        results = await self.search_similar_issues(
            query_text=query_text,
            similarity_threshold=0.3,
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
                recommended_tools=[],
                created_at=datetime.now()
            )
        
        best_match = results[0]
        is_classified = best_match.confidence_score >= min_confidence
        
        diagnostic_questions = best_match.diagnostic_questions or [
            "Can you provide more details about when this issue occurs?",
            "What steps have you already taken to try to resolve this?",
            "Is this affecting other users or just you?"
        ]
        
        recommended_tools = best_match.tools or ["search_knowledge_base", "query_database"]
        
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