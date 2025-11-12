#!/usr/bin/env python3
"""
Verify the loaded data and test search functionality
"""

import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def verify_data():
    conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
    
    # Count total issues
    total_count = await conn.fetchval("SELECT COUNT(*) FROM issues")
    print(f"📊 Total issues in database: {total_count}")
    
    # Count by category
    categories = await conn.fetch("""
        SELECT category, COUNT(*) as count 
        FROM issues 
        GROUP BY category 
        ORDER BY count DESC
    """)
    print("\n📈 Issues by category:")
    for row in categories:
        print(f"  {row['category']}: {row['count']}")
    
    # Test hybrid search function
    print("\n🔍 Testing hybrid search function:")
    try:
        search_results = await conn.fetch("""
            SELECT title, category, severity, similarity, confidence, search_method
            FROM search_issues_hybrid(
                'công thức', 
                NULL, 
                0.3, 
                5, 
                ARRAY['formula', 'formula_solution']
            )
        """)
        
        print(f"Found {len(search_results)} results for 'công thức':")
        for i, row in enumerate(search_results, 1):
            print(f"  {i}. {row['title']} ({row['category']}) - {row['search_method']}")
            print(f"     Similarity: {row['similarity']:.3f}, Confidence: {row['confidence']:.3f}")
    
    except Exception as e:
        print(f"❌ Search test failed: {e}")
    
    # Show some sample Vietnamese issues
    print("\n🇻🇳 Sample Vietnamese issues:")
    vietnamese = await conn.fetch("""
        SELECT title, category, severity 
        FROM issues 
        WHERE title LIKE '%Công thức%' OR title LIKE '%kho%'
        LIMIT 5
    """)
    for row in vietnamese:
        print(f"  • {row['title']} ({row['category']}, {row['severity']})")
    
    await conn.close()

if __name__ == "__main__":
    asyncio.run(verify_data())