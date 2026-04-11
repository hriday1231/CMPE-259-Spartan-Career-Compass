import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psycopg2
from config import DATABASE_URL, PROJECT_ROOT


def main():
    schema_path = PROJECT_ROOT / "schema.sql"
    if not schema_path.exists():
        print("schema.sql not found at", schema_path)
        sys.exit(1)
    sql = schema_path.read_text(encoding="utf-8")
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(sql)
    cur.close()
    conn.close()
    print("Schema applied successfully.")


if __name__ == "__main__":
    main()
