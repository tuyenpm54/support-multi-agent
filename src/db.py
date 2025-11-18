"""
Database connection utilities
"""
import asyncpg
import os
from typing import AsyncGenerator

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://localhost:5432/support_multi_agent")

async def get_db_connection() -> asyncpg.Connection:
    """Get a database connection"""
    return await asyncpg.connect(DATABASE_URL)

async def get_db_connection_pool() -> asyncpg.Pool:
    """Get a database connection pool"""
    return await asyncpg.create_pool(DATABASE_URL)