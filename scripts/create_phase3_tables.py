#!/usr/bin/env python3
"""
Create Phase 3 database tables:
- stackoverflow_data
- skill_web_mentions
"""
import sys
import os

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import engine, Base
from app.models.collected_data import StackOverflowData, SkillWebMention


def create_phase3_tables():
    """Create Phase 3 tables if they don't exist"""
    print("=" * 60)
    print("Creating Phase 3 Tables")
    print("=" * 60)

    # Import all models to ensure they're registered
    from app.models import collected_data

    try:
        # Check if tables already exist
        from sqlalchemy import inspect
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()

        print(f"\nExisting tables: {len(existing_tables)}")
        for table in existing_tables:
            print(f"  - {table}")

        # Create new tables
        print("\nCreating Phase 3 tables...")

        # This will only create tables that don't exist
        Base.metadata.create_all(bind=engine, checkfirst=True)

        # Check what was created
        inspector = inspect(engine)
        current_tables = inspector.get_table_names()

        print(f"\nTables after creation: {len(current_tables)}")

        # Check specifically for our new tables
        if "stackoverflow_data" in current_tables:
            print("  ✓ stackoverflow_data table created")
        else:
            print("  ✗ stackoverflow_data table NOT found")

        if "skill_web_mentions" in current_tables:
            print("  ✓ skill_web_mentions table created")
        else:
            print("  ✗ skill_web_mentions table NOT found")

        print("\n" + "=" * 60)
        print("Phase 3 Tables Created Successfully!")
        print("=" * 60)

        # Show table structures
        print("\nStackOverflow Data Columns:")
        for column in inspector.get_columns('stackoverflow_data'):
            print(f"  - {column['name']}: {column['type']}")

        print("\nSkill Web Mentions Columns:")
        for column in inspector.get_columns('skill_web_mentions'):
            print(f"  - {column['name']}: {column['type']}")

        return True

    except Exception as e:
        print(f"\n✗ Error creating tables: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = create_phase3_tables()
    sys.exit(0 if success else 1)
