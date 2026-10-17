import os
import sqlite3
from supabase import create_client
 
BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE, "canola.db")
 
# Parents first, children after 
TABLES = ["trial", "trial_sites", "treatment", "assessment_traits",
          "plots", "assessment_data", "measurement"]
BATCH = 500   # rows sent per request
 
url_ii = "https://tvwglonppmlggjmyyzyn.supabase.co"
key = "sb_secret_uBxS186f-Y0077l9pw9nUg_dwAHq7bh"

if not url_ii or not key:
    raise SystemExit("Set SUPABASE_URL and SUPABASE_KEY first.")
 
supabase = create_client(url_ii, key)
 
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row      #turn each row into a dictionary
 
for table in TABLES:
    rows = [dict(r) for r in conn.execute(f"SELECT * FROM {table}")]
 
    #insert new rows, update rows whose primary key already exists
    for i in range(0, len(rows), BATCH):
        supabase.table(table).upsert(rows[i:i + BATCH]).execute()
 
    #count the rows now in Supabase
    remote = supabase.table(table).select("*", count="exact").limit(1).execute().count
    status = "OK" if remote == len(rows) else "MISMATCH"
    print(f"{table}: local {len(rows)}, Supabase {remote} -> {status}")
 
conn.close()
