#!/usr/bin/env python3
"""
Verify final database architecture
"""

import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def verify_architecture():
    conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
    
    print("🏗️  Final Multi-Agent Support System Database Architecture")
    print("=" * 60)
    
    # Check all tables
    tables = await conn.fetch("""
        SELECT table_name
        FROM information_schema.tables 
        WHERE table_schema = 'public'
        ORDER BY table_name
    """)
    
    print("\n📋 Database Tables:")
    for row in tables:
        print(f"  • {row['table_name']}")
    
    # Verify issues table structure
    issues_columns = await conn.fetch("""
        SELECT column_name, data_type
        FROM information_schema.columns 
        WHERE table_name = 'issues'
        ORDER BY ordinal_position
    """)
    
    print("\n🎯 Issues Table (Knowledge Base for Classifier):")
    for col in issues_columns:
        print(f"  • {col['column_name']}: {col['data_type']}")
    
    # Check issues count and categories
    issues_count = await conn.fetchval("SELECT COUNT(*) FROM issues")
    print(f"\n📊 Total Issues in Knowledge Base: {issues_count}")
    
    categories = await conn.fetch("""
        SELECT category, COUNT(*) as count
        FROM issues 
        GROUP BY category
        ORDER BY count DESC
    """)
    
    print("\n📈 Issues by Category:")
    for row in categories:
        print(f"  • {row['category']}: {row['count']}")
    
    # Test semantic search functionality
    print("\n🔍 Testing Semantic Search (Classifier):")
    try:
        search_results = await conn.fetch("""
            SELECT title, category, severity, similarity, confidence, search_method
            FROM search_issues_hybrid('công thức', NULL, 0.3, 5, NULL)
        """)
        
        print(f"  Found {len(search_results)} results for Vietnamese search:")
        for i, row in enumerate(search_results, 1):
            print(f"    {i}. {row['title']} ({row['category']}) - {row['search_method']}")
            print(f"       Similarity: {row['similarity']:.3f}")
    except Exception as e:
        print(f"  ❌ Search test failed: {e}")
    
    print("\n🗄️  Session State Management:")
    print("  • Redis handles session state and active conversation context")
    print("  • No need for separate active_issues table/view")
    print("  • SessionManager in src/core/state_manager.py manages conversation state")
    
    print("\n🔄 Data Flow:")
    print("  Customer Input → Classifier Agent → Issues Knowledge Base (semantic search)")
    print("  ↓")
    print("  Session Context (Redis) ← Active Conversation Processing")
    print("  ↓")
    print("  Resolution ← Agent Coordination → Tools & Solutions")
    
    await conn.close()

if __name__ == "__main__":
    asyncio.run(verify_architecture())