"""
Database Initialization Script for MindVault AI Backend
Usage:
    python init_db.py
"""

import sys
from app.config import settings
from app.database import engine, Base
import app.models  # Ensures all models are registered with Base.metadata


def main():
    print("=" * 60)
    print("MindVault AI — Database Initialization")
    print("=" * 60)
    print(f"Connecting to database: {settings.DATABASE_URL.split('@')[-1] if '@' in settings.DATABASE_URL else settings.DATABASE_URL}")

    try:
        # If using PostgreSQL, verify if database exists or create it
        if settings.DATABASE_URL.startswith("postgresql"):
            import psycopg2
            from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
            from urllib.parse import urlparse

            parsed = urlparse(settings.DATABASE_URL)
            db_name = parsed.path.lstrip("/")
            
            # Connect to default 'postgres' database to check/create target database
            admin_conn = psycopg2.connect(
                dbname="postgres",
                user=parsed.username,
                password=parsed.password,
                host=parsed.hostname or "localhost",
                port=parsed.port or 5432,
            )
            admin_conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            with admin_conn.cursor() as cur:
                cur.execute("SELECT 1 FROM pg_database WHERE datname = %s;", (db_name,))
                if not cur.fetchone():
                    cur.execute(f'CREATE DATABASE "{db_name}";')
                    print(f"Created database '{db_name}' successfully.")
            admin_conn.close()

        # Create all tables defined in models
        Base.metadata.create_all(bind=engine)
        print("\nSuccessfully connected and created all database tables:")
        for table_name in Base.metadata.tables.keys():
            print(f"  - {table_name}")
        print("\nDatabase is ready for use!")
    except Exception as e:
        print(f"\n[ERROR] Failed to initialize database: {e}", file=sys.stderr)
        print("\nTroubleshooting tips:", file=sys.stderr)
        print("1. If using PostgreSQL, ensure PostgreSQL service is running and user credentials in backend/.env are correct.", file=sys.stderr)
        print("2. To use local SQLite instead, set DATABASE_URL=sqlite:///./mindvault.db in backend/.env", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
