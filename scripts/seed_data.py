#!/usr/bin/env python3
"""
Seed script to create initial data for development and testing.

Run this script after migrations to set up:
- A demo organization
- Default development environment with API keys
- An admin agent account

Usage:
    python scripts/seed_data.py

The script will output the credentials needed to test the API.
"""

import asyncio
import sys
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select

from app.core.config import settings
from app.core.security import (
    generate_api_key,
    generate_api_secret,
    generate_plugin_key,
    hash_password,
)
from app.db.postgres import AsyncSessionLocal
from app.domains.organization.models import Organization, OrganizationPlan
from app.domains.environment.models import Environment, EnvironmentType
from app.domains.agent.models import Agent, AgentRole


async def seed_database():
    """Create initial seed data."""

    async with AsyncSessionLocal() as db:
        # Check if data already exists
        result = await db.execute(select(Organization).limit(1))
        if result.scalar_one_or_none():
            print("Database already has data. Skipping seed.")
            return

        print("Creating seed data...")
        print("-" * 50)

        # 1. Create demo organization
        org = Organization(
            name="Demo Company",
            slug="demo-company",
            plan=OrganizationPlan.PRO,
            max_agents=10,
            settings={
                "chat_widget": {
                    "primary_color": "#6366f1",
                    "position": "bottom-right",
                    "greeting": "Hello! How can we help you today?",
                },
                "auto_assign": True,
            },
        )
        db.add(org)
        await db.flush()

        print(f"Created Organization: {org.name}")
        print(f"  ID: {org.id}")
        print(f"  Slug: {org.slug}")

        # 2. Create development environment
        dev_api_secret = generate_api_secret()
        dev_env = Environment(
            organization_id=org.id,
            name="Development",
            env_type=EnvironmentType.DEVELOPMENT,
            plugin_key=generate_plugin_key(),
            api_key=generate_api_key(),
            api_secret_hash=hash_password(dev_api_secret),
            allowed_domains=[
                "http://localhost:3000",
                "http://localhost:8000",
                "http://127.0.0.1:3000",
                "http://127.0.0.1:8000",
            ],
        )
        db.add(dev_env)
        await db.flush()

        print(f"\nCreated Development Environment:")
        print(f"  Plugin Key: {dev_env.plugin_key}")
        print(f"  API Key: {dev_env.api_key}")
        print(f"  API Secret: {dev_api_secret}")
        print("  (Save the API Secret - it won't be shown again!)")

        # 3. Create production environment
        prod_api_secret = generate_api_secret()
        prod_env = Environment(
            organization_id=org.id,
            name="Production",
            env_type=EnvironmentType.PRODUCTION,
            plugin_key=generate_plugin_key(),
            api_key=generate_api_key(),
            api_secret_hash=hash_password(prod_api_secret),
            allowed_domains=["https://demo-company.com"],
        )
        db.add(prod_env)
        await db.flush()

        print(f"\nCreated Production Environment:")
        print(f"  Plugin Key: {prod_env.plugin_key}")
        print(f"  API Key: {prod_env.api_key}")
        print(f"  API Secret: {prod_api_secret}")
        print("  (Save the API Secret - it won't be shown again!)")

        # 4. Create admin agent
        admin_password = "admin123!"  # Default password for testing
        admin = Agent(
            organization_id=org.id,
            email="admin@demo-company.com",
            password_hash=hash_password(admin_password),
            name="Demo Admin",
            nickname="Admin",
            role=AgentRole.ADMIN,
            max_concurrent_chats=10,
        )
        db.add(admin)
        await db.flush()

        print(f"\nCreated Admin Agent:")
        print(f"  Email: {admin.email}")
        print(f"  Password: {admin_password}")
        print(f"  Role: {admin.role.value}")

        # 5. Create a regular agent
        agent_password = "agent123!"
        agent = Agent(
            organization_id=org.id,
            email="agent@demo-company.com",
            password_hash=hash_password(agent_password),
            name="Demo Agent",
            nickname="Support",
            role=AgentRole.AGENT,
            max_concurrent_chats=5,
        )
        db.add(agent)
        await db.flush()

        print(f"\nCreated Agent:")
        print(f"  Email: {agent.email}")
        print(f"  Password: {agent_password}")
        print(f"  Role: {agent.role.value}")

        await db.commit()

        print("\n" + "=" * 50)
        print("Seed data created successfully!")
        print("=" * 50)

        # Print summary for easy copy-paste
        print("\n--- Quick Reference ---\n")
        print("Login (Admin):")
        print(f"  POST /v1/auth/login")
        print(f'  {{"email": "{admin.email}", "password": "{admin_password}"}}')

        print("\nSDK Authentication:")
        print(f"  X-Plugin-Key: {dev_env.plugin_key}")

        print("\nBackend Authentication:")
        print(f"  X-API-Key: {dev_env.api_key}")
        print(f"  X-API-Secret: {dev_api_secret}")


async def main():
    """Main entry point."""
    print(f"Environment: {settings.environment}")
    print(f"Database: {settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}")
    print()

    await seed_database()


if __name__ == "__main__":
    asyncio.run(main())
