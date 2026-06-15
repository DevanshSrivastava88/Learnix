import { useEffect, useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  TouchSensor,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import { api, type Task } from "./api";

const START_HOUR = 6;
const END_HOUR = 23;
const ROW = 60; // px per hour row

function hourLabel(h: number): string {
  const ap = h < 12 ? "AM" : "PM";
  const hh = h % 12 === 0 ? 12 : h % 12;
  return `${hh} ${ap}`;
}
function hourOf(due?: string | null): number | null {
  if (!due) return null;
  const d = new Date(due);
  if (isNaN(d.getTime())) return null;
  if (d.toDateString() !== new Date().toDateString()) return null;
  return d.getHours();
}
function isoForHour(h: number): string {
  const d = new Date();
  d.setHours(h, 0, 0, 0);
  return d.toISOString();
}

// ── presentational block (used in slots + drag overlay) ─────────────────────
function TaskBlock({ t, dragging }: { t: Task; dragging?: boolean }) {
  return (
    <div
      className={`glass flex items-center gap-2 rounded-xl px-3 py-2.5 ${
        dragging ? "scale-[1.03] shadow-2xl ring-1 ring-white/40" : ""
      }`}
    >
      <span className={`h-7 w-1 rounded-full ${t.type === "habit" ? "bg-acid" : "bg-white/70"}`} />
      <div className="min-w-0">
        <p className="truncate font-sans text-sm font-semibold leading-tight text-white">{t.title}</p>
        {t.type === "habit" && <p className="font-mono text-[8px] tracking-[0.14em] text-acid">↻ HABIT</p>}
      </div>
    </div>
  );
}

function DraggableTask({ t }: { t: Task }) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({ id: t.id });
  return (
    <div
      ref={setNodeRef}
      {...listeners}
      {...attributes}
      style={{ touchAction: "none" }}
      className={`cursor-grab active:cursor-grabbing ${isDragging ? "opacity-30" : ""}`}
    >
      <TaskBlock t={t} />
    </div>
  );
}

function Slot({ hour, task, onAdd }: { hour: number; task?: Task; onAdd: (h: number) => void }) {
  const { setNodeRef, isOver } = useDroppable({ id: `slot-${hour}` });
  const free = !task;
  return (
    <div
      ref={setNodeRef}
      onClick={() => free && onAdd(hour)}
      style={{ minHeight: ROW - 8 }}
      className={`flex-1 rounded-xl border transition ${
        isOver && free
          ? "border-acid/70 bg-acid/15"
          : task
          ? "border-transparent"
          : "cursor-pointer border-dashed border-white/10 bg-white/[0.02] hover:border-white/25 hover:bg-white/[0.05]"
      }`}
    >
      {task ? (
        <div className="p-1"><DraggableTask t={task} /></div>
      ) : (
        <div className="grid h-full place-items-center font-mono text-[10px] text-white/15">
          {isOver ? "drop here" : "+ add"}
        </div>
      )}
    </div>
  );
}

export default function DayPlanner({
  tasks: initial,
  onClose,
}: {
  tasks: Task[];
  onClose: (changed: boolean) => void;
}) {
  const [tasks, setTasks] = useState<Task[]>(() =>
    initial.filter((t) => t.status === "active" && !t.title.includes(" — Step "))
  );
  const [activeId, setActiveId] = useState<string | null>(null);
  const [changed, setChanged] = useState(false);
  const [addHour, setAddHour] = useState<number | null>(null);
  const [addTitle, setAddTitle] = useState("");
  const [nowMin, setNowMin] = useState(() => new Date().getHours() * 60 + new Date().getMinutes());

  useEffect(() => {
    const id = setInterval(() => {
      const n = new Date();
      setNowMin(n.getHours() * 60 + n.getMinutes());
    }, 30000);
    return () => clearInterval(id);
  }, []);

  // tap vs drag: pointer needs 8px move; touch needs a short hold — so a tap
  // still opens the add dialog, a hold+drag moves the task.
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 180, tolerance: 8 } })
  );

  const hours = useMemo(() => {
    const a: number[] = [];
    for (let h = START_HOUR; h <= END_HOUR; h++) a.push(h);
    return a;
  }, []);
  const byHour = useMemo(() => {
    const m = new Map<number, Task>();
    for (const t of tasks) {
      const h = hourOf(t.due);
      if (h != null && !m.has(h)) m.set(h, t);
    }
    return m;
  }, [tasks]);
  const unscheduled = tasks.filter((t) => hourOf(t.due) == null);
  const activeTask = tasks.find((t) => t.id === activeId) || null;

  async function move(id: string, dueISO: string | null) {
    const prev = tasks;
    setTasks((ts) => ts.map((t) => (t.id === id ? { ...t, due: dueISO } : t)));
    setChanged(true);
    try {
      await api.reschedule(id, dueISO);
    } catch {
      setTasks(prev);
    }
  }

  function onDragStart(e: DragStartEvent) {
    setActiveId(String(e.active.id));
  }
  function onDragEnd(e: DragEndEvent) {
    const id = String(e.active.id);
    setActiveId(null);
    const over = e.over?.id ? String(e.over.id) : null;
    if (!over) return;
    if (over === "tray") return move(id, null);
    if (over.startsWith("slot-")) {
      const h = parseInt(over.slice(5), 10);
      if (byHour.has(h) && byHour.get(h)!.id !== id) return; // occupied → no push (yet)
      move(id, isoForHour(h));
    }
  }

  async function addTask() {
    const title = addTitle.trim();
    const h = addHour;
    setAddHour(null);
    setAddTitle("");
    if (!title || h == null) return;
    const temp: Task = { id: `tmp-${Date.now()}`, title, status: "active", type: "task", due: isoForHour(h) };
    setTasks((ts) => [...ts, temp]);
    setChanged(true);
    try {
      const real = await api.add(title, isoForHour(h));
      setTasks((ts) => ts.map((t) => (t.id === temp.id ? real : t)));
    } catch {
      setTasks((ts) => ts.filter((t) => t.id !== temp.id));
    }
  }

  const TrayDrop = () => {
    const { setNodeRef, isOver } = useDroppable({ id: "tray" });
    return (
      <div
        ref={setNodeRef}
        className={`mt-4 rounded-2xl border p-3 transition ${
          isOver ? "border-acid/60 bg-acid/10" : "border-white/10 bg-white/[0.04]"
        }`}
      >
        <p className="mb-2 font-mono text-[9px] tracking-[0.16em] text-white/50">
          UNSCHEDULED — drag onto a slot{isOver ? " · drop to unschedule" : ""}
        </p>
        {unscheduled.length === 0 ? (
          <p className="font-mono text-xs text-white/30">nothing unscheduled 🎉</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {unscheduled.map((t) => (
              <div key={t.id} className="min-w-[44%] flex-1"><DraggableTask t={t} /></div>
            ))}
          </div>
        )}
      </div>
    );
  };

  // now-line offset within the timeline
  const nowTop = ((nowMin / 60) - START_HOUR) * ROW;
  const showNow = nowMin / 60 >= START_HOUR && nowMin / 60 <= END_HOUR + 1;

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-50 overflow-hidden">
      <div className="absolute inset-0 bg-cover bg-center" style={{ backgroundImage: "url(/focus-bg.png)" }} />
      <div className="absolute inset-0 bg-[#0a0613]/82 backdrop-blur-2xl" />

      <DndContext sensors={sensors} onDragStart={onDragStart} onDragEnd={onDragEnd}>
        <div className="relative z-10 mx-auto flex h-full max-w-2xl flex-col px-5 py-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-mono text-[10px] tracking-[0.28em] text-acid">PLAN YOUR DAY</p>
              <h1 className="mt-1 font-sans text-3xl font-extrabold tracking-tight text-white">
                {new Date().toLocaleDateString([], { weekday: "long", month: "short", day: "numeric" })}
              </h1>
            </div>
            <button onClick={() => onClose(changed)} className="glass rounded-full px-4 py-2 font-mono text-[10px] tracking-[0.16em] text-white transition hover:bg-white/20">
              ✓ DONE
            </button>
          </div>

          <TrayDrop />

          <div className="scrollbar-soft mt-4 flex-1 overflow-y-auto pr-1">
            <div className="relative">
              {showNow && (
                <div className="pointer-events-none absolute inset-x-0 z-10 flex items-center" style={{ top: nowTop }}>
                  <span className="ml-12 h-2 w-2 rounded-full bg-acid shadow-glow" />
                  <span className="h-px flex-1 bg-acid/70" />
                </div>
              )}
              <div className="space-y-2">
                {hours.map((h) => (
                  <div key={h} className="flex items-stretch gap-3" style={{ minHeight: ROW - 8 }}>
                    <span className="w-12 shrink-0 pt-1 text-right font-mono text-[10px] tracking-[0.1em] text-white/40">
                      {hourLabel(h)}
                    </span>
                    <Slot hour={h} task={byHour.get(h)} onAdd={(hr) => { setAddHour(hr); setAddTitle(""); }} />
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        <DragOverlay dropAnimation={{ duration: 200, easing: "cubic-bezier(0.22,1,0.36,1)" }}>
          {activeTask ? <div className="w-64"><TaskBlock t={activeTask} dragging /></div> : null}
        </DragOverlay>
      </DndContext>

      {/* tap-to-add dialog */}
      <AnimatePresence>
        {addHour != null && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="absolute inset-0 z-30 grid place-items-center bg-black/50 px-6">
            <motion.div initial={{ scale: 0.92, y: 12 }} animate={{ scale: 1, y: 0 }} className="glass w-full max-w-xs rounded-3xl p-6">
              <p className="font-mono text-[10px] tracking-[0.2em] text-acid">NEW TASK · {hourLabel(addHour)}</p>
              <input
                value={addTitle}
                onChange={(e) => setAddTitle(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && addTask()}
                autoFocus
                placeholder="what needs doing?"
                className="mt-3 w-full rounded-2xl border border-white/25 bg-white/10 px-4 py-3 font-sans text-base text-white placeholder:text-white/40 focus:border-white/50 focus:outline-none"
              />
              <button onClick={addTask} className="mt-4 w-full rounded-2xl bg-white/90 py-3 font-sans font-bold text-purple-900 transition hover:bg-white active:scale-[0.98]">
                Add at {hourLabel(addHour)}
              </button>
              <button onClick={() => setAddHour(null)} className="mt-2 w-full text-center font-mono text-[11px] tracking-[0.14em] text-white/55 transition hover:text-white/90">
                cancel
              </button>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
