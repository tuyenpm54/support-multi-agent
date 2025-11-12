#!/usr/bin/env python3
"""
Check the severity constraint
"""

import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def check_constraint():
    conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
    result = await conn.fetch("""
        SELECT conname, pg_get_constraintdef(oid) as definition
        FROM pg_constraint 
        WHERE conrelid = 'public.issues'::regclass 
        AND contype = 'c'
    """)
    print('Table constraints:')
    for row in result:
        print(f"  {row['conname']}: {row['definition']}")
    
    # Check existing severity values
    existing = await conn.fetch("SELECT DISTINCT severity FROM issues")
    print('\nExisting severity values:')
    for row in existing:
        print(f"  {row['severity']}")
    
    await conn.close()

asyncio.run(check_constraint())