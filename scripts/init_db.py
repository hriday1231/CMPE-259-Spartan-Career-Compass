"""apply schema.sql to the sqlite database"""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import DB_PATH, PROJECT_ROOT


def main():
    schema_path = PROJECT_ROOT / "schema.sql"
    if not schema_path.exists():
        print("schema.sql not found at", schema_path)
        sys.exit(1)
    sql = schema_path.read_text(encoding="utf-8")
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    try:
        conn.executescript(sql)
        conn.commit()
    finally:
        conn.close()
    print(f"Schema applied successfully. DB: {DB_PATH}")


if __name__ == "__main__":
    main()
