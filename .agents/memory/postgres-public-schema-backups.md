---
name: PostgreSQL public-schema backup restoration
description: Why restoring a schema-scoped custom archive to a disposable database can fail.
---

# PostgreSQL public-schema backup restoration

When verifying a schema-scoped PostgreSQL dump by restoring it into a new
disposable database, account for the default `public` schema already existing
in that new database. A dump of `public` can contain `CREATE SCHEMA public`,
which fails with `--exit-on-error` unless the destination is truly empty.

**Why:** The development reset's test-schema restore succeeded while a real
`public`-schema restore failed even though its archive was readable. The
difference was the default schema in a freshly created PostgreSQL database.

**How to apply:** For a disposable restore target, remove the empty default
`public` schema before restoring a dump that includes it. Never do this to
the source or a populated database. Verify both restored contents and the
source's current snapshot before a destructive operation.

For a backup that gates a destructive data operation, matching table counts
does not establish snapshot equivalence. Compare a deterministic digest of
every row (and sequence state) between the source and the restored archive,
and recheck the source while writes are locked.

**Why:** A same-count row update or replacement can otherwise pass a
count-based backup guard while the modified data has no restorable copy.

**How to apply:** Keep raw values out of logs and manifests; compare digests
and reject a stale archive even if every table's count is unchanged.