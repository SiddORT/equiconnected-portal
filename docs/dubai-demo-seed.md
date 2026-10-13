# Dubai demo provider seed

This is an **optional manual seed**, not part of deployment or startup.
It uses the application's existing root `.env` / process environment, database,
and contact-encryption configuration. It never creates keys, changes configuration,
runs migrations, resets data, creates user accounts, or sends invitations/emails.

## Run on your VPS

Use the same Python environment and repository checkout as your backend.
Run from the repository root after the normal deployment/database migrations:

```bash
# Preview the fixtures and visit dates; no database access or changes.
python backend/scripts/seed_dubai_providers.py

# Add the fixtures to the database configured for this checkout.
python backend/scripts/seed_dubai_providers.py --apply
```

From inside `backend/`, the equivalent command is:

```bash
python scripts/seed_dubai_providers.py --apply
```

No restart is required for database records to appear. Reload the admin provider
list, specialization master, or website. The public map shows active, published,
geocoded listings. Full directory/contact access still requires the application's
normal verified-member sign-in.

## What's included

- 3 hospitals: Al Marmoom, Jebel Ali, Dubai Academic City.
- 3 clinics: Al Quoz, Nad Al Sheba, Jumeirah.
- 3 doctors: Emirates Hills, Meydan, Al Barsha.
- 7 equine specializations, assigned across all provider types.
- All 9 listings active and published, with primary Dubai locations and
  approximate neighbourhood coordinates.
- 6 emergency-enabled demo listings: 2 hospitals, 2 clinics, and 2 doctors.
- 1 ongoing doctor and 2 visiting doctors, with complete date/location snapshots.
  The first trip runs from today minus 2 days through today plus 7 days;
  the second runs from today plus 14 days through today plus 23 days.
  “Today” uses Dubai time.
- Primary demo emails, non-working placeholder phone numbers, provider experience,
  and doctor biographies.

You may choose a visit calendar anchor for a reproducible first run:

```bash
python backend/scripts/seed_dubai_providers.py --apply --start-date 2026-10-13
```

All names, street addresses, experience, and contacts are fictional. Emergency
flags are for testing only. **These listings must not be used for real emergency
care.** The all-zero UAE phone placeholder is deliberately not a real subscriber
number; email addresses use the reserved `example.com` domain.
No photos, fake reviews, or real provider credentials are created.

## Reruns and safety

The command writes one transaction: failure rolls back the entire seed.
Concurrent runs are serialized by a PostgreSQL transaction advisory lock.
Stable demo IDs prevent duplicates even after an administrator renames a listing.
Existing demo providers are skipped completely; their edits, statuses, contacts,
specialization assignments, and original trip dates are preserved.

Existing active specializations are reused case-insensitively. An inactive required
specialization or a conflicting demo display name blocks the seed with a safe
message rather than silently modifying existing records.

Rerunning with a new `--start-date` does **not** refresh saved trips. Edit their dates
through admin when they expire. Because fixtures are published, run this only on a
test/UAT database where fictional listings are appropriate. The script does not
switch databases; confirm that the checkout uses your intended UAT configuration.

If encryption preflight blocks the seed, run:

```bash
python backend/scripts/check_contact_encryption.py
```

Fix the reported configuration issue using the application's existing keys;
do not generate replacement encryption material to make seeding pass.
