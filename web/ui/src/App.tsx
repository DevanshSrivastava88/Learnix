import { useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, LayoutGroup, motion } from "framer-motion";
import {
  DndContext,
  PointerSensor,
  TouchSensor,
  closestCenter,
  useSensor,
  useSensors,
  useDraggable,
  useDroppable,
  type DragEndEvent,
} from "@dnd-kit/core";
import { api, AuthError, type Task, type Stats, type DayCell } from "./api";
import FocusTimer from "./FocusTimer";
import DayPlanner from "./DayPlanner";

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
  const [adhd, setAdhd] = useState(() => localStorage.getItem("learnix_adhd") === "1");
  const [focusTask, setFocusTask] = useState<Task | null>(null);
  const [planning, setPlanning] = useState(false);
  const [theme, setTheme] = useState<"night" | "day">(
    () => (localStorage.getItem("learnix_theme") as "night" | "day") || "night"
  );

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  function toggleTheme() {
    setTheme((t) => {
      const next = t === "night" ? "day" : "night";
      localStorage.setItem("learnix_theme", next);
      return next;
    });
  }

  function refetch() {
    api.list().then((r) => setTasks([...r.active, ...r.completed])).catch(guard);
  }
  const inputRef = useRef<HTMLInputElement>(null);
  const prompt = useMemo(() => PROMPTS[Math.floor(Math.random() * PROMPTS.length)], []);

  function toggleAdhd() {
    setAdhd((v) => {
      localStorage.setItem("learnix_adhd", v ? "0" : "1");
      return !v;
    });
  }

  async function completeFromFocus(task: Task) {
    // Habit-aware (same as the list toggle): habit stays active with an advanced
    // reminder, one-off task closes.
    if (task.type !== "habit") {
      setTasks((prev) => prev.map((t) => (t.id === task.id ? { ...t, status: "completed" } : t)));
    }
    setFocusTask(null);
    try {
      const updated = await api.complete(task.id);
      setTasks((prev) => prev.map((t) => (t.id === task.id ? updated : t)));
    } catch (e) {
      guard(e);
    }
  }

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

  // Manual drag order wins (sort_order); otherwise scheduled tasks float up
  // (soonest first) and unscheduled sink — overdue naturally leads the stack.
  // Mirrors the server's _order_active so optimistic + fetched state agree.
  const active = useMemo(() => {
    const ts = (t: Task) => {
      const n = t.due ? new Date(t.due).getTime() : NaN;
      return isNaN(n) ? Infinity : n;
    };
    const all = tasks.filter((t) => t.status === "active");
    const hasManual = all.some((t) => t.ordering != null);
    if (!hasManual) return [...all].sort((a, b) => ts(a) - ts(b));
    const manual = all.filter((t) => t.ordering != null).sort((a, b) => a.ordering! - b.ordering!);
    const rest = all.filter((t) => t.ordering == null).sort((a, b) => ts(a) - ts(b));
    return [...manual, ...rest];
  }, [tasks]);
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
    // Un-checking a cleared task just flips it back to active.
    if (task.status === "completed") {
      setTasks((prev) => prev.map((t) => (t.id === task.id ? { ...t, status: "active" } : t)));
      try {
        await api.setStatus(task.id, "active");
      } catch (e) {
        setTasks((prev) => prev.map((t) => (t.id === task.id ? { ...t, status: "completed" } : t)));
        guard(e);
      }
      return;
    }
    // Completing: a habit logs today's done + advances its reminder and STAYS
    // in the list; a one-off task closes. The server decides — we reconcile
    // with whatever it returns (habit comes back active with a new due).
    const isHabit = task.type === "habit";
    if (!isHabit) {
      setTasks((prev) => prev.map((t) => (t.id === task.id ? { ...t, status: "completed" } : t)));
    }
    try {
      const updated = await api.complete(task.id);
      setTasks((prev) => prev.map((t) => (t.id === task.id ? updated : t)));
    } catch (e) {
      if (!isHabit) {
        setTasks((prev) => prev.map((t) => (t.id === task.id ? { ...t, status: "active" } : t)));
      }
      guard(e);
    }
  }

  // repeat toggle: habit repeats daily (stays active on complete), task is one-off
  async function toggleRepeat(task: Task) {
    if (task.type !== "task" && task.type !== "habit") return;
    const next = task.type === "habit" ? "task" : "habit";
    setTasks((prev) => prev.map((t) => (t.id === task.id ? { ...t, type: next } : t)));
    try {
      const updated = await api.setType(task.id, next);
      setTasks((prev) => prev.map((t) => (t.id === task.id ? updated : t)));
    } catch (e) {
      setTasks((prev) => prev.map((t) => (t.id === task.id ? { ...t, type: task.type } : t)));
      guard(e);
    }
  }

  // tap vs drag: require an 8px move (pointer) / short hold (touch) so the
  // check/delete buttons still click cleanly. Same constraints as DayPlanner.
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 180, tolerance: 8 } })
  );

  async function onReorder(e: DragEndEvent) {
    const fromId = String(e.active.id);
    const overId = e.over ? String(e.over.id) : null;
    if (!overId || fromId === overId) return;
    const order = active.map((t) => t.id);
    const from = order.indexOf(fromId);
    const to = order.indexOf(overId);
    if (from < 0 || to < 0) return;
    order.splice(to, 0, order.splice(from, 1)[0]);
    // write the new index onto every active task so the local sort agrees
    const rank = new Map(order.map((id, i) => [id, i]));
    const snapshot = tasks;
    setTasks((prev) =>
      prev.map((t) => (rank.has(t.id) ? { ...t, ordering: rank.get(t.id)! } : t))
    );
    try {
      await api.reorder(order);
    } catch (e) {
      setTasks(snapshot);
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
      <AnimatePresence>
        {focusTask && (
          <FocusTimer
            task={focusTask}
            onComplete={completeFromFocus}
            onExit={() => setFocusTask(null)}
          />
        )}
        {planning && (
          <DayPlanner
            tasks={tasks}
            onClose={(c) => { setPlanning(false); if (c) refetch(); }}
          />
        )}
      </AnimatePresence>

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
        <div className="flex items-center gap-3">
          <button
            onClick={toggleTheme}
            title={theme === "night" ? "Switch to day mode" : "Switch to night mode"}
            aria-label="toggle theme"
            className={`grid h-7 w-7 place-items-center rounded-full border text-sm transition ${
              theme === "day" ? "border-acid/50 bg-acid/10" : "border-white/10 hover:bg-white/5"
            }`}
          >
            🌙
          </button>
          <button
            onClick={() => setPlanning(true)}
            title="Plan your day — drag tasks into time slots"
            className="flex items-center gap-1.5 rounded-full border border-white/10 px-2.5 py-1 font-mono text-[9px] tracking-[0.14em] text-muted transition hover:text-text"
          >
            📅 PLAN
          </button>
          <button
            onClick={toggleAdhd}
            title="Focus mode — adds a ▶ to each task"
            className={`flex items-center gap-1.5 rounded-full border px-2.5 py-1 font-mono text-[9px] tracking-[0.14em] transition ${
              adhd ? "border-acid/50 bg-acid/10 text-acid" : "border-white/10 text-muted hover:text-text"
            }`}
          >
            <span className={`h-1.5 w-1.5 rounded-full ${adhd ? "bg-acid shadow-glow" : "bg-muted"}`} />
            FIX ADHD
          </button>
          <button
            onClick={doLogout}
            className="font-mono text-[9px] tracking-[0.16em] text-muted transition hover:text-red"
          >
            LOG OUT
          </button>
        </div>
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
            <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onReorder}>
              <ul className="space-y-2">
                <AnimatePresence initial={false}>
                  {active.map((t, i) => (
                    <DraggableRow
                      key={t.id}
                      task={t}
                      index={i}
                      onToggle={toggle}
                      onRemove={remove}
                      onPlay={adhd ? setFocusTask : undefined}
                      onOpen={setFocusTask}
                      onRepeat={toggleRepeat}
                    />
                  ))}
                </AnimatePresence>
              </ul>
            </DndContext>

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

function dueLabel(due?: string | null): { text: string; overdue: boolean } | null {
  if (!due) return null;
  const d = new Date(due);
  if (isNaN(d.getTime())) return null;
  const now = new Date();
  const overdue = d.getTime() < now.getTime();
  const sameDay = d.toDateString() === now.toDateString();
  const tomorrow = new Date(now);
  tomorrow.setDate(now.getDate() + 1);
  const isTomorrow = d.toDateString() === tomorrow.toDateString();
  const time = d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  let text: string;
  if (sameDay) text = time;
  else if (isTomorrow) text = `tmrw ${time}`;
  else text = d.toLocaleDateString([], { month: "short", day: "numeric" });
  return { text, overdue };
}

// Active-list row that is both a drag source and a drop target. The drag
// listeners live on the index grip (see Row) so the check/delete buttons stay
// clickable; the whole li is the droppable.
function DraggableRow(props: {
  task: Task;
  index: number;
  onToggle: (t: Task) => void;
  onRemove: (t: Task) => void;
  onPlay?: (t: Task) => void;
  onOpen?: (t: Task) => void;
  onRepeat?: (t: Task) => void;
}) {
  const { attributes, listeners, setNodeRef: setDragRef, isDragging } = useDraggable({
    id: props.task.id,
  });
  const { setNodeRef: setDropRef } = useDroppable({ id: props.task.id });
  const ref = (el: HTMLElement | null) => {
    setDragRef(el);
    setDropRef(el);
  };
  return (
    <Row
      {...props}
      dragRef={ref}
      dragHandle={{ ...listeners, ...attributes }}
      isDragging={isDragging}
    />
  );
}

function Row({
  task,
  index,
  onToggle,
  onRemove,
  onPlay,
  onOpen,
  onRepeat,
  dragRef,
  dragHandle,
  isDragging,
}: {
  task: Task;
  index: number;
  onToggle: (t: Task) => void;
  onRemove: (t: Task) => void;
  onPlay?: (t: Task) => void;
  onOpen?: (t: Task) => void;
  onRepeat?: (t: Task) => void;
  // drag wiring (active list only); absent for the cleared list
  dragRef?: (el: HTMLElement | null) => void;
  dragHandle?: Record<string, unknown>;
  isDragging?: boolean;
}) {
  const done = task.status === "completed";
  const badge = TYPE_BADGE[task.type];
  const due = !done ? dueLabel(task.due) : null;
  return (
    <motion.li
      ref={dragRef}
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, x: -16, transition: { duration: 0.2 } }}
      transition={{ layout: { type: "spring", stiffness: 320, damping: 32 }, delay: index * 0.03 }}
      className={`group flex items-center gap-3 rounded-xl border border-white/10 bg-panel px-4 py-3.5 transition hover:border-acid/30 hover:bg-panel-2 ${
        isDragging ? "opacity-40 ring-1 ring-acid/40" : ""
      }`}
    >
      {dragHandle ? (
        <span
          {...dragHandle}
          title="Drag to reorder"
          aria-label="drag to reorder"
          style={{ touchAction: "none" }}
          className="w-6 shrink-0 cursor-grab select-none text-center font-mono text-[10px] text-muted-deep transition hover:text-acid active:cursor-grabbing"
        >
          {String(index + 1).padStart(2, "0")}
        </span>
      ) : (
        <span className="w-6 shrink-0 font-mono text-[10px] text-muted-deep">
          {String(index + 1).padStart(2, "0")}
        </span>
      )}

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
        <span
          onClick={!done && onOpen ? () => onOpen(task) : undefined}
          title={!done && onOpen ? "Start a focus session" : undefined}
          className={`strike font-sans text-base leading-snug transition-colors ${
            done ? "on font-medium text-muted" : "text-text"
          } ${!done && onOpen ? "cursor-pointer hover:text-acid" : ""}`}
        >
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
              <span className={`font-mono text-[10px] ${due.overdue ? "text-red" : "text-muted-deep"}`}>
                {due.overdue ? "⏰ overdue · " : "⏰ "}{due.text}
              </span>
            )}
          </div>
        )}
      </div>

      {onRepeat && !done && (task.type === "task" || task.type === "habit") && (
        <button
          onClick={() => onRepeat(task)}
          aria-label="toggle repeat"
          title={task.type === "habit" ? "Repeats daily — tap to make one-off" : "Make repeatable (daily)"}
          className={`grid h-7 w-7 shrink-0 place-items-center rounded-full border text-[13px] transition ${
            task.type === "habit"
              ? "border-acid/60 bg-acid/15 text-acid"
              : "border-white/10 text-muted hover:border-acid/40 hover:text-acid"
          }`}
        >
          ↻
        </button>
      )}
      {onPlay && (
        <button
          onClick={() => onPlay(task)}
          aria-label="focus on task"
          title="Focus"
          className="grid h-7 w-7 shrink-0 place-items-center rounded-full border border-acid/40 bg-acid/10 text-[11px] text-acid transition hover:bg-acid hover:text-bg"
        >
          ▶
        </button>
      )}
      <button
        onClick={() => onRemove(task)}
        aria-label="delete task"
        title="Delete"
        className="grid h-7 w-7 shrink-0 place-items-center rounded-md border border-white/10 font-mono text-base text-muted transition hover:border-red/40 hover:bg-red/10 hover:text-red"
      >
        ×
      </button>
    </motion.li>
  );
}
