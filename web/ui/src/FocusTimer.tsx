import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import type { Task } from "./api";

// ── chime via Web Audio (no asset) ──────────────────────────────────────────
let _ctx: AudioContext | null = null;
function chime(kind: "break" | "done" = "done") {
  try {
    _ctx = _ctx || new (window.AudioContext || (window as any).webkitAudioContext)();
    const ctx = _ctx;
    const notes = kind === "done" ? [523.25, 659.25, 783.99] : [659.25, 523.25];
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

// "1:30" / "01:30" → 90 min; "45" → 45 min. Returns seconds, or null if invalid.
function parseHHMM(s: string): number | null {
  const t = (s || "").trim();
  if (!t) return null;
  if (t.includes(":")) {
    const [h, m] = t.split(":");
    const hh = parseInt(h || "0", 10);
    const mm = parseInt(m || "0", 10);
    if (isNaN(hh) && isNaN(mm)) return null;
    const total = (isNaN(hh) ? 0 : hh) * 3600 + (isNaN(mm) ? 0 : mm) * 60;
    return total > 0 ? total : null;
  }
  const n = parseInt(t, 10);
  return isNaN(n) || n <= 0 ? null : n * 60;
}

const DEFAULT_FOCUS = 30 * 60;
const BREAK_SEC = 5 * 60;

type Phase = "welcome" | "running" | "done";
type Mode = "focus" | "break";

export default function FocusTimer({
  task,
  onComplete,
  onExit,
}: {
  task: Task;
  onComplete: (t: Task) => void;
  onExit: () => void;
}) {
  const [phase, setPhase] = useState<Phase>("welcome");
  const [mode, setMode] = useState<Mode>("focus");
  const [durInput, setDurInput] = useState(""); // HH:MM or MM
  const [totalSec, setTotalSec] = useState(DEFAULT_FOCUS);
  const [elapsed, setElapsed] = useState(0);
  const [paused, setPaused] = useState(false);
  const [showGuard, setShowGuard] = useState(false);
  const [showEdit, setShowEdit] = useState(false);
  const [editInput, setEditInput] = useState("");
  const lastFocus = useRef(DEFAULT_FOCUS);

  // tick
  useEffect(() => {
    if (phase !== "running" || paused) return;
    const id = setInterval(() => setElapsed((e) => e + 1), 1000);
    return () => clearInterval(id);
  }, [phase, paused]);

  // completion
  useEffect(() => {
    if (phase === "running" && elapsed >= totalSec) {
      chime(mode === "break" ? "break" : "done");
      setPhase("done");
    }
  }, [elapsed, totalSec, phase, mode]);

  // back-guard: Esc + browser back
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

  function startFocus(sec: number) {
    lastFocus.current = sec;
    setMode("focus");
    setTotalSec(sec);
    setElapsed(0);
    setPaused(false);
    setPhase("running");
  }

  function startBreak() {
    setMode("break");
    setTotalSec(BREAK_SEC);
    setElapsed(0);
    setPaused(false);
    setPhase("running");
  }

  function applyEdit() {
    const sec = parseHHMM(editInput);
    if (sec) {
      setTotalSec(sec);
      if (mode === "focus") lastFocus.current = sec;
      if (elapsed >= sec) {
        chime("done");
        setPhase("done");
      } else {
        setPhase("running");
      }
    }
    setShowEdit(false);
  }

  const remaining = Math.max(0, totalSec - elapsed);
  const progress = totalSec ? elapsed / totalSec : 0;
  const R = 130;
  const C = 2 * Math.PI * R;
  const isBreak = mode === "break";

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 overflow-hidden"
    >
      <div className="absolute inset-0 bg-cover bg-center" style={{ backgroundImage: "url(/focus-bg.png)" }} />
      <div className={`absolute inset-0 backdrop-blur-[2px] ${isBreak ? "bg-indigo-950/45" : "bg-black/30"}`} />

      <AnimatePresence mode="wait">
        {/* ── welcome ── */}
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
                <label className="font-mono text-[10px] tracking-[0.18em] text-white/60">DURATION — hh:mm</label>
                <input
                  value={durInput}
                  onChange={(e) => setDurInput(e.target.value.replace(/[^\d:]/g, "").slice(0, 5))}
                  onKeyDown={(e) => e.key === "Enter" && startFocus(parseHHMM(durInput) ?? DEFAULT_FOCUS)}
                  inputMode="numeric"
                  placeholder="00:30"
                  className="mt-2 w-full rounded-2xl border border-white/25 bg-white/10 px-4 py-3 text-center font-mono text-xl text-white placeholder:text-white/40 focus:border-white/50 focus:outline-none"
                />
                <div className="mt-2 flex justify-center gap-2">
                  {[["30 min", 30], ["60 min", 60]].map(([label, m]) => (
                    <button
                      key={m}
                      onClick={() => setDurInput(`${m}`)}
                      className="rounded-full border border-white/25 bg-white/5 px-4 py-1 font-mono text-xs text-white/80 transition hover:bg-white/15"
                    >
                      {label as string}
                    </button>
                  ))}
                </div>
              </div>

              <button
                onClick={() => startFocus(parseHHMM(durInput) ?? DEFAULT_FOCUS)}
                className="mt-6 w-full rounded-2xl bg-white/90 py-3.5 font-sans text-lg font-bold text-purple-900 shadow-lg transition hover:bg-white active:scale-[0.98]"
              >
                Start focusing →
              </button>
              <p className="mt-2 font-mono text-[10px] text-white/45">defaults to 30 min if left blank</p>
              <button
                onClick={onExit}
                className="mt-3 font-mono text-[11px] tracking-[0.14em] text-white/55 transition hover:text-white/90"
              >
                ← back
              </button>
            </div>
          </motion.div>
        )}

        {/* ── running / done ── */}
        {(phase === "running" || phase === "done") && (
          <motion.div
            key="running"
            initial={{ opacity: 0, scale: 0.96 }}
            animate={{ opacity: 1, scale: 1 }}
            className="relative z-10 flex h-full flex-col items-center justify-center px-6"
          >
            {/* top: mode + title + edit */}
            <div className="absolute inset-x-0 top-0 flex items-center justify-between px-6 pt-6">
              <span className={`glass rounded-full px-3 py-1 font-mono text-[10px] tracking-[0.18em] ${isBreak ? "text-indigo-100" : "text-white"}`}>
                {isBreak ? "☕ BREAK" : "🎯 FOCUS"}
              </span>
              {!isBreak && phase === "running" && (
                <button
                  onClick={() => { setEditInput(""); setShowEdit(true); }}
                  className="glass rounded-full px-3 py-1 font-mono text-[10px] tracking-[0.16em] text-white transition hover:bg-white/20"
                >
                  ✎ EDIT TIME
                </button>
              )}
            </div>

            <p className="mb-6 max-w-md truncate text-center font-sans text-xl font-semibold text-white drop-shadow">
              {task.title}
            </p>

            <div className="glass relative grid h-[320px] w-[320px] place-items-center rounded-full">
              <svg className="absolute inset-0 -rotate-90" viewBox="0 0 300 300">
                <circle cx="150" cy="150" r={R} fill="none" stroke="rgba(255,255,255,0.18)" strokeWidth="6" />
                <circle
                  cx="150" cy="150" r={R} fill="none" stroke="white" strokeWidth="6"
                  strokeLinecap="round" strokeDasharray={C} strokeDashoffset={C * progress}
                  style={{ transition: "stroke-dashoffset 1s linear", filter: "drop-shadow(0 0 6px rgba(255,255,255,0.7))" }}
                />
              </svg>
              <div className="text-center">
                <div className="font-sans text-6xl font-extrabold tabular-nums text-white drop-shadow">{fmt(remaining)}</div>
                <div className="mt-1 font-mono text-[10px] tracking-[0.2em] text-white/70">
                  {phase === "done" ? (isBreak ? "BREAK OVER" : "TIME'S UP — NICE WORK") : "REMAINING"}
                </div>
              </div>
            </div>

            {/* controls */}
            <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
              {phase === "running" && (
                <button onClick={() => setPaused((p) => !p)} className="glass rounded-2xl px-6 py-3 font-sans font-semibold text-white transition hover:bg-white/20">
                  {paused ? "▶ Resume" : "❚❚ Pause"}
                </button>
              )}
              {phase === "done" && isBreak && (
                <button onClick={() => startFocus(lastFocus.current)} className="glass rounded-2xl px-6 py-3 font-sans font-semibold text-white transition hover:bg-white/20">
                  ▶ Back to focus
                </button>
              )}
              {phase === "done" && !isBreak && (
                <button onClick={startBreak} className="glass rounded-2xl px-6 py-3 font-sans font-semibold text-white transition hover:bg-white/20">
                  ☕ 5-min break
                </button>
              )}
              <button
                onClick={() => onComplete(task)}
                className={`rounded-2xl px-7 py-3 font-sans font-bold text-purple-900 shadow-lg transition active:scale-95 ${phase === "done" && !isBreak ? "animate-pulse bg-white" : "bg-white/90 hover:bg-white"}`}
              >
                ✓ Done
              </button>
            </div>

            <button onClick={attemptBack} className="mt-6 font-mono text-[11px] tracking-[0.14em] text-white/55 transition hover:text-white/90">
              ← back
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* edit-time overlay */}
      <AnimatePresence>
        {showEdit && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="absolute inset-0 z-20 grid place-items-center bg-black/50 px-6">
            <motion.div initial={{ scale: 0.92, y: 10 }} animate={{ scale: 1, y: 0 }} className="glass w-full max-w-xs rounded-3xl p-6 text-center">
              <p className="font-sans text-lg font-bold text-white">Set focus time</p>
              <input
                value={editInput}
                onChange={(e) => setEditInput(e.target.value.replace(/[^\d:]/g, "").slice(0, 5))}
                onKeyDown={(e) => e.key === "Enter" && applyEdit()}
                inputMode="numeric"
                placeholder="hh:mm"
                autoFocus
                className="mt-4 w-full rounded-2xl border border-white/25 bg-white/10 px-4 py-3 text-center font-mono text-2xl text-white placeholder:text-white/40 focus:border-white/50 focus:outline-none"
              />
              <div className="mt-3 flex justify-center gap-2">
                {[30, 60].map((m) => (
                  <button key={m} onClick={() => setEditInput(`${m}`)} className="rounded-full border border-white/25 bg-white/5 px-4 py-1 font-mono text-xs text-white/80 transition hover:bg-white/15">
                    {m} min
                  </button>
                ))}
              </div>
              <button onClick={applyEdit} className="mt-5 w-full rounded-2xl bg-white/90 py-3 font-sans font-bold text-purple-900 transition hover:bg-white">Apply</button>
              <button onClick={() => setShowEdit(false)} className="mt-2 font-mono text-[11px] tracking-[0.14em] text-white/55 transition hover:text-white/90">cancel</button>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* back-guard */}
      <AnimatePresence>
        {showGuard && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="absolute inset-0 z-20 grid place-items-center bg-black/50 px-6">
            <motion.div initial={{ scale: 0.92, y: 10 }} animate={{ scale: 1, y: 0 }} className="glass w-full max-w-xs rounded-3xl p-6 text-center">
              <p className="font-sans text-lg font-bold text-white">Going back will cost your focus.</p>
              <p className="mt-1 font-sans text-sm text-white/75">You're mid-session. Sure you want to bail?</p>
              <button onClick={() => setShowGuard(false)} className="mt-5 w-full rounded-2xl bg-white/90 py-3 font-sans font-bold text-purple-900 transition hover:bg-white">Return to timer</button>
              <button onClick={onExit} className="mt-2 w-full rounded-2xl border border-white/25 py-2.5 font-sans text-sm font-semibold text-white/80 transition hover:bg-white/10">Exit task</button>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
