#!/usr/bin/env python3
"""
Check table structure
"""

import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def check_table():
    conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
    result = await conn.fetch("""
        SELECT column_name, data_type, udt_name 
        FROM information_schema.columns 
        WHERE table_name = 'issues' AND column_name = 'embedding'
    """)
    print('Embedding column info:', result)
    await conn.close()

asyncio.run(check_table())