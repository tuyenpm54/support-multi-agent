#!/usr/bin/env python3
"""
Clean up redundant active_issues table
"""

import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def cleanup_active_issues():
    conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
    
    # Check if active_issues table exists
    table_exists = await conn.fetchval("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = 'active_issues'
        )
    """)
    
    if not table_exists:
        print("✅ active_issues table does not exist (already cleaned)")
        await conn.close()
        return
    
    print("🗑️  Dropping redundant active_issues table...")
    
    # Get count before dropping
    count = await conn.fetchval("SELECT COUNT(*) FROM active_issues")
    print(f"   Records to be removed: {count}")
    
    # Drop the view
    try:
        await conn.execute("DROP VIEW IF EXISTS active_issues")
        print("✅ Successfully dropped active_issues view")
    except Exception as e:
        print(f"❌ Failed to drop view: {e}")
    
    await conn.close()

if __name__ == "__main__":
    asyncio.run(cleanup_active_issues())