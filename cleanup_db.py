"""Clean up test junk: duplicate tasks + breakdown step tasks."""
import sys
sys.path.insert(0, r'D:\Projects\learnix\bot')
from dotenv import load_dotenv
load_dotenv(r'D:\Projects\learnix\bot\.env')
import supabase_svc

sb = supabase_svc.get_client()
USER_ID = 584321397

tasks = sb.table("tasks").select("*").eq("user_id", USER_ID).execute().data
print(f"Total tasks: {len(tasks)}")

deleted = []
seen_titles = {}

for t in sorted(tasks, key=lambda x: x.get("created_at","")):
    title = t["title"]
    tid = t["id"]

    # Delete breakdown steps
    if " — Step " in title:
        sb.table("tasks").delete().eq("id", tid).execute()
        deleted.append(f"[STEP] {title}")
        continue

    # Delete duplicates (keep first seen)
    if title in seen_titles:
        sb.table("tasks").delete().eq("id", tid).execute()
        deleted.append(f"[DUP]  {title}")
    else:
        seen_titles[title] = tid

print(f"\nDeleted {len(deleted)}:")
for d in deleted:
    print(" ", d)

remaining = sb.table("tasks").select("title,status").eq("user_id", USER_ID).execute().data
print(f"\nRemaining ({len(remaining)}):")
for t in remaining:
    print(f"  [{t['status']}] {t['title']}")
