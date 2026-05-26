import io
from datetime import date, timedelta

from supabase_svc import get_client


def log_activity(user_id: int, event_type: str, note: str = "") -> None:
    get_client().table("activity_log").insert({
        "user_id": user_id,
        "event_type": event_type,
        "event_date": date.today().isoformat(),
        "note": note,
    }).execute()


def get_activity_last_n_days(user_id: int, days: int = 30) -> list[dict]:
    since = (date.today() - timedelta(days=days - 1)).isoformat()
    res = (
        get_client().table("activity_log")
        .select("event_type, event_date")
        .eq("user_id", user_id)
        .gte("event_date", since)
        .execute()
    )
    return res.data or []


def build_graph(user_id: int, days: int = 30) -> io.BytesIO:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    rows = get_activity_last_n_days(user_id, days)

    today = date.today()
    date_list = [today - timedelta(days=days - 1 - i) for i in range(days)]
    date_strs = [d.isoformat() for d in date_list]
    date_index = {d: i for i, d in enumerate(date_strs)}

    study_counts = [0] * days
    habit_counts = [0] * days
    milestone_counts = [0] * days

    for row in rows:
        idx = date_index.get(str(row["event_date"]))
        if idx is None:
            continue
        t = row["event_type"]
        if t == "study":
            study_counts[idx] += 1
        elif t == "habit":
            habit_counts[idx] += 1
        elif t == "milestone":
            milestone_counts[idx] += 1

    x = np.arange(days)
    fig, ax = plt.subplots(figsize=(12, 5))

    ax.bar(x, study_counts, label="Study", color="#4A90D9", alpha=0.85)
    bottom_habit = list(study_counts)
    ax.bar(x, habit_counts, bottom=bottom_habit, label="Habits", color="#27AE60", alpha=0.85)
    bottom_milestone = [s + h for s, h in zip(study_counts, habit_counts)]
    ax.bar(x, milestone_counts, bottom=bottom_milestone, label="Milestones", color="#F39C12", alpha=0.85)

    tick_pos = list(range(0, days, 7)) + [days - 1]
    ax.set_xticks(tick_pos)
    ax.set_xticklabels(
        [date_list[i].strftime("%b %d") for i in tick_pos],
        rotation=30, ha="right", fontsize=8,
    )
    ax.set_ylabel("Activities completed")
    ax.set_title(f"Your Activity — Last {days} Days", fontsize=13)
    ax.legend(loc="upper left")
    ax.yaxis.set_major_locator(plt.MaxNLocator(integer=True))
    ax.set_xlim(-0.5, days - 0.5)

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=120)
    plt.close(fig)
    buf.seek(0)
    return buf
