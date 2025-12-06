"""MongoDB database connection using Motor (async driver)."""

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core.config import settings

# Global MongoDB client and database instances
mongodb_client: AsyncIOMotorClient | None = None
mongodb_db: AsyncIOMotorDatabase | None = None


async def connect_mongodb() -> None:
    """Connect to MongoDB."""
    global mongodb_client, mongodb_db

    # Optimized connection settings for low latency
    mongodb_client = AsyncIOMotorClient(
        settings.mongodb_url,
        maxPoolSize=50,  # Connection pool size
        minPoolSize=10,  # Minimum connections to keep
        maxIdleTimeMS=30000,  # Close idle connections after 30s
        connectTimeoutMS=5000,  # Connection timeout
        serverSelectionTimeoutMS=5000,  # Server selection timeout
    )
    mongodb_db = mongodb_client[settings.mongodb_database]

    # Test connection
    try:
        await mongodb_client.admin.command("ping")
        print(f"Connected to MongoDB: {settings.mongodb_database}")
    except Exception as e:
        print(f"Failed to connect to MongoDB: {e}")
        raise


async def close_mongodb() -> None:
    """Close MongoDB connection."""
    global mongodb_client

    if mongodb_client:
        mongodb_client.close()
        print("MongoDB connection closed")


def get_mongodb() -> AsyncIOMotorDatabase:
    """
    Get MongoDB database instance.

    Usage:
        @app.get("/")
        async def endpoint(db: AsyncIOMotorDatabase = Depends(get_mongodb)):
            collection = db["users"]
            ...
    """
    if mongodb_db is None:
        raise RuntimeError("MongoDB is not connected")
    return mongodb_db


def get_collection(collection_name: str):
    """
    Get a MongoDB collection.

    Args:
        collection_name: Name of the collection

    Returns:
        AsyncIOMotorCollection
    """
    db = get_mongodb()
    return db[collection_name]


def get_org_collection(base_name: str, org_id: str, env_type: str):
    """
    Get organization-specific collection.

    Collections are named: {base_name}_{org_id}_{env_type}
    Example: users_abc123_development

    Args:
        base_name: Base collection name (users, chats, messages)
        org_id: Organization ID
        env_type: Environment type (development, staging, production)

    Returns:
        AsyncIOMotorCollection
    """
    collection_name = f"{base_name}_{org_id}_{env_type}"
    return get_collection(collection_name)


async def ensure_indexes(org_id: str, env_type: str) -> None:
    """
    Create indexes for organization collections.
    Call this when a new organization is created.

    Indexes are critical for 150ms response time target.
    """
    db = get_mongodb()

    # Chats collection indexes
    chats_col = db[f"chats_{org_id}_{env_type}"]
    await chats_col.create_index("user_id")
    await chats_col.create_index("assigned_agent_id")
    await chats_col.create_index("status")
    await chats_col.create_index([("status", 1), ("created_at", -1)])
    await chats_col.create_index([("assigned_agent_id", 1), ("status", 1)])

    # Messages collection indexes
    messages_col = db[f"messages_{org_id}_{env_type}"]
    await messages_col.create_index("chat_id")
    await messages_col.create_index([("chat_id", 1), ("created_at", -1)])
    await messages_col.create_index([("chat_id", 1), ("read_by_agent", 1)])

    # Users collection indexes
    users_col = db[f"users_{org_id}_{env_type}"]
    await users_col.create_index("member_id", unique=True)
    await users_col.create_index("last_seen_at")

    print(f"Created indexes for org {org_id} ({env_type})")
