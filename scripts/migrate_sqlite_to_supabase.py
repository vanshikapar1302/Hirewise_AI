import os
import sys
import sqlite3
from pathlib import Path
from dotenv import load_dotenv

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Load environment variables
load_dotenv(PROJECT_ROOT / ".env")

import psycopg2
from psycopg2.extras import RealDictCursor

def migrate():
    print("=" * 80)
    print("                  HIREWISE AI - SQLITE TO SUPABASE MIGRATION                  ")
    print("=" * 80)

    sqlite_db_path = PROJECT_ROOT / "database" / "hirewise.db"
    if not sqlite_db_path.exists():
        print(f"[ERROR] SQLite database file not found at: {sqlite_db_path}")
        return

    postgres_url = os.environ.get("DATABASE_URL")
    if not postgres_url:
        print("[ERROR] DATABASE_URL environment variable is missing.")
        return

    if postgres_url.startswith("postgres://"):
        postgres_url = postgres_url.replace("postgres://", "postgresql://", 1)

    print(f"Source SQLite database: {sqlite_db_path}")
    print(f"Target PostgreSQL database URL: {postgres_url}")

    # Connect to SQLite
    conn_sq = sqlite3.connect(sqlite_db_path)
    conn_sq.row_factory = sqlite3.Row
    cursor_sq = conn_sq.cursor()

    # Connect to PostgreSQL
    try:
        conn_pg = psycopg2.connect(postgres_url)
        cursor_pg = conn_pg.cursor()
        print("[SUCCESS] Connected to Supabase PostgreSQL database.")
    except Exception as e:
        print(f"[ERROR] Failed to connect to PostgreSQL: {e}")
        return

    # Tables to migrate in topological order (dependency order)
    tables_to_migrate = [
        "roles",
        "users",
        "resume_uploads",
        "chat_sessions",
        "chat_messages",
        "practice_history",
        "interview_sessions",
        "responses",
        "performance_reports",
        "system_logs",
        "api_logs",
        "admin_logs"
    ]

    report = []
    has_errors = False

    try:
        # Disable foreign key checks temporarily during bulk loading if possible, 
        # but since we migrate in topological order, we shouldn't violate constraints.
        
        # Clear existing data in target tables to avoid duplicate key conflicts (if any)
        # We delete in reverse topological order
        print("\n--- Clearing existing data in target PostgreSQL tables ---")
        for table in reversed(tables_to_migrate):
            try:
                cursor_pg.execute(f"DELETE FROM {table};")
                print(f"Cleared table: {table}")
            except Exception as e:
                conn_pg.rollback()
                print(f"[WARNING] Could not clear table {table}: {e}")

        conn_pg.commit()

        print("\n--- Migrating tables ---")
        for table in tables_to_migrate:
            print(f"Migrating table: {table} ...")
            
            # 1. Fetch column definitions from SQLite to build queries
            cursor_sq.execute(f"PRAGMA table_info({table})")
            columns = [col[1] for col in cursor_sq.fetchall()]
            
            if not columns:
                print(f"[WARNING] Table '{table}' does not exist or has no columns in SQLite.")
                continue

            col_str = ", ".join(columns)
            placeholders = ", ".join(["%s"] * len(columns))

            # 2. Fetch rows from SQLite
            cursor_sq.execute(f"SELECT {col_str} FROM {table}")
            rows = cursor_sq.fetchall()
            row_count = len(rows)

            if row_count == 0:
                print(f"Table '{table}' has 0 rows in SQLite. Skipping insert.")
                report.append((table, 0, 0, "PASS"))
                continue

            # 3. Bulk insert into PostgreSQL
            insert_query = f"INSERT INTO {table} ({col_str}) VALUES ({placeholders})"
            inserted_count = 0
            
            # Fetch boolean columns for this table in PostgreSQL to handle strict boolean coercion
            cursor_pg.execute("""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name = %s AND data_type = 'boolean'
            """, (table,))
            boolean_cols = {r[0] for r in cursor_pg.fetchall()}

            for row in rows:
                values = []
                for col in columns:
                    val = row[col]
                    if col in boolean_cols and val is not None:
                        if val in (1, '1', True):
                            values.append(True)
                        elif val in (0, '0', False):
                            values.append(False)
                        else:
                            values.append(bool(val))
                    else:
                        values.append(val)
                
                try:
                    cursor_pg.execute(insert_query, values)
                    inserted_count += 1
                except Exception as row_error:
                    conn_pg.rollback()
                    print(f"[ERROR] Failed to insert row into '{table}': {row_error}")
                    print(f"Values: {values}")
                    has_errors = True
                    break
            
            if not has_errors:
                conn_pg.commit()
                print(f"[SUCCESS] Migrated {inserted_count}/{row_count} rows for table '{table}'")
                
                # 4. Reset PostgreSQL auto-incrementing serial sequence
                try:
                    # check if the table has an id sequence
                    cursor_pg.execute(f"""
                        SELECT pg_get_serial_sequence('{table}', 'id');
                    """)
                    seq_name = cursor_pg.fetchone()[0]
                    if seq_name:
                        cursor_pg.execute(f"""
                            SELECT setval('{seq_name}', COALESCE(MAX(id), 1)) FROM {table};
                        """)
                        conn_pg.commit()
                        print(f"Reset sequence '{seq_name}' successfully.")
                except Exception as seq_err:
                    conn_pg.rollback()
                    # Non-critical, some tables may not have sequence
                    pass

                report.append((table, row_count, inserted_count, "PASS"))
            else:
                report.append((table, row_count, inserted_count, "FAIL"))
                break

    except Exception as e:
        conn_pg.rollback()
        print(f"[CRITICAL ERROR] Migration pipeline failed: {e}")
        has_errors = True
    finally:
        conn_sq.close()
        conn_pg.close()

    print("\n" + "=" * 80)
    print("                           MIGRATION VERIFICATION REPORT                      ")
    print("=" * 80)
    print(f"{'Table Name':<25} | {'SQLite Rows':<15} | {'Postgres Rows':<15} | {'Status':<10}")
    print("-" * 80)
    for table, sq_cnt, pg_cnt, status in report:
        print(f"{table:<25} | {sq_cnt:<15} | {pg_cnt:<15} | {status:<10}")
    print("=" * 80)

    if not has_errors:
        print("\n[SUCCESS] SQLite to Supabase PostgreSQL database migration completed successfully!")
    else:
        print("\n[FAIL] Migration encountered errors. Please check the logs above.")

if __name__ == "__main__":
    migrate()
