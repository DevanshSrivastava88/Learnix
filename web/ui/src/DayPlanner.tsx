import { useEffect, useMemo, useRef, useState } from "react";
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
import { type Task } from "./api";

const START_HOUR = 6;
const END_HOUR = 23;
const ROW = 60; // px per hour row

function hourLabel(h: number): string {
  const ap = h < 12 ? "AM" : "PM";
  const hh = h % 12 === 0 ? 12 : h % 12;
  return `${hh} ${ap}`;
}
function hourOf(due: string | null | undefined, day: Date): number | null {
  if (!due) return null;
  const d = new Date(due);
  if (isNaN(d.getTime())) return null;
  if (d.toDateString() !== day.toDateString()) return null;
  return d.getHours();
}
function isoForHour(h: number, day: Date): string {
  const d = new Date(day);
  d.setHours(h, 0, 0, 0);
  return d.toISOString();
}
function startOfDay(d: Date): Date {
  const x = new Date(d);
  x.setHours(0, 0, 0, 0);
  return x;
}
function addDays(d: Date, n: number): Date {
  const x = new Date(d);
  x.setDate(x.getDate() + n);
  return x;
}
// local YYYY-MM-DD (toISOString would shift across the UTC boundary)
function ymd(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

// ── presentational block (used in slots + drag overlay) ─────────────────────
function TaskBlock({ t, dragging }: { t: Task; dragging?: boolean }) {
  return (
    <div
      className={`glass flex items-center gap-2 rounded-xl px-3 py-2.5 ${
        dragging ? "scale-[1.03] shadow-2xl ring-1 ring-white/40" : ""
      }`}
    >
      <span className={`h-7 w-1 rounded-full ${t.type === "habit" ? "bg-acid" : "bg-muted"}`} />
      <div className="min-w-0">
        <p className="truncate font-sans text-sm font-semibold leading-tight text-text">{t.title}</p>
        {t.type === "habit" && <p className="font-mono text-[8px] tracking-[0.14em] text-acid">↻ HABIT</p>}
      </div>
    </div>
  );
}

function DraggableTask({ t }: { t: Task }) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({ id: `plan-${t.id}` });
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
        <div className="grid h-full place-items-center font-mono text-[10px] text-muted-deep">
          {isOver ? "drop here" : "+ add"}
        </div>
      )}
    </div>
  );
}

// Inline day-planner section — shares the task state with the home page: the
// parent owns tasks and persistence, this only renders + raises onMove/onAdd.
export default function DayPlanner({
  tasks: all,
  onMove,
  onAdd,
}: {
  tasks: Task[];
  onMove: (id: string, dueISO: string | null) => void;
  onAdd: (title: string, dueISO: string) => void;
}) {
  const tasks = useMemo(
    () => all.filter((t) => t.status === "active" && !t.title.includes(" — Step ")),
    [all]
  );
  const [activeId, setActiveId] = useState<string | null>(null);
  const [addHour, setAddHour] = useState<number | null>(null);
  const [addTitle, setAddTitle] = useState("");
  const [day, setDay] = useState<Date>(() => startOfDay(new Date()));
  const [nowMin, setNowMin] = useState(() => new Date().getHours() * 60 + new Date().getMinutes());
  const isToday = day.toDateString() === new Date().toDateString();
  const scrollRef = useRef<HTMLDivElement>(null);

  // open with the current hour at the top of the timeline (today only)
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTop = isToday ? Math.max(0, (new Date().getHours() - START_HOUR) * ROW) : 0;
  }, [isToday, day]);

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
      const h = hourOf(t.due, day);
      if (h != null && !m.has(h)) m.set(h, t);
    }
    return m;
  }, [tasks, day]);
  const unscheduled = tasks.filter((t) => hourOf(t.due, day) == null);
  const activeTask = tasks.find((t) => t.id === activeId) || null;

  function onDragStart(e: DragStartEvent) {
    setActiveId(String(e.active.id).replace(/^plan-/, ""));
  }
  function onDragEnd(e: DragEndEvent) {
    const id = String(e.active.id).replace(/^plan-/, "");
    setActiveId(null);
    const over = e.over?.id ? String(e.over.id) : null;
    if (!over) return;
    if (over === "tray") return onMove(id, null);
    if (over.startsWith("slot-")) {
      const h = parseInt(over.slice(5), 10);
      if (byHour.has(h) && byHour.get(h)!.id !== id) return; // occupied → no push (yet)
      onMove(id, isoForHour(h, day));
    }
  }

  function addTask() {
    const title = addTitle.trim();
    const h = addHour;
    setAddHour(null);
    setAddTitle("");
    if (!title || h == null) return;
    onAdd(title, isoForHour(h, day));
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
        <p className="mb-2 font-mono text-[9px] tracking-[0.16em] text-muted">
          UNSCHEDULED / OTHER DAYS — drag onto a slot{isOver ? " · drop to unschedule" : ""}
        </p>
        {unscheduled.length === 0 ? (
          <p className="font-mono text-xs text-muted-deep">nothing unscheduled 🎉</p>
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
  const showNow = isToday && nowMin / 60 >= START_HOUR && nowMin / 60 <= END_HOUR + 1;

  return (
    <div className="mt-10">
      <div className="mb-3 flex items-center gap-3">
        <span className="font-mono text-[10px] tracking-[0.18em] text-muted">// PLAN</span>
        <span className="h-px flex-1 bg-white/10" />
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-sans text-2xl font-extrabold tracking-tight text-text">
          {day.toLocaleDateString([], { weekday: "long", month: "short", day: "numeric" })}
        </h2>
        {/* day switcher: today / tomorrow / any future date */}
        <div className="flex items-center gap-2">
          {([["TODAY", 0], ["TOMORROW", 1]] as const).map(([label, n]) => {
            const target = startOfDay(addDays(new Date(), n));
            const on = day.toDateString() === target.toDateString();
            return (
              <button
                key={label}
                onClick={() => setDay(target)}
                className={`rounded-full border px-3 py-1 font-mono text-[10px] tracking-[0.16em] transition ${
                  on ? "border-acid/60 bg-acid/15 text-acid" : "border-white/10 text-muted hover:text-text"
                }`}
              >
                {label}
              </button>
            );
          })}
          <label className="flex cursor-pointer items-center gap-1.5 rounded-full border border-white/10 px-3 py-1 font-mono text-[10px] tracking-[0.16em] text-muted transition hover:text-text">
            📆
            <input
              type="date"
              value={ymd(day)}
              min={ymd(new Date())}
              onChange={(e) => {
                const [y, m, d] = e.target.value.split("-").map(Number);
                if (y && m && d) setDay(new Date(y, m - 1, d));
              }}
              className="w-[7.5rem] bg-transparent font-mono text-[10px] text-muted outline-none"
            />
          </label>
        </div>
      </div>

      <DndContext sensors={sensors} onDragStart={onDragStart} onDragEnd={onDragEnd}>
        <TrayDrop />

        <div ref={scrollRef} className="scrollbar-soft mt-4 max-h-[440px] overflow-y-auto pr-1">
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
                  <span className="w-12 shrink-0 pt-1 text-right font-mono text-[10px] tracking-[0.1em] text-muted">
                    {hourLabel(h)}
                  </span>
                  <Slot hour={h} task={byHour.get(h)} onAdd={(hr) => { setAddHour(hr); setAddTitle(""); }} />
                </div>
              ))}
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
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-40 grid place-items-center bg-black/50 px-6">
            <motion.div initial={{ scale: 0.92, y: 12 }} animate={{ scale: 1, y: 0 }} className="glass w-full max-w-xs rounded-3xl p-6">
              <p className="font-mono text-[10px] tracking-[0.2em] text-acid">NEW TASK · {hourLabel(addHour)}</p>
              <input
                value={addTitle}
                onChange={(e) => setAddTitle(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && addTask()}
                autoFocus
                placeholder="what needs doing?"
                className="mt-3 w-full rounded-2xl border border-white/10 bg-panel px-4 py-3 font-sans text-base text-text placeholder:text-muted-deep focus:border-acid/40 focus:outline-none"
              />
              <button onClick={addTask} className="mt-4 w-full rounded-2xl bg-acid py-3 font-sans font-bold text-bg transition hover:brightness-110 active:scale-[0.98]">
                Add at {hourLabel(addHour)}
              </button>
              <button onClick={() => setAddHour(null)} className="mt-2 w-full text-center font-mono text-[11px] tracking-[0.14em] text-muted transition hover:text-text">
                cancel
              </button>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
