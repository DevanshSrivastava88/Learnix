import os
import requests
from collections import defaultdict

SUPABASE_URL = "https://rqdhaphfyitvtckdjgqg.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJxZGhhcGhmeWl0dnRja2RqZ3FnIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3OTgwODMzOCwiZXhwIjoyMDk1Mzg0MzM4fQ.p64a3TDYYSHxH3aBrNAYWy-fBBVNXDoMXs1N7FdlvwM"

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

def fetch_all_tasks():
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/tasks",
        headers=HEADERS,
        params={"select": "*", "order": "created_at.asc"}
    )
    resp.raise_for_status()
    return resp.json()

def delete_task(task_id):
    resp = requests.delete(
        f"{SUPABASE_URL}/rest/v1/tasks",
        headers=HEADERS,
        params={"id": f"eq.{task_id}"}
    )
    resp.raise_for_status()
    return resp

def main():
    print("=== Fetching all tasks ===")
    tasks = fetch_all_tasks()
    print(f"Total tasks found: {len(tasks)}")
    print()

    # Print all tasks before cleanup
    print("--- All tasks before cleanup ---")
    for t in tasks:
        print(f"  id={t['id']} user={t.get('user_id')} title={repr(t.get('title'))} created={t.get('created_at')}")
    print()

    # Group by (user_id, title) — ordered by created_at asc already, so first = oldest
    groups = defaultdict(list)
    for t in tasks:
        key = (t.get('user_id'), t.get('title'))
        groups[key].append(t)

    ids_to_delete = []
    print("=== Duplicate analysis ===")
    for (user_id, title), group in groups.items():
        if len(group) > 1:
            keeper = group[0]  # oldest (lowest created_at)
            dupes = group[1:]
            print(f"  DUPLICATE: user={user_id} title={repr(title)}")
            print(f"    Keeping:  id={keeper['id']} created={keeper['created_at']}")
            for d in dupes:
                print(f"    Deleting: id={d['id']} created={d['created_at']}")
                ids_to_delete.append(d['id'])
        else:
            print(f"  UNIQUE:    user={user_id} title={repr(title)}")

    print()
    if not ids_to_delete:
        print("No duplicates found. Nothing to delete.")
    else:
        print(f"=== Deleting {len(ids_to_delete)} duplicate task(s) ===")
        for tid in ids_to_delete:
            delete_task(tid)
            print(f"  Deleted id={tid}")
        print()

        # Verify
        print("=== Verifying: fetching tasks after cleanup ===")
        tasks_after = fetch_all_tasks()
        print(f"Total tasks after cleanup: {len(tasks_after)}")
        print()
        print("--- Clean task list ---")
        for t in tasks_after:
            print(f"  id={t['id']} user={t.get('user_id')} title={repr(t.get('title'))} created={t.get('created_at')}")

if __name__ == "__main__":
    main()
