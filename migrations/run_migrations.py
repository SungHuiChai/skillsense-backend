"""
Migration runner for SkillSense database migrations

Usage:
    python migrations/run_migrations.py              # Run all migrations
    python migrations/run_migrations.py --downgrade  # Rollback all migrations
"""

import sys
import logging
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import engine

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_migration_files():
    """Get all migration files in order"""
    migrations_dir = Path(__file__).parent
    migration_files = sorted([
        f for f in migrations_dir.glob("*.py")
        if f.name.startswith("00") and f.name != "__init__.py"
    ])
    return migration_files


def run_migrations(downgrade=False):
    """Run all migrations"""
    migration_files = get_migration_files()

    if not migration_files:
        logger.warning("No migration files found")
        return

    logger.info(f"Found {len(migration_files)} migration(s)")

    for migration_file in migration_files:
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing: {migration_file.name}")
        logger.info(f"{'='*60}")

        try:
            # Import migration module dynamically
            module_name = migration_file.stem
            spec = __import__(f"migrations.{module_name}", fromlist=['upgrade', 'downgrade'])

            if downgrade:
                if hasattr(spec, 'downgrade'):
                    spec.downgrade(engine)
                else:
                    logger.warning(f"No downgrade function in {migration_file.name}")
            else:
                if hasattr(spec, 'upgrade'):
                    spec.upgrade(engine)
                else:
                    logger.error(f"No upgrade function in {migration_file.name}")

        except Exception as e:
            logger.error(f"Failed to run migration {migration_file.name}: {e}")
            raise

    logger.info(f"\n{'='*60}")
    logger.info("✅ All migrations completed!")
    logger.info(f"{'='*60}\n")


if __name__ == "__main__":
    downgrade = "--downgrade" in sys.argv or "-d" in sys.argv

    if downgrade:
        logger.warning("⚠️  Running in DOWNGRADE mode - this will rollback changes!")
        confirm = input("Are you sure you want to continue? (yes/no): ")
        if confirm.lower() != "yes":
            logger.info("Cancelled")
            sys.exit(0)

    try:
        run_migrations(downgrade=downgrade)
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        sys.exit(1)
