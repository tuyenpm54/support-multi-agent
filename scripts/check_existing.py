#!/usr/bin/env python3
"""
Check existing embeddings format
"""

import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def check_existing():
    conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
    result = await conn.fetch("""
        SELECT issue_id, title, embedding::text 
        FROM issues 
        LIMIT 2
    """)
    print('Existing embeddings:')
    for row in result:
        print(f"  {row['title']}: {row['embedding'][:100]}...")
    await conn.close()

asyncio.run(check_existing())