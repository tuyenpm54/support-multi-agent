"""
Hierarchical Semantic Search Service

Optimized semantic search for hierarchical issue structure with:
- Multi-field embedding strategy
- Dynamic threshold adjustment
- Enhanced query processing
- Hierarchical result ranking
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import json
import re

from src.db import get_db_connection_pool
from src.core.embeddings import get_embedding_service, EmbeddingService


class SemanticSearchConfig:
    """Configuration for semantic search optimization."""
    
    def __init__(self):
        # Search result limits
        self.max_results = 10
        self.min_results = 3
        self.max_detailed_results = 5
        
        # Confidence thresholds
        self.base_confidence_threshold = 0.7
        self.simple_query_threshold = 0.8
        self.complex_query_threshold = 0.6
        
        # Field weights for query enhancement
        self.field_weights = {
            'title': 3.0,
            'symptoms': 2.5,
            'description': 2.0,
            'keywords': 1.5,
            'category': 1.0
        }
        
        # Boost factors
        self.category_match_boost = 0.15
        self.severity_match_boost = 0.1
        self.issue_type_boost = {
            'detailed': 0.1,
            'general': 0.05
        }


class HierarchicalSemanticSearchService:
    """Enhanced semantic search for hierarchical issue structure."""
    
    def __init__(self, config: Optional[SemanticSearchConfig] = None):
        self.logger = logging.getLogger(__name__)
        self.config = config or SemanticSearchConfig()
        self.embedding_service: Optional[EmbeddingService] = None
        self._connection_pool = None
    
    async def initialize(self):
        """Initialize the search service."""
        try:
            self.embedding_service = await get_embedding_service()
            self._connection_pool = await get_db_connection_pool()
            self.logger.info("Hierarchical semantic search service initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize search service: {str(e)}")
            raise
    
    async def search_issues(
        self,
        query_text: str,
        max_results: Optional[int] = None,
        similarity_threshold: Optional[float] = None,
        issue_type_filter: Optional[str] = None,
        category_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Perform optimized semantic search with hierarchical awareness.
        
        Args:
            query_text: User query text
            max_results: Maximum number of results to return
            similarity_threshold: Minimum similarity threshold
            issue_type_filter: Filter by issue type ('general' or 'detailed')
            category_filter: Filter by category
            
        Returns:
            List of matching issues with hierarchical context
        """
        if not query_text.strip():
            return []
        
        try:
            # Calculate dynamic threshold
            threshold = self._calculate_dynamic_threshold(query_text, similarity_threshold)
            results_limit = max_results or self.config.max_results
            
            # Generate query embedding
            query_embedding = await self.embedding_service.generate_embedding(query_text)
            
            # Perform semantic search
            search_results = await self._perform_vector_search(
                query_embedding, threshold, results_limit, 
                issue_type_filter, category_filter
            )
            
            # Enhance results with hierarchical context
            enhanced_results = await self._enhance_search_results(search_results, query_text)
            
            self.logger.info(f"Semantic search found {len(enhanced_results)} results")
            return enhanced_results
            
        except Exception as e:
            self.logger.error(f"Semantic search failed: {str(e)}")
            return []
    
    async def search_general_issue_with_details(
        self,
        query_text: str,
        general_issue_id: str
    ) -> Dict[str, Any]:
        """
        Search for a general issue and return it with its detailed children.
        
        Args:
            query_text: User query text
            general_issue_id: ID of the general issue to analyze
            
        Returns:
            General issue with ordered detailed children
        """
        try:
            async with self._connection_pool.acquire() as conn:
                # Get general issue
                general_issue = await conn.fetchrow("""
                    SELECT * FROM issues 
                    WHERE issue_id = $1 AND issue_type = 'general'
                """, general_issue_id)
                
                if not general_issue:
                    return {"error": "General issue not found"}
                
                # Get detailed children in order
                children = await conn.fetch("""
                    SELECT * FROM get_child_issues_ordered($1)
                    ORDER BY order_index
                """, general_issue_id)
                
                return {
                    "general_issue": dict(general_issue),
                    "detailed_issues": [dict(child) for child in children],
                    "total_children": len(children),
                    "search_query": query_text
                }
                
        except Exception as e:
            self.logger.error(f"Failed to get general issue with details: {str(e)}")
            return {"error": str(e)}
    
    async def get_issue_resolution_path(
        self,
        session_id: str,
        root_issue_id: str
    ) -> Dict[str, Any]:
        """
        Get the resolution path for a hierarchical issue in a session.
        
        Returns the status of each issue and what to attempt next.
        """
        try:
            async with self._connection_pool.acquire() as conn:
                # Get issue hierarchy
                hierarchy = await self._get_issue_hierarchy(root_issue_id)
                
                # Check resolution status for each issue
                resolution_status = {}
                for issue in hierarchy:
                    status = await conn.fetchrow("""
                        SELECT status, user_feedback, attempted_at, completed_at
                        FROM issue_resolution_tracking
                        WHERE session_id = $1 AND issue_id = $2
                        ORDER BY attempted_at DESC
                        LIMIT 1
                    """, session_id, issue['issue_id'])
                    
                    resolution_status[issue['issue_id']] = {
                        "status": status['status'] if status else "not_attempted",
                        "feedback": status['user_feedback'] if status else None,
                        "attempted_at": status['attempted_at'] if status else None
                    }
                
                # Determine next step
                next_action = await self._determine_next_action(hierarchy, resolution_status)
                
                return {
                    "hierarchy": hierarchy,
                    "resolution_status": resolution_status,
                    "next_action": next_action
                }
                
        except Exception as e:
            self.logger.error(f"Failed to get resolution path: {str(e)}")
            return {"error": str(e)}
    
    async def _perform_vector_search(
        self,
        query_embedding: List[float],
        threshold: float,
        limit: int,
        issue_type_filter: Optional[str],
        category_filter: Optional[str]
    ) -> List[Dict[str, Any]]:
        """Perform core vector search with filters."""
        async with self._connection_pool.acquire() as conn:
            # Build WHERE clause
            where_conditions = ["1 = 1"]
            params = [query_embedding, threshold]
            param_count = 2
            
            if issue_type_filter:
                where_conditions.append(f"issue_type = ${param_count}")
                params.append(issue_type_filter)
                param_count += 1
            
            if category_filter:
                where_conditions.append(f"category = ${param_count}")
                params.append(category_filter)
                param_count += 1
            
            where_clause = " AND ".join(where_conditions)
            
            query = f"""
                SELECT 
                    issue_id, title, description, category, severity, issue_type,
                    parent_issue_id, priority, solution_steps, validation_criteria,
                    searchable_content, symptoms, diagnostic_questions, tools,
                    1 - (embedding <=> $1) as similarity_score
                FROM issues
                WHERE {where_clause}
                  AND 1 - (embedding <=> $1) >= $2
                ORDER BY 
                    CASE 
                        WHEN issue_type = 'detailed' THEN priority * 1.2
                        ELSE priority
                    END DESC,
                    similarity_score DESC,
                    created_at DESC
                LIMIT $ {param_count}
            """
            
            params.append(limit)
            results = await conn.fetch(query, *params)
            
            return [dict(row) for row in results]
    
    async def _enhance_search_results(
        self,
        search_results: List[Dict[str, Any]],
        query_text: str
    ) -> List[Dict[str, Any]]:
        """Enhance search results with additional context and scoring."""
        enhanced_results = []
        
        for result in search_results:
            # Calculate composite score
            composite_score = await self._calculate_composite_score(result, query_text)
            
            # Add hierarchical context
            if result['issue_type'] == 'detailed' and result['parent_issue_id']:
                parent_info = await self._get_parent_info(result['parent_issue_id'])
                result['parent_issue'] = parent_info
            
            # Add child count for general issues
            if result['issue_type'] == 'general':
                child_count = await self._get_child_count(result['issue_id'])
                result['child_count'] = child_count
            
            result['composite_score'] = composite_score
            result['search_match_reason'] = self._get_match_reason(result, query_text)
            
            enhanced_results.append(result)
        
        # Sort by composite score
        enhanced_results.sort(key=lambda x: x['composite_score'], reverse=True)
        
        return enhanced_results
    
    def _calculate_dynamic_threshold(
        self,
        query_text: str,
        manual_threshold: Optional[float]
    ) -> float:
        """Calculate dynamic threshold based on query complexity."""
        if manual_threshold is not None:
            return manual_threshold
        
        base_threshold = self.config.base_confidence_threshold
        query_words = len(query_text.split())
        
        # Adjust based on query length
        if query_words > 10:  # Complex query
            base_threshold -= 0.1
        elif query_words < 5:  # Simple query
            base_threshold += 0.1
        
        # Adjust based on specific keywords
        if any(word in query_text.lower() for word in ['lỗi', 'error', 'không', 'chậm']):
            base_threshold -= 0.05  # Slightly lower for error reports
        
        return max(0.5, min(0.9, base_threshold))
    
    async def _calculate_composite_score(
        self,
        result: Dict[str, Any],
        query_text: str
    ) -> float:
        """Calculate composite score combining similarity and other factors."""
        base_score = float(result['similarity_score'])
        
        # Issue type boost
        issue_type_boost = self.config.issue_type_boost.get(result['issue_type'], 0)
        
        # Priority boost
        priority_boost = result.get('priority', 0) * 0.01
        
        # Category match (simplified)
        category_match_boost = 0.0
        if result.get('category') and result['category'].lower() in query_text.lower():
            category_match_boost = self.config.category_match_boost
        
        composite_score = base_score + issue_type_boost + priority_boost + category_match_boost
        
        return min(1.0, composite_score)
    
    def _get_match_reason(self, result: Dict[str, Any], query_text: str) -> List[str]:
        """Determine why this result matches the query."""
        reasons = []
        
        if result['issue_type'] == 'detailed':
            reasons.append("Specific solution available")
        
        if result.get('priority', 0) > 5:
            reasons.append("High priority issue")
        
        if result.get('severity') == 'High':
            reasons.append("High severity issue")
        
        return reasons
    
    async def _get_parent_info(self, parent_id: str) -> Optional[Dict[str, Any]]:
        """Get information about parent issue."""
        try:
            async with self._connection_pool.acquire() as conn:
                parent = await conn.fetchrow("""
                    SELECT issue_id, title, description, category, severity, issue_type
                    FROM issues WHERE issue_id = $1
                """, parent_id)
                
                return dict(parent) if parent else None
        except Exception:
            return None
    
    async def _get_child_count(self, issue_id: str) -> int:
        """Get number of child issues for a general issue."""
        try:
            async with self._connection_pool.acquire() as conn:
                count = await conn.fetchval("""
                    SELECT COUNT(*) FROM issues WHERE parent_issue_id = $1
                """, issue_id)
                
                return count or 0
        except Exception:
            return 0
    
    async def _get_issue_hierarchy(self, root_id: str) -> List[Dict[str, Any]]:
        """Get hierarchical structure of issues."""
        try:
            async with self._connection_pool.acquire() as conn:
                # Get root issue
                root = await conn.fetchrow("""
                    SELECT * FROM issues WHERE issue_id = $1
                """, root_id)
                
                if not root:
                    return []
                
                hierarchy = [dict(root)]
                
                # If root is general, get children
                if root['issue_type'] == 'general':
                    children = await conn.fetch("""
                        SELECT * FROM issues WHERE parent_issue_id = $1
                        ORDER BY priority DESC, title
                    """, root_id)
                    
                    hierarchy.extend([dict(child) for child in children])
                
                return hierarchy
        except Exception as e:
            self.logger.error(f"Failed to get issue hierarchy: {str(e)}")
            return []
    
    async def _determine_next_action(
        self,
        hierarchy: List[Dict[str, Any]],
        resolution_status: Dict[str, str]
    ) -> Dict[str, Any]:
        """Determine what action to take next in resolution."""
        # Find first unattempted issue
        for issue in hierarchy:
            issue_status = resolution_status.get(issue['issue_id'], 'not_attempted')
            
            if issue_status['status'] == 'not_attempted':
                return {
                    "action": "attempt_issue",
                    "issue": issue,
                    "reason": "Next unattempted issue"
                }
            
            elif issue_status['status'] == 'failed':
                return {
                    "action": "retry_issue", 
                    "issue": issue,
                    "reason": "Previously failed, retrying",
                    "previous_attempt": issue_status.get('attempted_at')
                }
        
        # All issues attempted
        return {
            "action": "complete",
            "reason": "All issues have been attempted",
            "summary": resolution_status
        }


# Global service instance
_hierarchical_search_service = None


async def get_hierarchical_search_service() -> HierarchicalSemanticSearchService:
    """Get the global hierarchical semantic search service instance."""
    global _hierarchical_search_service
    
    if _hierarchical_search_service is None:
        _hierarchical_search_service = HierarchicalSemanticSearchService()
        await _hierarchical_search_service.initialize()
    
    return _hierarchical_search_service