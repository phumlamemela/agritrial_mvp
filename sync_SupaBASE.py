import os
import sqlite3

from dotenv import load_dotenv
from supabase import create_client

BASE = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE, ".env"))

DB_PATH = os.path.join(BASE, "canola.db")

# Parents first, children after
TABLES = ["trial", "trial_sites", "treatment", "assessment_traits",
          "plots", "assessment_data", "measurement"]
BATCH = 500   # rows sent per request

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")

if not url or not key:
    raise SystemExit("Set SUPABASE_URL and SUPABASE_KEY in your .env file first.")

supabase = create_client(url, key)

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

for table in TABLES:
    rows = [dict(r) for r in conn.execute(f"SELECT * FROM {table}")]

    for i in range(0, len(rows), BATCH):
        supabase.table(table).upsert(rows[i:i + BATCH]).execute()

    remote = supabase.table(table).select("*", count="exact").limit(1).execute().count
    status = "OK" if remote == len(rows) else "MISMATCH"
    print(f"{table}: local {len(rows)}, Supabase {remote} -> {status}")

conn.close()
