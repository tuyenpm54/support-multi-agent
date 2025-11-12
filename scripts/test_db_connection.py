#!/usr/bin/env python3
"""
Test database connection
"""

import asyncio
import asyncpg
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

async def test_connection():
    try:
        print(f"Connecting to: {DATABASE_URL}")
        conn = await asyncpg.connect(DATABASE_URL)
        
        # Test basic query
        version = await conn.fetchval('SELECT version()')
        print(f"✅ Connected successfully!")
        print(f"📊 PostgreSQL version: {version}")
        
        # Check if issues table exists
        table_exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'issues'
            )
        """)
        
        if table_exists:
            print("✅ Issues table exists")
            
            # Count existing records
            count = await conn.fetchval("SELECT COUNT(*) FROM issues")
            print(f"📈 Current issues count: {count}")
        else:
            print("❌ Issues table does not exist")
        
        await conn.close()
        
    except Exception as e:
        print(f"❌ Connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_connection())