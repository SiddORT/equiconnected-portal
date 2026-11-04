# Member account choices

Member sign-up offers:

| Choice | Stored role(s) | Profile flow |
| --- | --- | --- |
| Horse Owner | `horse_owner` | Personal information and horse profiles |
| Horse Rider | `horse_rider` | The same personal-information and horse-profile flow as Horse Owner |
| Stable Manager | `stable_manager` | Personal information and stable management |
| Both | `horse_owner`, `stable_manager` | Horse Owner and Stable Manager combined |

Horse Rider retains its own account label in profiles and admin member filters.
It shares the existing member registration, email verification, sign-in,
password recovery, and verified-member provider discovery flow. It does not
grant stable-management, provider-portal, or administrator privileges.
The existing “Both” option has not been redefined as a rider combination.

## Deployment

The new Alembic migration adds the `horse_rider` role without updating existing
accounts. Run the usual backend migration step before allowing rider sign-ups:

```bash
cd backend
alembic upgrade head
```

The administrator seed also includes the role for normal bootstrap consistency.
Do not reset or stamp migration history to add it. A migration downgrade is
blocked while any account still uses the rider role, to avoid deleting
assignments or locking users out.

Development migration and synthetic tests do not deploy these changes to UAT.
