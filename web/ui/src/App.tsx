import { useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, LayoutGroup, motion } from "framer-motion";
import { api, type Task } from "./api";

const PROMPTS = [
  "what's the move today?",
  "one small thing counts.",
  "you're someone who shows up.",
  "tiny steps, real progress.",
  "future you says thanks.",
];

function todayLabel() {
  return new Date().toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
  });
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

  async function addTask() {
    const title = draft.trim();
    if (!title) return;
    setDraft("");
    // optimistic
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
    <div className="relative z-10 mx-auto flex min-h-full max-w-2xl flex-col px-6 pb-24 pt-14 sm:pt-20">
      {/* header */}
      <motion.header
        initial={{ opacity: 0, y: -12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
      >
        <p className="font-body text-sm font-semibold uppercase tracking-[0.32em] text-terracotta-deep">
          {todayLabel()}
        </p>
        <h1 className="mt-1 font-display text-6xl font-semibold italic leading-none text-ink sm:text-7xl">
          today
        </h1>
        <p className="mt-3 font-hand text-2xl text-ink-soft">{prompt}</p>

        {total > 0 && (
          <div className="mt-6 flex items-center gap-3">
            <div className="h-2 flex-1 overflow-hidden rounded-full bg-paper-deep">
              <motion.div
                className="h-full rounded-full bg-gradient-to-r from-terracotta to-terracotta-deep"
                initial={false}
                animate={{ width: total ? `${(doneCount / total) * 100}%` : "0%" }}
                transition={{ type: "spring", stiffness: 120, damping: 20 }}
              />
            </div>
            <span className="font-body text-sm font-semibold text-ink-soft">
              {doneCount}/{total}
            </span>
          </div>
        )}
      </motion.header>

      {/* add box */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.12, duration: 0.5 }}
        className="mt-8 flex items-center gap-2 rounded-2xl border border-paper-deep bg-white/55 p-2 shadow-card backdrop-blur-sm focus-within:shadow-lift"
      >
        <input
          ref={inputRef}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && addTask()}
          placeholder="add something…"
          className="flex-1 bg-transparent px-3 py-2 font-body text-lg text-ink placeholder:text-ink-soft/60 focus:outline-none"
        />
        <button
          onClick={addTask}
          aria-label="add task"
          className="grid h-11 w-11 place-items-center rounded-xl bg-terracotta text-2xl text-white transition hover:bg-terracotta-deep active:scale-90"
        >
          +
        </button>
      </motion.div>

      {/* body */}
      <div className="mt-8 flex-1">
        {loading && <p className="font-hand text-2xl text-ink-soft">loading your day…</p>}

        {!loading && (
          <LayoutGroup>
            {/* open tasks */}
            <ul className="space-y-2">
              <AnimatePresence initial={false}>
                {active.map((t, i) => (
                  <Row key={t.id} task={t} index={i} onToggle={toggle} onRemove={remove} />
                ))}
              </AnimatePresence>
            </ul>

            {active.length === 0 && (
              <motion.div
                initial={{ opacity: 0, scale: 0.96 }}
                animate={{ opacity: 1, scale: 1 }}
                className="rounded-2xl border border-dashed border-paper-deep bg-white/40 px-6 py-12 text-center"
              >
                <p className="font-display text-3xl italic text-ink">all clear</p>
                <p className="mt-2 font-hand text-2xl text-sage">go touch some grass 🌱</p>
              </motion.div>
            )}

            {/* done */}
            {completed.length > 0 && (
              <div className="mt-10">
                <div className="mb-3 flex items-center gap-3">
                  <span className="font-hand text-2xl text-ink-soft">done</span>
                  <span className="rounded-full bg-paper-deep px-2.5 py-0.5 font-body text-xs font-bold text-ink-soft">
                    {completed.length}
                  </span>
                  <span className="h-px flex-1 bg-paper-deep" />
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
          <p className="mt-6 rounded-xl bg-terracotta/10 px-4 py-3 font-body text-sm text-terracotta-deep">
            {error}
          </p>
        )}
      </div>

      <footer className="mt-12 text-center font-body text-xs uppercase tracking-[0.3em] text-ink-soft/50">
        learnix · just for you
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
      transition={{ layout: { type: "spring", stiffness: 320, damping: 32 }, delay: index * 0.035 }}
      className="group flex items-center gap-3 rounded-2xl border border-paper-deep/70 bg-white/55 px-4 py-3.5 shadow-card backdrop-blur-sm transition hover:border-terracotta/40 hover:shadow-lift"
    >
      <button
        onClick={() => onToggle(task)}
        aria-label={done ? "mark not done" : "mark done"}
        className={`relative grid h-7 w-7 shrink-0 place-items-center rounded-full border-2 transition active:scale-90 ${
          done ? "border-terracotta-deep bg-terracotta-deep" : "border-ink-soft/40 bg-transparent hover:border-terracotta"
        }`}
      >
        <motion.svg
          viewBox="0 0 24 24"
          className="h-4 w-4"
          initial={false}
          animate={{ scale: done ? 1 : 0, opacity: done ? 1 : 0 }}
          transition={{ type: "spring", stiffness: 500, damping: 24 }}
        >
          <path
            d="M5 12.5l4 4 10-10"
            fill="none"
            stroke="white"
            strokeWidth="3"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </motion.svg>
      </button>

      <span
        className={`strike flex-1 font-body text-lg leading-snug transition-colors ${
          done ? "on text-ink-soft/60" : "text-ink"
        }`}
      >
        {task.title}
      </span>

      <button
        onClick={() => onRemove(task)}
        aria-label="delete task"
        className="grid h-7 w-7 shrink-0 place-items-center rounded-full text-lg text-ink-soft/0 transition hover:bg-paper-deep hover:text-terracotta-deep group-hover:text-ink-soft/50"
      >
        ×
      </button>
    </motion.li>
  );
}
