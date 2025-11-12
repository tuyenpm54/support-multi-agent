#!/usr/bin/env python3
"""
Check active_issues table structure and purpose
"""

import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def check_active_issues():
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
        print("❌ active_issues table does not exist")
        await conn.close()
        return
    
    # Get table structure
    columns = await conn.fetch("""
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns 
        WHERE table_name = 'active_issues'
        ORDER BY ordinal_position
    """)
    
    print("📋 active_issues table structure:")
    for col in columns:
        nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
        default = f" DEFAULT {col['column_default']}" if col['column_default'] else ""
        print(f"  • {col['column_name']}: {col['data_type']} {nullable}{default}")
    
    # Check current count
    count = await conn.fetchval("SELECT COUNT(*) FROM active_issues")
    print(f"\n📊 Current active issues: {count}")
    
    # Check indexes
    indexes = await conn.fetch("""
        SELECT indexname, indexdef 
        FROM pg_indexes 
        WHERE tablename = 'active_issues'
    """)
    
    if indexes:
        print("\n🗂️  Indexes on active_issues:")
        for idx in indexes:
            print(f"  • {idx['indexname']}")
    
    # Check foreign key constraints
    constraints = await conn.fetch("""
        SELECT
            tc.constraint_name,
            tc.constraint_type,
            kcu.column_name,
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        LEFT JOIN information_schema.constraint_column_usage AS ccu
            ON ccu.constraint_name = tc.constraint_name
            AND ccu.table_schema = tc.table_schema
        WHERE tc.table_name = 'active_issues'
        AND tc.constraint_type IN ('FOREIGN KEY', 'PRIMARY KEY')
    """)
    
    if constraints:
        print("\n🔗 Constraints:")
        for cons in constraints:
            if cons['constraint_type'] == 'FOREIGN KEY':
                print(f"  • FK: {cons['column_name']} → {cons['foreign_table_name']}.{cons['foreign_column_name']}")
            else:
                print(f"  • {cons['constraint_type']}: {cons['column_name']}")
    
    await conn.close()

if __name__ == "__main__":
    asyncio.run(check_active_issues())