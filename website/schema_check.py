from sqlalchemy import inspect
import os

def _has_column(engine, table: str, column: str) -> bool:
    insp = inspect(engine)
    try:
        cols = {c["name"] for c in insp.get_columns(table)}
    except Exception:
        return False
    return column in cols

def _ensure_column(engine, table: str, column: str, ddl: str):
    """
    Adds a column to an existing SQLite table if it's missing.
    Keep added columns NULLABLE or give them a DEFAULT.
    Example ddl: "ALTER TABLE users ADD COLUMN first_name VARCHAR(80)"
    """
    if not _has_column(engine, table, column):
        with engine.begin() as conn:
            conn.exec_driver_sql(ddl)

def _ensure_index(engine, name: str, ddl: str):
    """
    Create an index if it doesn't exist.
    Example ddl: "CREATE INDEX IF NOT EXISTS ix_events_start_cancel ON events (start_at, cancelled)"
    """
    with engine.begin() as conn:
        conn.exec_driver_sql(ddl)

def ensure_schema(engine):
    """
    Run all lightweight, safe, idempotent schema patches here.
    Call this after db.create_all().
    """

    _ensure_column(
        engine, "events", "is_active",
        "ALTER TABLE events ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1"
    )

    _ensure_column(
        engine, "users", "first_name",
        "ALTER TABLE users ADD COLUMN first_name VARCHAR(80)"
    )
    _ensure_column(
        engine, "users", "last_name",
        "ALTER TABLE users ADD COLUMN last_name VARCHAR(80)"
    )
    _ensure_column(
        engine, "users", "street_address",
        "ALTER TABLE users ADD COLUMN street_address VARCHAR(160)"
    )
    _ensure_column(
        engine, "users", "profile_pic_path",
        "ALTER TABLE users ADD COLUMN profile_pic_path VARCHAR(255)"
    )
    
    _ensure_column(
        engine, "events", "is_draft",
        "ALTER TABLE events ADD COLUMN is_draft INTEGER NOT NULL DEFAULT 0"
    )

    _ensure_index(
        engine, "ix_events_start_cancel",
        "CREATE INDEX IF NOT EXISTS ix_events_start_cancel ON events (start_at, cancelled)"
    )
    _ensure_index(
        engine, "ix_events_host_start",
        "CREATE INDEX IF NOT EXISTS ix_events_host_start ON events (host_user_id, start_at)"
    )
    _ensure_index(
        engine, "ix_bookings_user_created",
        "CREATE INDEX IF NOT EXISTS ix_bookings_user_created ON bookings (user_id, created_at DESC)"
    )
    _ensure_index(
        engine, "ix_bookings_event_status",
        "CREATE INDEX IF NOT EXISTS ix_bookings_event_status ON bookings (event_id, status)"
    )
    _ensure_index(
        engine, "ix_payments_booking_status",
        "CREATE INDEX IF NOT EXISTS ix_payments_booking_status ON payments (booking_id, status)"
    )
    _ensure_index(
        engine, "ix_tags_name",
        "CREATE INDEX IF NOT EXISTS ix_tags_name ON tags (name)"
    )
    _ensure_index(
        engine, "ix_tags_slug",
        "CREATE INDEX IF NOT EXISTS ix_tags_slug ON tags (slug)"
    )


def ensure_upload_dirs(static_folder: str):
    """Not DB, but handy: make sure profile upload dir exists."""
    os.makedirs(os.path.join(static_folder, "uploads", "profiles"), exist_ok=True)
