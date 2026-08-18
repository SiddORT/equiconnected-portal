"""
Secure one-time admin seed script.

Usage:
    cd backend
    ADMIN_EMAIL=admin@example.com ADMIN_PASSWORD=changeme123 python scripts/seed_admin.py

Environment variables required:
    ADMIN_EMAIL     — admin account email
    ADMIN_PASSWORD  — admin account password (min 12 chars)
    DATABASE_URL    — PostgreSQL connection string (auto-set by Replit)

This script is idempotent: running it twice will not create a duplicate admin.
Credentials must NEVER be passed as command-line arguments or hard-coded.
"""
import os
import sys

# Allow running from the backend/ directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import get_settings  # noqa: E402
from app.core.logging import configure_logging, get_logger  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.repositories.user_repository import UserRepository  # noqa: E402

configure_logging()
logger = get_logger(__name__)


def main() -> None:
    email = os.environ.get("ADMIN_EMAIL", "").strip().lower()
    password = os.environ.get("ADMIN_PASSWORD", "")

    if not email:
        logger.error("seed.missing_env", var="ADMIN_EMAIL")
        sys.exit(1)
    if len(password) < 12:
        logger.error("seed.password_too_short", min_length=12)
        sys.exit(1)

    db = SessionLocal()
    try:
        repo = UserRepository(db)

        # Ensure admin role exists
        role = repo.get_role_by_name("admin")
        if role is None:
            logger.info("seed.creating_role", role="admin")
            role = repo.create_role("admin", description="Full system administrator")

        # Check if admin already exists
        existing = repo.get_by_email(email)
        if existing is not None:
            logger.info("seed.admin_exists", email=email)
            print(f"Admin user already exists: {email}")
            return

        # Create admin user
        password_hash = hash_password(password)
        user = repo.create_user(
            email=email,
            password_hash=password_hash,
            role=role,
            first_name=os.environ.get("ADMIN_FIRST_NAME"),
            last_name=os.environ.get("ADMIN_LAST_NAME"),
        )
        repo.commit()

        logger.info("seed.admin_created", user_id=str(user.id), email=email)
        print(f"✓ Admin user created: {email} (id={user.id})")

    except Exception as exc:
        db.rollback()
        logger.error("seed.failed", error=str(exc))
        print(f"✗ Seed failed: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
