# Railway Deployment Playbook

Deploy the Salesforce Help Agent to Railway with a public URL.

## Prerequisites

- [Railway account](https://railway.com) on the Hobby plan ($5/month)
- Railway CLI installed: `npm install -g @railway/cli` or `brew install railway`
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

```bash
# Login to Railway
railway login

# Create a new project
railway init --name sfdc-help-agent
```

## Step 2: Deploy PostgreSQL with pgvector

Railway has a pgvector template in their marketplace.

```bash
# Add a Postgres service with pgvector
# Option A: Via the Railway dashboard
#   1. Go to your project in https://railway.com/dashboard
#   2. Click "New" -> "Database" -> "PostgreSQL"
#   3. Or search for "pgvector" in templates and deploy that

# Option B: Via CLI (standard Postgres, then enable pgvector)
railway add --plugin postgresql
```

After Postgres is provisioned, note the connection string. It will be available as `DATABASE_URL` in the service environment.

### Run migrations

Connect to the Railway Postgres and run the initial migration:

```bash
# Get the connection string from Railway
railway variables --service postgresql

# Run migration against Railway DB
psql "$RAILWAY_DATABASE_URL" < db/migrations/001_initial.sql
```

## Step 3: Deploy the App Service

```bash
# Link to the project
railway link

# Set environment variables
railway variables set BRAINTRUST_API_KEY="sk-your-key-here"
railway variables set CLASSIFIER_MODEL="claude-haiku-4-5"
railway variables set EXECUTOR_MODEL="claude-sonnet-4-5"
railway variables set EMBEDDING_MODEL="text-embedding-3-small"
railway variables set CLASSIFIER_TEMPERATURE="0.0"
railway variables set EXECUTOR_TEMPERATURE="0.2"
railway variables set EXECUTOR_MAX_TOKENS="4096"
railway variables set PORT="8000"

# DATABASE_URL is automatically set by Railway when you link Postgres to the app service
# Verify it's set:
railway variables | grep DATABASE_URL

# Deploy
railway up
```

Railway will:
1. Detect the `Dockerfile`
2. Build the image
3. Deploy and expose port 8000
4. Provide a public URL (e.g., `sfdc-help-agent-production.up.railway.app`)

## Step 4: Seed the Database

### Option A: Load articles directly into Railway DB

Point the scraper's load command at the Railway database:

```bash
# Get Railway DB URL
export RAILWAY_DB_URL=$(railway variables get DATABASE_URL --service postgresql)

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

```bash
# Get the public URL
railway domain

# Test it
curl https://your-app.up.railway.app/

# Open in browser
open https://your-app.up.railway.app/
```

## Step 6: Custom Domain (Optional)

```bash
# Add a custom domain
railway domain add help-agent.yourdomain.com

# Then add a CNAME record in your DNS:
# help-agent.yourdomain.com -> your-app.up.railway.app
```

---

## Step 7: Deploy Simulator Service (Optional)

The simulator runs as a separate Railway service that generates realistic traffic at a configurable cadence. This produces a steady stream of traced conversations in Braintrust for error analysis.

### Create a new service in Railway

In the Railway dashboard:
1. Click "New" -> "Service" -> "From Repo" (same repo)
2. Set the **Dockerfile path** to `Dockerfile.simulator`
3. Set the **Start command** to `python -m simulator.service` (or leave default from Dockerfile)

### Set environment variables

Same DB and API credentials as the agent, plus simulator-specific config:

```bash
# Same as agent service
railway variables set DATABASE_URL="$RAILWAY_DATABASE_URL" --service simulator
railway variables set BRAINTRUST_API_KEY="sk-your-key" --service simulator
railway variables set CLASSIFIER_MODEL="claude-haiku-4-5" --service simulator
railway variables set EXECUTOR_MODEL="claude-sonnet-4-5" --service simulator
railway variables set EMBEDDING_MODEL="text-embedding-3-small" --service simulator

# Simulator-specific
railway variables set SIMULATOR_CADENCE="300" --service simulator      # 5 min between batches
railway variables set SIMULATOR_BATCH_SIZE="5" --service simulator      # 5 conversations per batch
railway variables set SIMULATOR_CONCURRENCY="3" --service simulator     # 3 concurrent
railway variables set SIMULATOR_MODEL="gpt-5-nano" --service simulator  # cheap sim model
railway variables set SIMULATOR_ENABLED="true" --service simulator      # set to "false" to pause
```

### Cost for simulator

With default settings (5 conversations every 5 minutes):
- ~1,440 conversations/day × $0.03/conversation = **~$43/day**
- That's high for continuous use. Recommended production settings:

| Setting | Low traffic | Medium | High |
|---|---|---|---|
| `SIMULATOR_CADENCE` | 3600 (1hr) | 600 (10min) | 300 (5min) |
| `SIMULATOR_BATCH_SIZE` | 2 | 3 | 5 |
| Conversations/day | ~48 | ~432 | ~1,440 |
| LLM cost/day | ~$1.50 | ~$13 | ~$43 |
| Compute cost/day | ~$0.50 | ~$1 | ~$2 |

For error analysis, **low traffic (1 batch per hour)** is usually sufficient. You can temporarily increase the cadence when you want more data.

### Pause/Resume

```bash
# Pause without deleting
railway variables set SIMULATOR_ENABLED="false" --service simulator

# Resume
railway variables set SIMULATOR_ENABLED="true" --service simulator
```

---

## Updating the Deployment

```bash
# After making changes locally:
git add -A && git commit -m "update"
railway up

# Or connect GitHub for auto-deploy:
# In Railway dashboard -> Settings -> Connect GitHub repo
# Every push to main will auto-deploy
```

## Monitoring

- **Railway dashboard**: CPU, memory, network usage per service
- **Braintrust dashboard**: Trace logs, token usage, latency
- **Logs**: `railway logs` or view in dashboard

## Troubleshooting

| Issue | Fix |
|---|---|
| `pgvector extension not found` | Run `CREATE EXTENSION IF NOT EXISTS vector;` on Railway Postgres |
| `DATABASE_URL not set` | Link the Postgres service to the app service in Railway dashboard |
| Port issues | Ensure `PORT=8000` env var is set; Chainlit reads from this |
| Connection refused | Check Railway's internal networking; services communicate via internal hostnames |
| Slow cold starts | Railway sleeps idle services; first request after idle takes longer |
