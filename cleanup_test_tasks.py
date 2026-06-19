"""Remove tasks created by automated test runs (after 20:00 UTC on 2026-06-11)."""
import os
import requests

H = {"Authorization": "Bearer " + os.environ["SUPABASE_PAT"],
     "Content-Type": "application/json"}
U = "https://api.supabase.com/v1/projects/rqdhaphfyitvtckdjgqg/database/query"

sql = ("delete from tasks where user_id=584321397 "
       "and title in ('Call Mom','Buy Groceries','Water plants','Meditation Task','Stretch Break','Water the Plants') "
       "and created_at > '2026-06-11 20:00:00+00' returning title")
r = requests.post(U, json={"query": sql}, headers=H)
print(r.status_code, r.text)
