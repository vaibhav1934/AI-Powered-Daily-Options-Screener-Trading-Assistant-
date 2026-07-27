#!/usr/bin/env python
"""
CLI Tool: Administrator User Creation
=====================================
Creates or updates a user account in the StockGlass database.
Per institutional security rules, there is NO public registration endpoint in the API;
user accounts must be created exclusively via this administrator tool.

Usage:
    python scripts/create_user.py --username admin --password secret
"""

import argparse
import asyncio
import os
import sys

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.models import Base
from app.db.session import engine, async_session_factory
from app.services.auth_service import create_user_in_db


async def main() -> None:
    parser = argparse.ArgumentParser(description="Create or update a StockGlass user account.")
    parser.add_argument("--username", required=True, help="Username for login (e.g. admin or trader)")
    parser.add_argument("--password", required=True, help="Password for login")
    parser.add_argument(
        "--inactive", action="store_true", help="Set account to inactive/disabled state"
    )

    args = parser.parse_args()

    print(f"[StockGlass CLI] Initializing database schema...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    print(f"[StockGlass CLI] Processing account for user '{args.username}'...")
    async with async_session_factory() as session:
        user = await create_user_in_db(
            session=session,
            username=args.username,
            password=args.password,
            is_active=not args.inactive,
        )
        print(f"[SUCCESS] User '{user.username}' (ID: {user.id}) successfully created/updated!")
        print(f"          Active Status: {user.is_active}")
        print(f"          Ready for JWT authentication via POST /v1/auth/login")


if __name__ == "__main__":
    asyncio.run(main())
