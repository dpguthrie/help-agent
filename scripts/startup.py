"""
Startup script for Railway deployment.
Runs migrations, seeds data, then starts the Chainlit app.
"""
import os
import sys
import subprocess
import asyncio
import asyncpg


async def run_migrations():
    """Run SQL migrations against the database."""
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL not set")
        sys.exit(1)

    print("Running migrations...")
    conn = await asyncpg.connect(db_url)

    # Read and execute migration file
    migration_path = os.path.join(os.path.dirname(__file__), "..", "db", "migrations", "001_initial.sql")
    with open(migration_path) as f:
        sql = f.read()

    # Split on semicolons and execute each statement
    # (asyncpg doesn't support multi-statement execute)
    statements = [s.strip() for s in sql.split(";") if s.strip()]
    for stmt in statements:
        try:
            await conn.execute(stmt)
        except asyncpg.exceptions.DuplicateObjectError:
            pass  # Table/index already exists
        except asyncpg.exceptions.DuplicateTableError:
            pass
        except Exception as e:
            # Log but don't fail - most errors are "already exists"
            if "already exists" not in str(e):
                print(f"  Migration warning: {e}")

    await conn.close()
    print("Migrations complete.")


async def seed_users():
    """Seed default users if table is empty."""
    db_url = os.environ.get("DATABASE_URL")
    conn = await asyncpg.connect(db_url)

    count = await conn.fetchval("SELECT count(*) FROM users")
    if count == 0:
        print("Seeding users...")
        # Import here to avoid path issues
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
        from pgvector.asyncpg import register_vector
        await register_vector(conn)

        pool = await asyncpg.create_pool(db_url, init=lambda c: register_vector(c))
        from db.seed import seed_users as do_seed
        await do_seed(pool)
        await pool.close()
        print("Users seeded.")
    else:
        print(f"Users table has {count} rows, skipping seed.")

    await conn.close()


async def main():
    await run_migrations()
    await seed_users()


if __name__ == "__main__":
    # Run migrations and seed
    asyncio.run(main())

    # Run Chainlit DB migrations (creates Thread, Element tables etc.)
    print("Running Chainlit DB migrations...")
    subprocess.run(["chainlit", "db", "upgrade"], check=False)

    # Start Chainlit
    port = os.environ.get("PORT", "8000")
    print(f"Starting Chainlit on port {port}...")
    os.execvp(
        "chainlit",
        ["chainlit", "run", "src/app.py", "--host", "0.0.0.0", "--port", port],
    )
