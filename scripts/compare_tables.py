#!/usr/bin/env python3
"""
Compare issues and active_issues tables
"""

import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def compare_tables():
    conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
    
    # Compare counts
    issues_count = await conn.fetchval("SELECT COUNT(*) FROM issues")
    active_count = await conn.fetchval("SELECT COUNT(*) FROM active_issues")
    
    print(f"📊 Table comparison:")
    print(f"  • issues table: {issues_count} records")
    print(f"  • active_issues table: {active_count} records")
    
    # Check if they have the same data
    sample_issues = await conn.fetch("""
        SELECT issue_id, title, category, severity
        FROM issues 
        LIMIT 5
    """)
    
    sample_active = await conn.fetch("""
        SELECT issue_id, title, category, severity
        FROM active_issues 
        LIMIT 5
    """)
    
    print("\n📋 Sample from issues table:")
    for row in sample_issues:
        print(f"  • {row['title']} ({row['category']}, {row['severity']})")
    
    print("\n📋 Sample from active_issues table:")
    for row in sample_active:
        print(f"  • {row['title']} ({row['category']}, {row['severity']})")
    
    # Check for differences
    categories_issues = await conn.fetch("""
        SELECT category, COUNT(*) as count
        FROM issues 
        GROUP BY category
        ORDER BY count DESC
    """)
    
    categories_active = await conn.fetch("""
        SELECT category, COUNT(*) as count
        FROM active_issues 
        GROUP BY category
        ORDER BY count DESC
    """)
    
    print("\n📈 Categories in issues table:")
    for row in categories_issues:
        print(f"  • {row['category']}: {row['count']}")
    
    print("\n📈 Categories in active_issues table:")
    for row in categories_active:
        print(f"  • {row['category']}: {row['count']}")
    
    await conn.close()

if __name__ == "__main__":
    asyncio.run(compare_tables())