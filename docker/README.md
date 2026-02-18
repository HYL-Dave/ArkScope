# MindfulRL-Intraday: PostgreSQL + pgvector

## Quick Start

```bash
# On the DB machine (remote):
cd docker/
docker compose up -d

# Check status:
docker compose ps          # STATUS should be "healthy"
docker exec mindfulrl-postgres pg_isready -U postgres -d mindfulrl

# Verify tables (should see 7 tables):
docker exec mindfulrl-postgres psql -U postgres -d mindfulrl -c "\dt"
```

Default connection string:
```
postgresql://postgres:mindfulrl_dev_2026@<DB_HOST>:15432/mindfulrl
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_PASSWORD` | `mindfulrl_dev_2026` | Database password |
| `POSTGRES_PORT` | `15432` | Host port mapping |

Override via environment:
```bash
POSTGRES_PORT=25432 POSTGRES_PASSWORD=my_secret docker compose up -d
```

## Schema

Tables are auto-created on first startup from `sql/` directory:
- `001_init_schema.sql` — news, prices, iv_history, fundamentals, signals, agent_queries
- `002_add_news_scores.sql` — news_scores (multi-model scoring) + news_latest_scores view

Extensions: `pgvector` (semantic search ready), `pg_trgm` (text search).

## Backup & Restore

### Backup

```bash
# Option A: Via docker exec (no local pg_dump needed)
ssh user@<DB_HOST> "docker exec mindfulrl-postgres pg_dump -U postgres -Fc mindfulrl" > backup.dump

# Option B: Local pg_dump (if installed)
pg_dump -h <DB_HOST> -p 15432 -U postgres -Fc mindfulrl > backup.dump

# Check size
ls -lh backup.dump
```

### Restore

```bash
# On the new machine, start a fresh container first:
docker compose up -d

# Wait for healthy, then restore:
docker exec -i mindfulrl-postgres pg_restore -U postgres -d mindfulrl --clean --if-exists < backup.dump
```

## Migration to Another Machine

1. **Backup** current data (see above)
2. **Copy files** to new machine:
   ```bash
   scp -r docker/ sql/ user@new-host:/path/to/mindfulrl/
   scp backup.dump user@new-host:/tmp/
   ```
3. **Start container** on new machine:
   ```bash
   ssh user@new-host
   cd /path/to/mindfulrl/docker
   docker compose up -d
   ```
4. **Restore** data:
   ```bash
   docker exec -i mindfulrl-postgres pg_restore -U postgres -d mindfulrl --clean --if-exists < /tmp/backup.dump
   ```
5. **Update** `config/.env` on dev machine with new `DATABASE_URL`

## Firewall

If the DB machine has a firewall, allow inbound on the configured port:
```bash
sudo ufw allow 15432/tcp
```

## Troubleshooting

```bash
# View logs
docker compose logs -f postgres

# Connect interactively
docker exec -it mindfulrl-postgres psql -U postgres -d mindfulrl

# Check disk usage
docker exec mindfulrl-postgres psql -U postgres -d mindfulrl \
  -c "SELECT pg_size_pretty(pg_database_size('mindfulrl'))"

# Reset (destroys all data!)
docker compose down -v
docker compose up -d
```