import { useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, LayoutGroup, motion } from "framer-motion";
import { api, type Task } from "./api";

const PROMPTS = [
  "one small win still counts.",
  "you're someone who shows up.",
  "tiny steps. real progress.",
  "future you is watching.",
  "do the next thing. only that.",
];

function todayLabel() {
  return new Date()
    .toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" })
    .toUpperCase();
}

export default function App() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const prompt = useMemo(() => PROMPTS[Math.floor(Math.random() * PROMPTS.length)], []);

  useEffect(() => {
    api
      .list()
      .then((r) => setTasks([...r.active, ...r.completed]))
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
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
      setError(String(e));
    }
  }

  async function toggle(task: Task) {
    const next = task.status === "active" ? "completed" : "active";
    setTasks((prev) => prev.map((t) => (t.id === task.id ? { ...t, status: next } : t)));
    try {
      await api.setStatus(task.id, next);
    } catch (e) {
      setTasks((prev) => prev.map((t) => (t.id === task.id ? { ...t, status: task.status } : t)));
      setError(String(e));
    }
  }

  async function remove(task: Task) {
    const snapshot = tasks;
    setTasks((prev) => prev.filter((t) => t.id !== task.id));
    try {
      await api.remove(task.id);
    } catch (e) {
      setTasks(snapshot);
      setError(String(e));
    }
  }

  return (
    <div className="relative z-10 mx-auto flex min-h-full max-w-2xl flex-col px-6 pb-24 pt-12 sm:pt-16">
      {/* brand bar */}
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
        <div className="flex items-center gap-2">
          <span className="h-[7px] w-[7px] rounded-full bg-acid shadow-glow" />
          <span className="font-mono text-[9px] tracking-[0.16em] text-muted">SYSTEM ONLINE</span>
        </div>
      </motion.div>

      {/* header */}
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
              <span className="text-text">
                {doneCount}/{total} CLEARED · {pct}%
              </span>
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

      {/* composer */}
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

      {/* body */}
      <div className="mt-9 flex-1">
        {loading && (
          <p className="font-mono text-sm text-muted">
            <span className="text-acid">&gt;</span> loading directives…
          </p>
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
        learnix · single operator
      </footer>
    </div>
  );
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
          <path
            d="M5 12.5l4 4 10-10"
            fill="none"
            stroke="#080a0d"
            strokeWidth="3.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </motion.svg>
      </button>

      <span
        className={`strike flex-1 font-sans text-base leading-snug transition-colors ${
          done ? "on font-medium text-muted" : "text-text"
        }`}
      >
        {task.title}
      </span>

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
