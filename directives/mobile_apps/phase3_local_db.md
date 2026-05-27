# Phase 3 — Local SQLite Database

## Goal

Replace AsyncStorage with `expo-sqlite` for any data that's relational, large, or queried by predicate. Ship raw SQL CRUD wrappers (no ORM) plus an auto-migration runner driven by `PRAGMA user_version`. Migrations run on every app start; schema drift between dev and prod becomes impossible.

## Inputs

- Phase 1 + 2 complete (AsyncStorage + axios client working)
- Schema requirements from the app spec — which entities, which columns, which indices
- Per-app repo at `C:\Users\deban\dev\mobile-apps\<slug>\`

## Tools/Scripts

- `expo-sqlite` — official Expo SQLite binding
- `src/db/schema.sql` — versioned schema as raw SQL (single source of truth)
- `src/db/migrate.ts` — migration runner, called from `App.tsx` on mount
- `src/db/<entity>.ts` — typed CRUD wrappers per table (e.g. `tasks.ts` exports `insertTask`, `listTasks`, `updateTask`, `deleteTask`)

## Steps

1. **Install.** `npx expo install expo-sqlite`. Use `expo install`, not `npm install` — native binding must match Expo SDK.
2. **Author schema.** `src/db/schema.sql` — one CREATE TABLE per entity, with explicit types, NOT NULL where appropriate, foreign keys with ON DELETE CASCADE. End with `PRAGMA user_version = N;` (start at 1).
3. **Write `migrate.ts`.**
   - Open the DB via `SQLite.openDatabaseAsync('<slug>.db')`.
   - Read current version: `await db.getFirstAsync<{user_version: number}>('PRAGMA user_version')`.
   - If current < target: execute migrations in order (see step 4) inside a transaction. On any error, ROLLBACK and throw — never partially-migrate.
   - On success, set `PRAGMA user_version = <target>` inside the same transaction.
4. **Versioned migrations.** `src/db/migrations/001_initial.sql`, `002_add_index_on_tasks_created_at.sql`, etc. Each file is idempotent CREATE-IF-NOT-EXISTS plus the schema delta for that version. `migrate.ts` loads them in order, runs all between current+1 and target.
5. **CRUD wrappers.** For each entity, `src/db/<entity>.ts`:
   ```ts
   export async function insertTask(t: Omit<Task, 'id'>): Promise<Task> { ... }
   export async function listTasks(filter?: TaskFilter): Promise<Task[]> { ... }
   ```
   Use parameterized queries (`db.runAsync('INSERT ... VALUES (?, ?)', [...])`). Never string-interpolate user input.
6. **Migrate AsyncStorage data on first SQLite boot.** If `app_state` exists in AsyncStorage, parse it, write to SQLite, then `AsyncStorage.removeItem('app_state')`. One-shot data migration. Log to console; never silently lose data.
7. **Update Context.** `src/state/Context.tsx` now reads from SQLite via the CRUD wrappers instead of AsyncStorage. The provider can either cache a snapshot in memory + invalidate on mutation, or treat SQLite as the single source (re-query on every render — fine for small tables).
8. **Boot test.** Cold install: `npx expo start --clear`. Confirm schema created, version = N. Insert sample data, kill app, reopen, confirm rows persisted.
9. **Migration test.** Bump schema to version N+1 (add a column via `ALTER TABLE`), confirm app boots, new column populated, no data loss.
10. **Commit.** `git commit -m "phase 3 — expo-sqlite with auto-migration"`.

## Outputs

- `src/db/schema.sql` — versioned schema
- `src/db/migrate.ts` — migration runner
- `src/db/migrations/<NNN>_<name>.sql` — one file per schema version
- `src/db/<entity>.ts` — CRUD wrappers (one per entity)
- AsyncStorage drained on first SQLite boot
- Phase 3 commit in the app repo

## Edge Cases

- **Migration failure rollback.** Transaction wraps every migration step. If `002_add_column.sql` throws, ROLLBACK keeps the DB at version 1 — the app boots in degraded mode (still on old schema) but never corrupted. Log loudly; surface to the user as a non-recoverable error banner.
- **Schema drift dev vs prod.** Without migrations, devs add columns locally that prod never gets. The version pragma + ordered migration files makes this impossible — every install runs the same sequence.
- **Concurrent migrations.** Expo apps are single-process; no concurrent migration risk. But if the user kills the app mid-migration, the next boot re-runs the same migration (it must be idempotent). Test by force-killing during step 9.
- **Foreign-key enforcement.** SQLite defaults FK enforcement to OFF. Enable per-connection: `PRAGMA foreign_keys = ON;` at the top of `migrate.ts` after openDatabase.
- **Date columns.** SQLite has no native DATETIME. Store as ISO 8601 TEXT (`'2026-05-27T14:33:00Z'`) or Unix epoch INTEGER. Pick one project-wide and document it in `schema.sql` comments.
- **`.db` file size on iOS.** Apple may prompt the user about "large app data" above ~50 MB. For photo-heavy or transcript-heavy apps, store binaries on the CF Worker's R2 (Phase 4a) and keep SQLite for metadata only.
- **Reset for dev.** `expo-sqlite` does NOT clear the DB on Metro reload. To start fresh: `npx expo start --clear` only clears bundler cache; the DB persists on the device. Manually delete in Expo Go: settings → app → clear data, or uninstall.
- **`PRAGMA user_version` is 0 by default.** First boot: current=0, target=1, run 001_initial.sql. Subsequent boots: current=1, target=1, skip.

## Notes

- Raw SQL > ORM here. Drizzle / Prisma / TypeORM add native deps, weight, and another schema source of truth. The 3-layer pattern says deterministic, simple, debuggable wins.
- Migrations are append-only. Never edit `001_initial.sql` after it ships — write `002_*.sql` instead. Edits cause silent drift on devices that already ran the old version.
- Anneal classic mode runs after this phase via the `/mobile-app` skill.
