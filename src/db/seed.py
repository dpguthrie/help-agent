from __future__ import annotations
import asyncpg


SEED_USERS = [
    {
        "tenant_name": "COMPANY_demo_001",
        "org_id": "SFID_demo_001",
        "product": "core",
        "success_plan": "Premier",
        "timezone": "America/Chicago",
        "phone_number": "+1 555-0100",
        "can_create_case": True,
        "is_chat_transfer_allowed": True,
        "is_authenticated": True,
    },
    {
        "tenant_name": "COMPANY_demo_002",
        "org_id": "SFID_demo_002",
        "product": "core",
        "success_plan": "Standard",
        "timezone": None,
        "phone_number": None,
        "can_create_case": True,
        "is_chat_transfer_allowed": False,
        "is_authenticated": True,
    },
    {
        "tenant_name": "COMPANY_demo_003",
        "org_id": "SFID_demo_003",
        "product": "marketing_cloud",
        "success_plan": "Premier",
        "timezone": "Asia/Tokyo",
        "phone_number": "+81 3-1234-5678",
        "can_create_case": True,
        "is_chat_transfer_allowed": True,
        "is_authenticated": False,
    },
]


async def seed_users(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        for user in SEED_USERS:
            await conn.execute(
                """
                INSERT INTO users (tenant_name, org_id, product, success_plan, timezone,
                                   phone_number, can_create_case, is_chat_transfer_allowed, is_authenticated)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (org_id) DO NOTHING
                """,
                user["tenant_name"], user["org_id"], user["product"],
                user["success_plan"], user["timezone"], user["phone_number"],
                user["can_create_case"], user["is_chat_transfer_allowed"],
                user["is_authenticated"],
            )
