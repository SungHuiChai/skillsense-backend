# Database Migrations

This directory contains database migration scripts for the SkillSense backend.

## Migration Files

- `001_add_gpt_data_collection.py` - Adds GPT-enhanced data collection fields
  - Adds `readme_samples`, `commit_samples`, `commit_statistics` to `github_data` table
  - Creates `linkedin_data` table for LinkedIn profile data

## Running Migrations

### Apply All Migrations
```bash
python migrations/run_migrations.py
```

### Rollback All Migrations
```bash
python migrations/run_migrations.py --downgrade
```

### Run Single Migration
```bash
python migrations/001_add_gpt_data_collection.py
```

## Creating New Migrations

1. Create a new file with format `00X_description.py`
2. Implement `upgrade(engine)` and `downgrade(engine)` functions
3. Use `column_exists()` and `table_exists()` helper functions to make migrations idempotent
4. Test the migration locally before deploying

## Migration Structure

```python
def upgrade(engine):
    """Apply migration"""
    with engine.connect() as conn:
        # Add columns, create tables, etc.
        conn.execute(text("ALTER TABLE ..."))
        conn.commit()

def downgrade(engine):
    """Rollback migration"""
    with engine.connect() as conn:
        # Remove changes
        conn.execute(text("DROP TABLE ..."))
        conn.commit()
```

## Best Practices

- Always check if columns/tables exist before creating
- Use transactions for atomic operations
- Add proper indexes for foreign keys
- Document all changes in migration docstring
- Test both upgrade and downgrade paths
