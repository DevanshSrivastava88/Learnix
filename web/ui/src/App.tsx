import { useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, LayoutGroup, motion } from "framer-motion";
import { api, AuthError, type Task, type Stats, type DayCell } from "./api";

const PROMPTS = [
  "one small win still counts.",
  "you're someone who shows up.",
  "tiny steps. real progress.",
  "future you is watching.",
  "do the next thing. only that.",
];

const BOT = "@Quest3131Bot";

function todayLabel() {
  return new Date()
    .toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" })
    .toUpperCase();
}

// ───────────────────────────────────────────────────────────────────────────
// Auth gate
// ───────────────────────────────────────────────────────────────────────────
export default function App() {
  const [authed, setAuthed] = useState<boolean | null>(null); // null = checking

  useEffect(() => {
    api.me().then(() => setAuthed(true)).catch(() => setAuthed(false));
  }, []);

  if (authed === null) {
    return (
      <div className="relative z-10 grid min-h-full place-items-center">
        <p className="font-mono text-sm text-muted">
          <span className="text-acid">&gt;</span> connecting…
        </p>
      </div>
    );
  }
  if (!authed) return <Login onSuccess={() => setAuthed(true)} />;
  return <TaskApp onLogout={() => setAuthed(false)} />;
}

function Login({ onSuccess }: { onSuccess: () => void }) {
  const [code, setCode] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function verify() {
    const c = code.trim();
    if (!c) return;
    setBusy(true);
    setErr(null);
    try {
      await api.verify(c);
      onSuccess();
    } catch (e) {
      setErr(e instanceof AuthError ? "Invalid or expired code." : String(e));
      setBusy(false);
    }
  }

  return (
    <div className="relative z-10 mx-auto flex min-h-full max-w-md flex-col justify-center px-6 py-16">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
      >
        <div className="mb-8 flex items-center gap-3">
          <span className="grid h-10 w-10 place-items-center rounded-[10px] border border-acid/40 bg-acid/[0.08] font-mono text-base text-acid">
            LX
          </span>
          <div className="leading-none">
            <p className="font-mono text-xs tracking-[0.22em] text-text">LEARNIX</p>
            <p className="mt-1 font-mono text-[8px] tracking-[0.18em] text-muted">SECURE ACCESS</p>
          </div>
        </div>

        <h1 className="font-sans text-4xl font-extrabold tracking-[-0.03em] text-text">
          Log in
        </h1>
        <p className="mt-3 font-mono text-sm leading-relaxed text-muted">
          No passwords. Get a one-time code from the bot:
        </p>

        <ol className="mt-4 space-y-2 font-mono text-sm text-muted">
          <li><span className="text-acid">1.</span> Open Telegram → <span className="text-text">{BOT}</span></li>
          <li><span className="text-acid">2.</span> Send <span className="text-text">/weblogin</span></li>
          <li><span className="text-acid">3.</span> Enter the code below</li>
        </ol>

        <input
          value={code}
          onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 4))}
          onKeyDown={(e) => e.key === "Enter" && verify()}
          placeholder="0000"
          inputMode="numeric"
          maxLength={4}
          autoFocus
          className="mt-6 w-full rounded-xl border border-white/10 bg-panel px-4 py-3 text-center font-mono text-3xl tracking-[0.5em] text-text placeholder:text-muted-deep focus:border-acid/40 focus:outline-none"
        />

        <button
          onClick={verify}
          disabled={busy || !code.trim()}
          className="mt-3 w-full rounded-xl bg-acid py-3 font-sans text-base font-bold text-bg transition hover:brightness-110 active:scale-[0.98] disabled:opacity-40"
        >
          {busy ? "checking…" : "Enter"}
        </button>

        {err && (
          <p className="mt-4 rounded-xl border border-red/30 bg-red/[0.08] px-4 py-3 font-mono text-xs text-red">
            ! {err}
          </p>
        )}
      </motion.div>
    </div>
  );
}

// ───────────────────────────────────────────────────────────────────────────
// Task app
// ───────────────────────────────────────────────────────────────────────────
function TaskApp({ onLogout }: { onLogout: () => void }) {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [activity, setActivity] = useState<DayCell[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const prompt = useMemo(() => PROMPTS[Math.floor(Math.random() * PROMPTS.length)], []);

  // any 401 from the API → session gone, bounce to login
  const guard = (e: unknown) => {
    if (e instanceof AuthError) onLogout();
    else setError(String(e));
  };

  useEffect(() => {
    api
      .list()
      .then((r) => setTasks([...r.active, ...r.completed]))
      .catch(guard)
      .finally(() => setLoading(false));
    // dashboard data — best-effort, never blocks the task list
    api.stats().then(setStats).catch(() => {});
    api.activity().then((r) => setActivity(r.days)).catch(() => {});
  }, []);

  const active = tasks.filter((t) => t.status === "active");
  const completed = tasks.filter((t) => t.status === "completed");
  const doneCount = completed.length;
  const total = tasks.length;
  const pct = total ? Math.round((doneCount / total) * 100) : 0;

  async function addTask() {
    const title = draft.trim();
    if (!title) return;
    setDraft("");
    const temp: Task = { id: `tmp-${Date.now()}`, title, status: "active", type: "task" };
    setTasks((prev) => [...prev, temp]);
    try {
      const real = await api.add(title);
      setTasks((prev) => prev.map((t) => (t.id === temp.id ? real : t)));
    } catch (e) {
      setTasks((prev) => prev.filter((t) => t.id !== temp.id));
      guard(e);
    }
  }

  async function toggle(task: Task) {
    const next = task.status === "active" ? "completed" : "active";
    setTasks((prev) => prev.map((t) => (t.id === task.id ? { ...t, status: next } : t)));
    try {
      await api.setStatus(task.id, next);
    } catch (e) {
      setTasks((prev) => prev.map((t) => (t.id === task.id ? { ...t, status: task.status } : t)));
      guard(e);
    }
  }

  async function remove(task: Task) {
    const snapshot = tasks;
    setTasks((prev) => prev.filter((t) => t.id !== task.id));
    try {
      await api.remove(task.id);
    } catch (e) {
      setTasks(snapshot);
      guard(e);
    }
  }

  async function doLogout() {
    try { await api.logout(); } catch { /* ignore */ }
    onLogout();
  }

  return (
    <div className="relative z-10 mx-auto flex min-h-full max-w-2xl flex-col px-6 pb-24 pt-12 sm:pt-16">
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="flex items-center justify-between border-b border-white/10 pb-5"
      >
        <div className="flex items-center gap-3">
          <span className="grid h-9 w-9 place-items-center rounded-[10px] border border-acid/40 bg-acid/[0.08] font-mono text-sm text-acid">
            LX
          </span>
          <div className="leading-none">
            <p className="font-mono text-[11px] tracking-[0.22em] text-text">LEARNIX</p>
            <p className="mt-1 font-mono text-[8px] tracking-[0.18em] text-muted">TASK PROTOCOL</p>
          </div>
        </div>
        <button
          onClick={doLogout}
          className="font-mono text-[9px] tracking-[0.16em] text-muted transition hover:text-red"
        >
          LOG OUT
        </button>
      </motion.div>

      <motion.header
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.08, duration: 0.55 }}
        className="pt-10"
      >
        <p className="font-mono text-[10px] tracking-[0.28em] text-acid">{todayLabel()}</p>
        <h1 className="mt-2 font-sans text-6xl font-extrabold tracking-[-0.04em] text-text sm:text-7xl">
          TODAY
        </h1>
        <p className="mt-3 font-mono text-sm tracking-wide text-muted">
          <span className="text-acid">&gt;</span> {prompt}
        </p>

        {total > 0 && (
          <div className="mt-7">
            <div className="mb-2 flex items-center justify-between font-mono text-[9px] tracking-[0.16em] text-muted">
              <span>PROGRESS</span>
              <span className="text-text">{doneCount}/{total} CLEARED · {pct}%</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full border border-white/10 bg-panel">
              <motion.div
                className="h-full rounded-full bg-acid shadow-glow"
                initial={false}
                animate={{ width: `${pct}%` }}
                transition={{ type: "spring", stiffness: 120, damping: 20 }}
              />
            </div>
          </div>
        )}
      </motion.header>

      {stats && <StatsStrip stats={stats} />}
      {activity.some((d) => d.done || d.skipped) && <ActivityChart days={activity} />}

      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.16, duration: 0.5 }}
        className="mt-8 grid grid-cols-[1fr_48px] gap-2"
      >
        <input
          ref={inputRef}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && addTask()}
          placeholder="new directive…"
          className="h-12 rounded-xl border border-white/10 bg-panel px-4 font-mono text-sm text-text placeholder:text-muted-deep focus:border-acid/40 focus:outline-none"
        />
        <button
          onClick={addTask}
          aria-label="add task"
          className="grid place-items-center rounded-xl bg-acid text-2xl font-bold text-bg transition hover:brightness-110 active:scale-90"
        >
          +
        </button>
      </motion.div>

      <div className="mt-9 flex-1">
        {loading && (
          <ul className="space-y-2">
            {[0, 1, 2].map((i) => (
              <li
                key={i}
                className="h-[58px] animate-pulse rounded-xl border border-white/5 bg-panel/60"
                style={{ animationDelay: `${i * 120}ms` }}
              />
            ))}
          </ul>
        )}

        {!loading && (
          <LayoutGroup>
            <div className="mb-3 flex items-center gap-3">
              <span className="font-mono text-[10px] tracking-[0.18em] text-muted">// ACTIVE</span>
              <span className="h-px flex-1 bg-white/10" />
            </div>
            <ul className="space-y-2">
              <AnimatePresence initial={false}>
                {active.map((t, i) => (
                  <Row key={t.id} task={t} index={i} onToggle={toggle} onRemove={remove} />
                ))}
              </AnimatePresence>
            </ul>

            {active.length === 0 && (
              <motion.div
                initial={{ opacity: 0, scale: 0.97 }}
                animate={{ opacity: 1, scale: 1 }}
                className="rounded-xl border border-dashed border-white/12 bg-panel/50 px-6 py-12 text-center"
              >
                <p className="font-sans text-3xl font-extrabold tracking-tight text-text">ALL CLEAR</p>
                <p className="mt-2 font-mono text-sm text-acid">&gt; no active directives. rest up.</p>
              </motion.div>
            )}

            {completed.length > 0 && (
              <div className="mt-10">
                <div className="mb-3 flex items-center gap-3">
                  <span className="font-mono text-[10px] tracking-[0.18em] text-muted">// CLEARED</span>
                  <span className="rounded-full border border-white/10 bg-panel px-2 py-0.5 font-mono text-[9px] text-muted">
                    {completed.length}
                  </span>
                  <span className="h-px flex-1 bg-white/10" />
                </div>
                <ul className="space-y-2">
                  <AnimatePresence initial={false}>
                    {completed.map((t, i) => (
                      <Row key={t.id} task={t} index={i} onToggle={toggle} onRemove={remove} />
                    ))}
                  </AnimatePresence>
                </ul>
              </div>
            )}
          </LayoutGroup>
        )}

        {error && (
          <p className="mt-6 rounded-xl border border-red/30 bg-red/[0.08] px-4 py-3 font-mono text-xs text-red">
            ! {error}
          </p>
        )}
      </div>

      <footer className="mt-12 text-center font-mono text-[9px] uppercase tracking-[0.28em] text-muted-deep">
        learnix · your tasks
      </footer>
    </div>
  );
}

function StatsStrip({ stats }: { stats: Stats }) {
  const cards = [
    { v: `${stats.streak}`, sub: "DAY STREAK", icon: "🔥" },
    { v: `${stats.week_rate}%`, sub: "THIS WEEK", icon: "✓" },
    { v: `${stats.cleared}`, sub: "CLEARED", icon: "◇" },
  ];
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.14, duration: 0.5 }}
      className="mt-6 grid grid-cols-3 gap-2"
    >
      {cards.map((c) => (
        <div key={c.sub} className="rounded-xl border border-white/10 bg-panel px-3 py-3">
          <div className="flex items-baseline gap-1.5">
            <span className="text-sm">{c.icon}</span>
            <span className="font-sans text-2xl font-extrabold tracking-tight text-text">{c.v}</span>
          </div>
          <p className="mt-1 font-mono text-[8px] tracking-[0.16em] text-muted">{c.sub}</p>
        </div>
      ))}
    </motion.div>
  );
}

function ActivityChart({ days }: { days: DayCell[] }) {
  const max = Math.max(1, ...days.map((d) => d.done));
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.2, duration: 0.5 }}
      className="mt-3 rounded-xl border border-white/10 bg-panel px-4 py-3"
    >
      <div className="mb-2 flex items-center justify-between">
        <span className="font-mono text-[9px] tracking-[0.16em] text-muted">LAST {days.length} DAYS</span>
        <span className="font-mono text-[8px] tracking-[0.14em] text-muted-deep">
          <span className="text-acid">▌</span> done <span className="ml-2 text-red">▌</span> skipped
        </span>
      </div>
      <div className="flex h-16 items-end gap-[3px]">
        {days.map((d) => {
          const h = d.done ? Math.max(8, Math.round((d.done / max) * 100)) : 0;
          return (
            <div
              key={d.date}
              title={`${d.date}: ${d.done} done, ${d.skipped} skipped`}
              className="flex flex-1 flex-col items-center justify-end gap-[2px]"
            >
              {d.done > 0 && (
                <div className="w-full rounded-sm bg-acid" style={{ height: `${h}%` }} />
              )}
              {d.skipped > 0 && <div className="h-[3px] w-full rounded-sm bg-red" />}
              {d.done === 0 && d.skipped === 0 && (
                <div className="h-[3px] w-full rounded-sm bg-white/10" />
              )}
            </div>
          );
        })}
      </div>
    </motion.div>
  );
}

const TYPE_BADGE: Record<string, { label: string; cls: string }> = {
  habit: { label: "↻ HABIT", cls: "border-acid/30 text-acid" },
  study: { label: "✦ STUDY", cls: "border-sky-400/30 text-sky-300" },
  milestone: { label: "◈ GOAL", cls: "border-fuchsia-400/30 text-fuchsia-300" },
};

function dueLabel(due?: string | null): string | null {
  if (!due) return null;
  const d = new Date(due);
  if (isNaN(d.getTime())) return null;
  const now = new Date();
  const sameDay = d.toDateString() === now.toDateString();
  const tomorrow = new Date(now);
  tomorrow.setDate(now.getDate() + 1);
  const isTomorrow = d.toDateString() === tomorrow.toDateString();
  const time = d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  if (sameDay) return time;
  if (isTomorrow) return `tmrw ${time}`;
  return d.toLocaleDateString([], { month: "short", day: "numeric" });
}

function Row({
  task,
  index,
  onToggle,
  onRemove,
}: {
  task: Task;
  index: number;
  onToggle: (t: Task) => void;
  onRemove: (t: Task) => void;
}) {
  const done = task.status === "completed";
  const badge = TYPE_BADGE[task.type];
  const due = !done ? dueLabel(task.due) : null;
  return (
    <motion.li
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, x: -16, transition: { duration: 0.2 } }}
      transition={{ layout: { type: "spring", stiffness: 320, damping: 32 }, delay: index * 0.03 }}
      className="group flex items-center gap-3 rounded-xl border border-white/10 bg-panel px-4 py-3.5 transition hover:border-acid/30 hover:bg-panel-2"
    >
      <span className="w-6 shrink-0 font-mono text-[10px] text-muted-deep">
        {String(index + 1).padStart(2, "0")}
      </span>

      <button
        onClick={() => onToggle(task)}
        aria-label={done ? "mark not done" : "mark done"}
        className={`relative grid h-6 w-6 shrink-0 place-items-center rounded-[7px] border transition active:scale-90 ${
          done ? "border-acid bg-acid shadow-glow" : "border-white/25 bg-transparent hover:border-acid"
        }`}
      >
        <motion.svg
          viewBox="0 0 24 24"
          className="h-3.5 w-3.5"
          initial={false}
          animate={{ scale: done ? 1 : 0, opacity: done ? 1 : 0 }}
          transition={{ type: "spring", stiffness: 500, damping: 24 }}
        >
          <path d="M5 12.5l4 4 10-10" fill="none" stroke="#080a0d" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round" />
        </motion.svg>
      </button>

      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <span className={`strike font-sans text-base leading-snug transition-colors ${done ? "on font-medium text-muted" : "text-text"}`}>
          {task.title}
        </span>
        {(badge || due) && (
          <div className="flex items-center gap-2">
            {badge && (
              <span className={`rounded-full border px-1.5 py-0.5 font-mono text-[8px] tracking-[0.12em] ${badge.cls}`}>
                {badge.label}
              </span>
            )}
            {due && (
              <span className="font-mono text-[10px] text-muted-deep">⏰ {due}</span>
            )}
          </div>
        )}
      </div>

      <button
        onClick={() => onRemove(task)}
        aria-label="delete task"
        className="grid h-6 w-6 shrink-0 place-items-center rounded-md font-mono text-base text-transparent transition hover:bg-white/5 hover:text-red group-hover:text-muted"
      >
        ×
      </button>
    </motion.li>
  );
}
