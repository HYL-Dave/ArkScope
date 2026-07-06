# ArkScope: PostgreSQL — archive access only

> **The app does NOT need docker.** ArkScope's runtime is local-first
> (SQLite/DuckDB under `data/`); the PG exit completed 2026-07-05 and PostgreSQL
> holds only frozen archives. This compose exists for exactly one purpose:
> **restoring / inspecting `data/pg_archive/*` dumps** (and reading the three
> remaining archive tables: `agent_queries`, `research_reports`,
> `agent_memories`). If you are setting up ArkScope for development, skip this
> directory entirely — see the root `README.md` quickstart.

## Start (requires an explicit password — no default)

```bash
cd docker/
ARKSCOPE_ARCHIVE_PG_PASSWORD=<archive-pg-password> docker compose up -d
docker compose ps          # STATUS should be "healthy"
```

The compose refuses to start without `ARKSCOPE_ARCHIVE_PG_PASSWORD` — no
password is stored in this repo. Schema auto-initializes from `../sql/` on
first startup (schema lineage record).

| Variable | Default | Description |
|----------|---------|-------------|
| `ARKSCOPE_ARCHIVE_PG_PASSWORD` | *(required)* | Archive DB password |
| `POSTGRES_PORT` | `15432` | Host port mapping |

## Restore an archive dump (two-stage proof pattern)

Mirrors the PG-exit gate CLIs (`scripts/migration/n9_*.py`): restore into a
scratch database, verify presence, then inspect — never restore over a live DB.

```bash
# 1. Create a scratch DB and restore the dump into it
#    (dump filenames differ per batch — read the "dump_file" field in the
#     batch's manifest.json: n9_batch1.dump / n9_batch3_prices.dump /
#     app_records.dump / ...)
docker exec -i mindfulrl-postgres createdb -U postgres archive_scratch
docker exec -i mindfulrl-postgres pg_restore -U postgres -d archive_scratch \
  < ../data/pg_archive/<batch-dir>/<dump-file-from-manifest>

# 2. Apply any archived function DDL (batch-3+ archives carry function_ddl.sql)
docker exec -i mindfulrl-postgres psql -U postgres -d archive_scratch \
  < ../data/pg_archive/<batch-dir>/function_ddl.sql   # if present

# 3. Inspect, then drop the scratch DB when done
docker exec -it mindfulrl-postgres psql -U postgres -d archive_scratch -c "\dt"
docker exec -i mindfulrl-postgres dropdb -U postgres archive_scratch
```

Each `data/pg_archive/<batch-dir>/` carries its own manifest + sha256; verify
the dump checksum against the manifest before trusting a restore.

> **The original remote PG instance was STOPPED on 2026-07-06** after the three
> app-record archive tables were dumped to
> `data/pg_archive/app_records_20260706T121127Z/` (with restore proof). There is
> no live ArkScope PG anywhere; this compose + the dumps are the complete
> archive story.

## Password rotation

The pre-2026-07 dev password was published and is COMPROMISED
(`docs/PUBLICATION_REVIEW.md`). Rotation runbook (user-executed):

```bash
docker exec -it mindfulrl-postgres psql -U postgres -d mindfulrl \
  -c "ALTER USER postgres PASSWORD '<new-password>';"
```

Then update `config/.env` `DATABASE_URL` (if set) and any MCP postgres server
config. The new password lives only in your private environment — never in
tracked files.

## Troubleshooting

```bash
docker compose logs -f postgres
docker exec -it mindfulrl-postgres psql -U postgres -d mindfulrl
docker compose down          # stop (keeps the volume)
docker compose down -v       # reset — destroys the archive volume!
```
