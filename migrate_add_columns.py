"""
VEKTOR — Add missing Product columns migration
Run ONCE from your project root:

    python migrate_add_columns.py

Safe to run multiple times — skips columns that already exist.
"""

import sqlite3
import os

# ── Point this at your actual DB file ────────────────────
DB_PATH = os.path.join(os.path.dirname(__file__), "database", "vektor.db")
# If your DB is elsewhere, change the path above.
# Common locations: "instance/vektor.db", "vektor.db", "database/vektor.db"

NEW_COLUMNS = [
    # (column_name,        sql_type_and_default)
    ("name_mr",            "VARCHAR(200)"),
    ("description_mr",     "TEXT"),
    ("tagline_sk",         "VARCHAR(200)"),
    ("collection",         "VARCHAR(100)"),
    ("season",             "VARCHAR(50)  DEFAULT 'SS/26'"),
    ("sku",                "VARCHAR(100)"),
    ("low_stock",          "INTEGER DEFAULT 10"),
    ("save_text",          "VARCHAR(100)"),
    ("tax_info",           "VARCHAR(150)"),
    ("badge",              "VARCHAR(50)"),
]

def migrate():
    if not os.path.exists(DB_PATH):
        print(f"❌ DB not found at: {DB_PATH}")
        print("   Edit DB_PATH in this script to point to your vektor.db file.")
        return

    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()

    # Get existing columns
    cur.execute("PRAGMA table_info(products)")
    existing = {row[1] for row in cur.fetchall()}
    print(f"✅ Connected to: {DB_PATH}")
    print(f"   Existing columns: {len(existing)}")

    added = 0
    for col_name, col_type in NEW_COLUMNS:
        if col_name in existing:
            print(f"   ⏭  SKIP  {col_name} (already exists)")
        else:
            sql = f"ALTER TABLE products ADD COLUMN {col_name} {col_type}"
            cur.execute(sql)
            print(f"   ✅ ADDED {col_name}  ({col_type})")
            added += 1

    conn.commit()
    conn.close()

    print(f"\n{'✅ Done!' if added else '✅ Nothing to do.'} {added} column(s) added.")
    if added:
        print("   Restart your Flask app now.")

if __name__ == "__main__":
    migrate()