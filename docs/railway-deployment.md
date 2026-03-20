# Railway Deployment Playbook

Deploy the Salesforce Help Agent to Railway with a public URL.

## Prerequisites

- [Railway account](https://railway.com) on the Hobby plan ($5/month)
- GitHub repo with the agent code pushed
- `BRAINTRUST_API_KEY` ready
- Local DB loaded with articles (run `./scripts/load_all_scraped.sh` first)

## Expected Monthly Cost

~$5-8/month on Hobby plan for a low-traffic demo:
- App compute: ~$7.50 (0.25 vCPU, 256MB RAM)
- Postgres compute: ~$4.50 (0.1 vCPU, 256MB RAM)
- Storage: ~$0.15 (1GB volume)
- Minus $5 included credit = **~$7-8 total**

---

## Step 1: Create Railway Project

1. Go to [railway.com/dashboard](https://railway.com/dashboard)
2. Click **"New Project"**
3. Select **"Empty Project"**
4. Name it `sfdc-help-agent`

## Step 2: Deploy PostgreSQL with pgvector

1. Inside your project, click **"New"** → **"Database"** → **"PostgreSQL"**
   - Alternatively, search for **"pgvector"** in the template marketplace for a pre-configured pgvector instance
2. Wait for the database to provision (takes ~30 seconds)
3. Click on the Postgres service → **"Variables"** tab
4. Copy the `DATABASE_URL` connection string — you'll need this for migrations and seeding

### Run migrations

Connect to the Railway Postgres from your local machine and run the initial migration:

```bash
# Use the DATABASE_URL you copied from Railway
psql "postgresql://postgres:xxxx@xxxx.railway.app:xxxx/railway" < db/migrations/001_initial.sql
```

## Step 3: Deploy the App Service

1. In your project, click **"New"** → **"GitHub Repo"**
2. Select your repository
3. Railway will auto-detect the `Dockerfile` and start building

### Set environment variables

1. Click on the app service → **"Variables"** tab
2. Click **"New Variable"** and add each of these:

| Variable | Value |
|---|---|
| `BRAINTRUST_API_KEY` | `sk-your-key-here` |
| `CLASSIFIER_MODEL` | `claude-haiku-4-5` |
| `EXECUTOR_MODEL` | `claude-sonnet-4-5` |
| `EMBEDDING_MODEL` | `text-embedding-3-small` |
| `CLASSIFIER_TEMPERATURE` | `0.0` |
| `EXECUTOR_TEMPERATURE` | `0.2` |
| `EXECUTOR_MAX_TOKENS` | `4096` |
| `PORT` | `8000` |

3. **Link the database**: Click **"New Variable"** → **"Add Reference"** → select the Postgres service → select `DATABASE_URL`. This auto-populates the connection string and keeps it in sync.

### Configure networking

1. Click on the app service → **"Settings"** tab
2. Under **"Networking"**, click **"Generate Domain"** to get a public URL (e.g., `sfdc-help-agent-production.up.railway.app`)
3. Set the port to **8000**

Railway will automatically rebuild and deploy when you push to your GitHub repo.

## Step 4: Seed the Database

### Option A: Load articles directly into Railway DB

Point the scraper's load command at the Railway database URL you copied in Step 2:

```bash
# Replace with your Railway DATABASE_URL
export RAILWAY_DB_URL="postgresql://postgres:xxxx@xxxx.railway.app:xxxx/railway"

# Load articles
PYTHONPATH=src:. .venv/bin/python -m scraper.cli load \
  --input /tmp/all_scraped_merged.jsonl \
  --db-url "$RAILWAY_DB_URL" \
  --api-key "$BRAINTRUST_API_KEY" \
  --no-questions --force
```

### Option B: pg_dump from local, pg_restore to Railway

```bash
# Dump local DB (data only)
pg_dump -h localhost -p 5433 -U sfdc --data-only sfdc > /tmp/sfdc_data.sql

# Restore to Railway
psql "$RAILWAY_DB_URL" < /tmp/sfdc_data.sql
```

### Seed users

```bash
PYTHONPATH=src:. .venv/bin/python -c "
import asyncio, asyncpg
from pgvector.asyncpg import register_vector
from db.seed import seed_users
async def main():
    pool = await asyncpg.create_pool('$RAILWAY_DB_URL', init=lambda c: register_vector(c))
    await seed_users(pool)
    await pool.close()
    print('Seeded.')
asyncio.run(main())
"
```

## Step 5: Verify Deployment

1. Open the public URL from Step 3 in your browser
2. You should see the Chainlit welcome message
3. Try: "How do I create a report?" — should search the KB and return results

---

## Step 6: Custom Domain (Optional)

1. Click on the app service → **"Settings"** → **"Networking"**
2. Click **"Custom Domain"**
3. Enter your domain (e.g., `help-agent.yourdomain.com`)
4. Add a **CNAME record** in your DNS provider pointing to the Railway domain

---

## Step 7: Deploy Simulator Service (Optional)

The simulator runs as a separate Railway service that generates realistic traffic at a configurable cadence.

### Create the simulator service

1. In your project, click **"New"** → **"GitHub Repo"** (same repo)
2. Click on the new service → **"Settings"** tab
3. Under **"Build"**, set the **Dockerfile path** to `Dockerfile.simulator`
4. Under **"Deploy"**, set the **Start command** to `python -m simulator.service`

### Set environment variables

1. Click on the simulator service → **"Variables"** tab
2. Add a **reference** to the Postgres `DATABASE_URL` (same as the agent service)
3. Add these variables:

| Variable | Value |
|---|---|
| `BRAINTRUST_API_KEY` | `sk-your-key-here` |
| `CLASSIFIER_MODEL` | `claude-haiku-4-5` |
| `EXECUTOR_MODEL` | `claude-sonnet-4-5` |
| `EMBEDDING_MODEL` | `text-embedding-3-small` |
| `SIMULATOR_CADENCE` | `3600` (1 batch per hour) |
| `SIMULATOR_BATCH_SIZE` | `3` |
| `SIMULATOR_CONCURRENCY` | `3` |
| `SIMULATOR_MODEL` | `gpt-5-nano` |
| `SIMULATOR_ENABLED` | `true` |

### Cost for simulator

| Setting | Low traffic | Medium | High |
|---|---|---|---|
| `SIMULATOR_CADENCE` | 3600 (1hr) | 600 (10min) | 300 (5min) |
| `SIMULATOR_BATCH_SIZE` | 2 | 3 | 5 |
| Conversations/day | ~48 | ~432 | ~1,440 |
| LLM cost/day | ~$1.50 | ~$13 | ~$43 |
| Compute cost/day | ~$0.50 | ~$1 | ~$2 |

Start with **low traffic** and increase when you want more data for error analysis.

### Pause/Resume

To pause the simulator without deleting it:
1. Click on the simulator service → **"Variables"** tab
2. Change `SIMULATOR_ENABLED` to `false`
3. To resume, change it back to `true`

---

## Updating the Deployment

**Auto-deploy (recommended):**
1. Click on the app service → **"Settings"** → **"Source"**
2. Connect your GitHub repo if not already connected
3. Every push to `main` will auto-deploy

**Manual deploy:**
1. Push your changes to GitHub
2. In Railway dashboard, click on the service → **"Deployments"** → **"Deploy"**

## Monitoring

- **Railway dashboard**: Click on any service to see CPU, memory, network usage, and logs
- **Braintrust dashboard**: Trace logs, token usage, latency at [braintrust.dev](https://www.braintrust.dev)

## Troubleshooting

| Issue | Fix |
|---|---|
| `pgvector extension not found` | Connect to Railway Postgres and run `CREATE EXTENSION IF NOT EXISTS vector;` |
| `DATABASE_URL not set` | Add a variable reference from the Postgres service to the app service |
| Port issues | Ensure `PORT=8000` is set in the app service variables |
| Connection refused | Ensure the Postgres service is linked via variable reference, not a hardcoded URL |
| Slow cold starts | Railway sleeps idle services on the Hobby plan; first request after idle takes a few seconds |
| Build fails | Check the build logs in the **"Deployments"** tab for the service |
