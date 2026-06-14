import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import type { Task } from "./api";

// ── chime via Web Audio (no asset) ──────────────────────────────────────────
let _ctx: AudioContext | null = null;
function chime(kind: "tick" | "done" = "done") {
  try {
    _ctx = _ctx || new (window.AudioContext || (window as any).webkitAudioContext)();
    const ctx = _ctx;
    const notes = kind === "done" ? [523.25, 659.25, 783.99] : [659.25, 783.99];
    notes.forEach((f, i) => {
      const o = ctx.createOscillator();
      const g = ctx.createGain();
      o.type = "sine";
      o.frequency.value = f;
      const t = ctx.currentTime + i * 0.16;
      g.gain.setValueAtTime(0, t);
      g.gain.linearRampToValueAtTime(0.22, t + 0.04);
      g.gain.exponentialRampToValueAtTime(0.0001, t + 0.9);
      o.connect(g).connect(ctx.destination);
      o.start(t);
      o.stop(t + 0.95);
    });
  } catch {
    /* audio blocked — silent */
  }
}

function fmt(total: number): string {
  const s = Math.max(0, Math.floor(total));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
  return `${m}:${String(sec).padStart(2, "0")}`;
}

type Phase = "welcome" | "running" | "done";

export default function FocusTimer({
  task,
  onComplete,
  onExit,
}: {
  task: Task;
  onComplete: (t: Task) => void; // marks task completed (server)
  onExit: () => void; // abandon, nothing logged
}) {
  const [phase, setPhase] = useState<Phase>("welcome");
  const [durationMin, setDurationMin] = useState<string>(""); // empty = count up
  const [elapsed, setElapsed] = useState(0); // seconds
  const [paused, setPaused] = useState(false);
  const [showGuard, setShowGuard] = useState(false);
  const planned = useRef<number | null>(null); // total seconds, null = count up
  const firedMarks = useRef<Set<number>>(new Set());

  // tick
  useEffect(() => {
    if (phase !== "running" || paused) return;
    const id = setInterval(() => setElapsed((e) => e + 1), 1000);
    return () => clearInterval(id);
  }, [phase, paused]);

  // chimes + completion
  useEffect(() => {
    if (phase !== "running") return;
    const total = planned.current;
    if (total != null) {
      if (elapsed >= total) {
        chime("done");
        setPhase("done");
      }
    } else {
      // count up — chime at 30 and 60 min
      for (const mark of [1800, 3600]) {
        if (elapsed >= mark && !firedMarks.current.has(mark)) {
          firedMarks.current.add(mark);
          chime("tick");
        }
      }
    }
  }, [elapsed, phase]);

  // back-guard: intercept Esc + browser back
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        attemptBack();
      }
    };
    window.addEventListener("keydown", onKey);
    window.history.pushState({ focus: true }, "");
    const onPop = () => {
      window.history.pushState({ focus: true }, "");
      attemptBack();
    };
    window.addEventListener("popstate", onPop);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("popstate", onPop);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase]);

  function attemptBack() {
    if (phase === "welcome") return onExit();
    setShowGuard(true);
  }

  function start() {
    const n = parseInt(durationMin, 10);
    planned.current = !isNaN(n) && n > 0 ? n * 60 : null;
    setElapsed(0);
    firedMarks.current.clear();
    setPhase("running");
  }

  const total = planned.current;
  const remaining = total != null ? Math.max(0, total - elapsed) : null;
  const display = remaining != null ? remaining : elapsed;
  // ring progress 0..1
  const progress =
    total != null ? (total ? elapsed / total : 0) : (elapsed % 3600) / 3600;
  const R = 130;
  const C = 2 * Math.PI * R;

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 overflow-hidden"
    >
      {/* dreamy cat background */}
      <div
        className="absolute inset-0 bg-cover bg-center"
        style={{ backgroundImage: "url(/focus-bg.png)" }}
      />
      <div className="absolute inset-0 bg-black/30 backdrop-blur-[2px]" />

      {/* ── welcome ── */}
      <AnimatePresence mode="wait">
        {phase === "welcome" && (
          <motion.div
            key="welcome"
            initial={{ opacity: 0, scale: 0.94, y: 16 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96 }}
            transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
            className="relative z-10 flex h-full items-center justify-center px-6"
          >
            <div className="glass w-full max-w-sm rounded-[28px] p-7 text-center">
              <p className="font-mono text-[10px] tracking-[0.28em] text-white/70">FOCUS SESSION</p>
              <h1 className="mt-3 font-sans text-3xl font-extrabold leading-tight text-white drop-shadow">
                You made it here.
              </h1>
              <p className="mt-1 font-sans text-base text-white/80">
                That's the hard part. The rest is just showing up. 🎯
              </p>
              <p className="mt-5 truncate font-mono text-sm text-white/90">▸ {task.title}</p>

              <div className="mt-5">
                <label className="font-mono text-[10px] tracking-[0.18em] text-white/60">
                  DURATION (min) — optional
                </label>
                <input
                  value={durationMin}
                  onChange={(e) => setDurationMin(e.target.value.replace(/\D/g, "").slice(0, 3))}
                  onKeyDown={(e) => e.key === "Enter" && start()}
                  inputMode="numeric"
                  placeholder="∞  open focus"
                  className="mt-2 w-full rounded-2xl border border-white/25 bg-white/10 px-4 py-3 text-center font-mono text-xl text-white placeholder:text-white/40 focus:border-white/50 focus:outline-none"
                />
                <div className="mt-2 flex justify-center gap-2">
                  {[15, 25, 45].map((d) => (
                    <button
                      key={d}
                      onClick={() => setDurationMin(String(d))}
                      className="rounded-full border border-white/25 bg-white/5 px-3 py-1 font-mono text-xs text-white/80 transition hover:bg-white/15"
                    >
                      {d}m
                    </button>
                  ))}
                </div>
              </div>

              <button
                onClick={start}
                className="mt-6 w-full rounded-2xl bg-white/90 py-3.5 font-sans text-lg font-bold text-purple-900 shadow-lg transition hover:bg-white active:scale-[0.98]"
              >
                Start focusing →
              </button>
              <button
                onClick={onExit}
                className="mt-3 font-mono text-[11px] tracking-[0.14em] text-white/55 transition hover:text-white/90"
              >
                ← back
              </button>
            </div>
          </motion.div>
        )}

        {(phase === "running" || phase === "done") && (
          <motion.div
            key="running"
            initial={{ opacity: 0, scale: 0.96 }}
            animate={{ opacity: 1, scale: 1 }}
            className="relative z-10 flex h-full flex-col items-center justify-center px-6"
          >
            <p className="mb-6 max-w-md truncate text-center font-sans text-xl font-semibold text-white drop-shadow">
              {task.title}
            </p>

            <div className="glass relative grid h-[320px] w-[320px] place-items-center rounded-full">
              <svg className="absolute inset-0 -rotate-90" viewBox="0 0 300 300">
                <circle cx="150" cy="150" r={R} fill="none" stroke="rgba(255,255,255,0.18)" strokeWidth="6" />
                <circle
                  cx="150" cy="150" r={R} fill="none" stroke="white" strokeWidth="6"
                  strokeLinecap="round" strokeDasharray={C}
                  strokeDashoffset={total != null ? C * progress : C * (1 - progress)}
                  style={{ transition: "stroke-dashoffset 1s linear", filter: "drop-shadow(0 0 6px rgba(255,255,255,0.7))" }}
                />
              </svg>
              <div className="text-center">
                <div className="font-sans text-6xl font-extrabold tabular-nums text-white drop-shadow">
                  {fmt(display)}
                </div>
                <div className="mt-1 font-mono text-[10px] tracking-[0.2em] text-white/70">
                  {phase === "done" ? "TIME'S UP — LOCK IT IN" : total != null ? "REMAINING" : "FOCUSING"}
                </div>
              </div>
            </div>

            {/* controls */}
            <div className="mt-8 flex items-center gap-3">
              {phase === "running" && (
                <button
                  onClick={() => setPaused((p) => !p)}
                  className="glass rounded-2xl px-6 py-3 font-sans font-semibold text-white transition hover:bg-white/20"
                >
                  {paused ? "▶ Resume" : "❚❚ Pause"}
                </button>
              )}
              <button
                onClick={() => onComplete(task)}
                className={`rounded-2xl px-7 py-3 font-sans font-bold text-purple-900 shadow-lg transition active:scale-95 ${
                  phase === "done" ? "animate-pulse bg-white" : "bg-white/90 hover:bg-white"
                }`}
              >
                ✓ Done
              </button>
            </div>

            <button
              onClick={attemptBack}
              className="mt-6 font-mono text-[11px] tracking-[0.14em] text-white/55 transition hover:text-white/90"
            >
              ← back
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* back-guard */}
      <AnimatePresence>
        {showGuard && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="absolute inset-0 z-20 grid place-items-center bg-black/50 px-6"
          >
            <motion.div
              initial={{ scale: 0.92, y: 10 }}
              animate={{ scale: 1, y: 0 }}
              className="glass w-full max-w-xs rounded-3xl p-6 text-center"
            >
              <p className="font-sans text-lg font-bold text-white">Going back will cost your focus.</p>
              <p className="mt-1 font-sans text-sm text-white/75">You're mid-session. Sure you want to bail?</p>
              <button
                onClick={() => setShowGuard(false)}
                className="mt-5 w-full rounded-2xl bg-white/90 py-3 font-sans font-bold text-purple-900 transition hover:bg-white"
              >
                Return to timer
              </button>
              <button
                onClick={onExit}
                className="mt-2 w-full rounded-2xl border border-white/25 py-2.5 font-sans text-sm font-semibold text-white/80 transition hover:bg-white/10"
              >
                Exit task
              </button>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
