import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import { api, type Task } from "./api";

const START_HOUR = 6;
const END_HOUR = 23; // 6 AM .. 11 PM

function hourLabel(h: number): string {
  const ap = h < 12 ? "AM" : "PM";
  const hh = h % 12 === 0 ? 12 : h % 12;
  return `${hh} ${ap}`;
}

function hourOf(due?: string | null): number | null {
  if (!due) return null;
  const d = new Date(due);
  if (isNaN(d.getTime())) return null;
  const today = new Date();
  if (d.toDateString() !== today.toDateString()) return null; // only today's slots
  return d.getHours();
}

function isoForHour(h: number): string {
  const d = new Date();
  d.setHours(h, 0, 0, 0);
  return d.toISOString();
}

export default function DayPlanner({
  tasks: initial,
  onClose,
}: {
  tasks: Task[];
  onClose: (changed: boolean) => void;
}) {
  // only active, non-subtask tasks are plannable
  const [tasks, setTasks] = useState<Task[]>(() =>
    initial.filter((t) => t.status === "active" && !t.title.includes(" — Step "))
  );
  const [dragId, setDragId] = useState<string | null>(null);
  const [overHour, setOverHour] = useState<number | "tray" | null>(null);
  const [changed, setChanged] = useState(false);

  const hours = useMemo(() => {
    const arr: number[] = [];
    for (let h = START_HOUR; h <= END_HOUR; h++) arr.push(h);
    return arr;
  }, []);

  const byHour = useMemo(() => {
    const m = new Map<number, Task>();
    for (const t of tasks) {
      const h = hourOf(t.due);
      if (h != null && !m.has(h)) m.set(h, t); // one per slot (no stacking for now)
    }
    return m;
  }, [tasks]);

  const unscheduled = tasks.filter((t) => hourOf(t.due) == null);

  async function move(id: string, dueISO: string | null) {
    const prev = tasks;
    setTasks((ts) => ts.map((t) => (t.id === id ? { ...t, due: dueISO } : t)));
    setChanged(true);
    try {
      await api.reschedule(id, dueISO);
    } catch {
      setTasks(prev); // revert on failure
    }
  }

  function dropOnHour(h: number) {
    setOverHour(null);
    if (!dragId) return;
    if (byHour.has(h) && byHour.get(h)!.id !== dragId) return; // occupied → reject (no push yet)
    move(dragId, isoForHour(h));
    setDragId(null);
  }

  function dropOnTray() {
    setOverHour(null);
    if (!dragId) return;
    move(dragId, null); // unschedule
    setDragId(null);
  }

  const TaskCard = ({ t, compact }: { t: Task; compact?: boolean }) => (
    <div
      draggable
      onDragStart={() => setDragId(t.id)}
      onDragEnd={() => { setDragId(null); setOverHour(null); }}
      className={`glass cursor-grab select-none rounded-xl px-3 py-2 active:cursor-grabbing ${
        dragId === t.id ? "opacity-40" : ""
      } ${compact ? "" : "w-full"}`}
    >
      <p className="truncate font-sans text-sm font-semibold text-white">{t.title}</p>
      {t.type === "habit" && <p className="font-mono text-[8px] tracking-[0.14em] text-acid">↻ HABIT</p>}
    </div>
  );

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 overflow-hidden"
    >
      {/* dreamy backdrop, heavily blurred so the glass timeline reads clearly */}
      <div className="absolute inset-0 bg-cover bg-center" style={{ backgroundImage: "url(/focus-bg.png)" }} />
      <div className="absolute inset-0 bg-[#0a0613]/80 backdrop-blur-2xl" />

      <div className="relative z-10 mx-auto flex h-full max-w-2xl flex-col px-5 py-6">
        {/* header */}
        <div className="flex items-center justify-between">
          <div>
            <p className="font-mono text-[10px] tracking-[0.28em] text-acid">PLAN YOUR DAY</p>
            <h1 className="mt-1 font-sans text-3xl font-extrabold tracking-tight text-white">
              {new Date().toLocaleDateString([], { weekday: "long", month: "short", day: "numeric" })}
            </h1>
          </div>
          <button
            onClick={() => onClose(changed)}
            className="glass rounded-full px-4 py-2 font-mono text-[10px] tracking-[0.16em] text-white transition hover:bg-white/20"
          >
            ✓ DONE
          </button>
        </div>

        {/* unscheduled tray */}
        <div
          onDragOver={(e) => { e.preventDefault(); setOverHour("tray"); }}
          onDrop={dropOnTray}
          className={`mt-4 rounded-2xl border p-3 transition ${
            overHour === "tray" ? "border-acid/60 bg-acid/10" : "border-white/10 bg-white/[0.04]"
          }`}
        >
          <p className="mb-2 font-mono text-[9px] tracking-[0.16em] text-white/50">
            UNSCHEDULED — drag onto a free slot {overHour === "tray" && "· drop to unschedule"}
          </p>
          {unscheduled.length === 0 ? (
            <p className="font-mono text-xs text-white/30">nothing unscheduled 🎉</p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {unscheduled.map((t) => (
                <div key={t.id} className="max-w-[48%]"><TaskCard t={t} compact /></div>
              ))}
            </div>
          )}
        </div>

        {/* timeline */}
        <div className="scrollbar-soft mt-4 flex-1 space-y-1.5 overflow-y-auto pr-1">
          {hours.map((h) => {
            const t = byHour.get(h);
            const isOver = overHour === h;
            const free = !t;
            return (
              <div key={h} className="flex items-stretch gap-3">
                <span className="w-14 shrink-0 pt-2 text-right font-mono text-[10px] tracking-[0.12em] text-white/45">
                  {hourLabel(h)}
                </span>
                <div
                  onDragOver={(e) => { if (free) { e.preventDefault(); setOverHour(h); } }}
                  onDragLeave={() => setOverHour((o) => (o === h ? null : o))}
                  onDrop={() => dropOnHour(h)}
                  className={`min-h-[48px] flex-1 rounded-xl border transition ${
                    isOver && free
                      ? "border-acid/60 bg-acid/10"
                      : t
                      ? "border-transparent"
                      : "border-dashed border-white/10 bg-white/[0.02] hover:border-white/20"
                  }`}
                >
                  {t ? <div className="p-1.5"><TaskCard t={t} /></div> : (
                    <div className="grid h-full min-h-[48px] place-items-center font-mono text-[9px] text-white/15">
                      {isOver && free ? "drop here" : ""}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </motion.div>
  );
}
