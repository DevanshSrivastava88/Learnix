import io
from collections import Counter
from datetime import date, timedelta, datetime, timezone

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
    ax.set_ylim(bottom=0)

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=120)
    plt.close(fig)
    buf.seek(0)
    return buf


def get_skips_last_n_days(user_id: int, days: int = 30) -> list:
    since = (date.today() - timedelta(days=days - 1)).isoformat()
    res = (
        get_client().table("task_skips")
        .select("task_id, skipped_at, note")
        .eq("user_id", user_id)
        .gte("skipped_at", since + "T00:00:00+00:00")
        .execute()
    )
    return res.data or []


def get_done_counts_last_n_days(user_id: int, days: int = 30) -> list:
    since = (date.today() - timedelta(days=days - 1)).isoformat()
    res = (
        get_client().table("activity_log")
        .select("event_date")
        .eq("user_id", user_id)
        .eq("event_type", "habit")
        .gte("event_date", since)
        .execute()
    )
    return res.data or []


def build_skip_graph(user_id: int, days: int = 30) -> io.BytesIO:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    skip_rows = get_skips_last_n_days(user_id, days)
    done_rows = get_done_counts_last_n_days(user_id, days)

    today = date.today()
    date_list = [today - timedelta(days=days - 1 - i) for i in range(days)]
    date_strs = [d.isoformat() for d in date_list]
    date_index = {d: i for i, d in enumerate(date_strs)}

    skip_counts = [0] * days
    done_counts = [0] * days
    task_skip_tally = Counter()

    for row in skip_rows:
        raw = row["skipped_at"][:10]
        idx = date_index.get(raw)
        if idx is not None:
            skip_counts[idx] += 1
        task_skip_tally[row["task_id"]] += 1

    for row in done_rows:
        idx = date_index.get(str(row["event_date"]))
        if idx is not None:
            done_counts[idx] += 1

    completion_rate = []
    for d, s in zip(done_counts, skip_counts):
        total = d + s
        completion_rate.append((d / total * 100) if total > 0 else None)

    x = np.arange(days)
    fig, ax1 = plt.subplots(figsize=(12, 5))
    ax2 = ax1.twinx()

    max_skip = max(skip_counts) if any(skip_counts) else 1
    bar_colors = ["#E74C3C" if s == max_skip and s > 0 else "#EC7063" for s in skip_counts]
    ax1.bar(x, skip_counts, color=bar_colors, alpha=0.85, label="Skips per day")

    valid_x = [i for i, r in enumerate(completion_rate) if r is not None]
    valid_y = [r for r in completion_rate if r is not None]
    if valid_x:
        ax2.plot(valid_x, valid_y, color="#27AE60", linewidth=2, marker="o",
                 markersize=3, label="Completion rate %")
        ax2.set_ylim(0, 110)
        ax2.set_ylabel("Completion rate (%)", color="#27AE60")
        ax2.tick_params(axis="y", labelcolor="#27AE60")

    tick_pos = list(range(0, days, 7)) + [days - 1]
    ax1.set_xticks(tick_pos)
    ax1.set_xticklabels(
        [date_list[i].strftime("%b %d") for i in tick_pos],
        rotation=30, ha="right", fontsize=8,
    )
    ax1.set_ylabel("Skips")
    ax1.set_title("Skip Analytics — Last 30 Days", fontsize=13)
    ax1.yaxis.set_major_locator(plt.MaxNLocator(integer=True))
    ax1.set_xlim(-0.5, days - 0.5)

    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, loc="upper left")

    if task_skip_tally:
        from tasks.svc import get_task
        most_skipped_id = task_skip_tally.most_common(1)[0][0]
        t = get_task(most_skipped_id)
        if t:
            ax1.set_xlabel(f"Most skipped: {t['title']}", fontsize=9, color="#E74C3C")

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=120)
    plt.close(fig)
    buf.seek(0)
    return buf
