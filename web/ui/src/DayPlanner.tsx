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
const PANE = 440; // timeline viewport height — bottom spacer lets ANY hour scroll to the top

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

const BADGE: Record<string, { label: string; cls: string }> = {
  habit: { label: "↻ HABIT", cls: "border-acid/30 text-acid" },
  study: { label: "✦ STUDY", cls: "border-sky-400/30 text-sky-300" },
  milestone: { label: "◈ GOAL", cls: "border-fuchsia-400/30 text-fuchsia-300" },
};

// a habit anchored at its due date repeats every `recurrence` days at the
// same clock time — project it onto any day on its cadence
function habitOccursOn(t: Task, day: Date): boolean {
  if (t.type !== "habit" || !t.due) return false;
  const d = new Date(t.due);
  if (isNaN(d.getTime())) return false;
  const anchor = startOfDay(d).getTime();
  const target = startOfDay(day).getTime();
  if (target < anchor) return false;
  const rec = t.recurrence && t.recurrence > 0 ? t.recurrence : 1;
  const diffDays = Math.round((target - anchor) / 86400000);
  return diffDays % rec === 0;
}

// which hour a task occupies on the viewed day (habits project forward)
function slotHour(t: Task, day: Date): number | null {
  if (t.type === "habit" && t.due) {
    const d = new Date(t.due);
    if (!isNaN(d.getTime())) return habitOccursOn(t, day) ? d.getHours() : null;
  }
  return hourOf(t.due, day);
}

// when a task is due on a DIFFERENT day than the one being viewed, say so
function dueChip(due: string | null | undefined, day: Date): string | null {
  if (!due) return null;
  const d = new Date(due);
  if (isNaN(d.getTime())) return null;
  if (d.toDateString() === day.toDateString()) return null; // its slot shows it
  const now = new Date();
  const time = d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  if (d.toDateString() === now.toDateString()) return `today ${time}`;
  if (d.toDateString() === addDays(now, 1).toDateString()) return `tmrw ${time}`;
  return `${d.toLocaleDateString([], { month: "short", day: "numeric" })} ${time}`;
}

type TaskActions = {
  onToggle: (t: Task) => void;
  onRepeat: (t: Task) => void; // habit → untoggle; task → opens the time dialog
  onRemove: (t: Task) => void;
  onOpen: (t: Task) => void;
};

// stop pointerdown so pressing a control never starts a drag
const stopDrag = { onPointerDown: (e: React.PointerEvent) => e.stopPropagation() };

// ── task chip with full controls (tray + slots + drag overlay) ──────────────
function TaskBlock({ t, day, actions, inSlot, dragging }: { t: Task; day: Date; actions: TaskActions; inSlot?: boolean; dragging?: boolean }) {
  const badge = BADGE[t.type];
  const chip = dueChip(t.due, day);
  // repeat toggle: habits always show it (status + untoggle); plain tasks only
  // once scheduled into a slot — schedule first, then make it repeat
  const showRepeat = t.type === "habit" || (t.type === "task" && inSlot);
  return (
    <div
      className={`glass flex items-center gap-2 rounded-xl px-2.5 py-2 ${
        dragging ? "scale-[1.03] shadow-2xl ring-1 ring-white/40" : ""
      }`}
    >
      <button
        {...stopDrag}
        onClick={(e) => { e.stopPropagation(); actions.onToggle(t); }}
        aria-label="mark done"
        title="Mark done"
        className="grid h-5 w-5 shrink-0 place-items-center rounded-md border border-white/25 transition hover:border-acid active:scale-90"
      />
      <div
        onClick={(e) => { e.stopPropagation(); actions.onOpen(t); }}
        title="Start a focus session"
        className="min-w-0 flex-1 cursor-pointer"
      >
        <p className="truncate font-sans text-sm font-semibold leading-tight text-text">{t.title}</p>
        {(badge || chip) && (
          <p className="mt-0.5 flex items-center gap-1.5 font-mono text-[8px] tracking-[0.12em]">
            {badge && <span className={badge.cls.split(" ")[1]}>{badge.label}</span>}
            {chip && <span className="text-muted">⏰ {chip}</span>}
          </p>
        )}
      </div>
      {showRepeat && (
        <button
          {...stopDrag}
          onClick={(e) => { e.stopPropagation(); actions.onRepeat(t); }}
          aria-label="toggle repeat"
          title={t.type === "habit" ? "Repeats daily — tap to make one-off" : "Make repeatable (daily)"}
          className={`grid h-5 w-5 shrink-0 place-items-center rounded-full border text-[10px] transition ${
            t.type === "habit"
              ? "border-acid/60 bg-acid/15 text-acid"
              : "border-white/10 text-muted hover:border-acid/40 hover:text-acid"
          }`}
        >
          ↻
        </button>
      )}
      <button
        {...stopDrag}
        onClick={(e) => { e.stopPropagation(); actions.onRemove(t); }}
        aria-label="delete task"
        title="Delete"
        className="grid h-5 w-5 shrink-0 place-items-center rounded-md border border-white/10 text-xs text-muted transition hover:border-red/40 hover:text-red"
      >
        ×
      </button>
    </div>
  );
}

function DraggableTask({ t, day, actions, inSlot }: { t: Task; day: Date; actions: TaskActions; inSlot?: boolean }) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({ id: `plan-${t.id}` });
  return (
    <div
      ref={setNodeRef}
      {...listeners}
      {...attributes}
      style={{ touchAction: "none" }}
      className={`cursor-grab active:cursor-grabbing ${isDragging ? "opacity-30" : ""}`}
    >
      <TaskBlock t={t} day={day} actions={actions} inSlot={inSlot} />
    </div>
  );
}

function Slot({ hour, task, day, actions, onAdd }: { hour: number; task?: Task; day: Date; actions: TaskActions; onAdd: (h: number) => void }) {
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
        <div className="p-1"><DraggableTask t={task} day={day} actions={actions} inSlot /></div>
      ) : (
        <div className="grid h-full place-items-center font-mono text-[10px] text-muted-deep">
          {isOver ? "drop here" : "+ add"}
        </div>
      )}
    </div>
  );
}

// The active-task view: scheduled tasks sit in the timeline, everything else
// in the UNSCHEDULED tray. Parent owns task state + persistence.
export default function DayPlanner({
  tasks: all,
  onMove,
  onAdd,
  onToggle,
  onRepeat,
  onRemove,
  onOpen,
}: {
  tasks: Task[];
  onMove: (id: string, dueISO: string | null) => void;
  onAdd: (title: string, dueISO: string) => void;
  onToggle: (t: Task) => void;
  onRepeat: (t: Task, dueISO?: string | null) => void;
  onRemove: (t: Task) => void;
  onOpen: (t: Task) => void;
}) {
  const tasks = useMemo(() => all.filter((t) => t.status === "active"), [all]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [addHour, setAddHour] = useState<number | null>(null);
  const [addTitle, setAddTitle] = useState("");
  const [repeatFor, setRepeatFor] = useState<Task | null>(null);
  const [repeatTime, setRepeatTime] = useState("09:00");

  // habit → untoggle straight away; task → ask what time it repeats daily
  const actions: TaskActions = {
    onToggle,
    onRemove,
    onOpen,
    onRepeat: (t: Task) => {
      if (t.type === "habit") return onRepeat(t);
      const d = t.due ? new Date(t.due) : null;
      setRepeatTime(
        d && !isNaN(d.getTime())
          ? `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`
          : "09:00"
      );
      setRepeatFor(t);
    },
  };

  function confirmRepeat() {
    const t = repeatFor;
    setRepeatFor(null);
    if (!t) return;
    let iso: string | undefined;
    if (repeatTime) {
      const [hh, mm] = repeatTime.split(":").map(Number);
      const d = new Date(day);
      d.setHours(hh || 0, mm || 0, 0, 0);
      iso = d.toISOString();
    }
    onRepeat(t, iso);
  }
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

  // tap vs drag: pointer needs 8px move; touch needs a short hold — so taps
  // (checkbox, title, buttons, empty slot) still click, hold+drag moves.
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
      const h = slotHour(t, day);
      if (h != null && !m.has(h)) m.set(h, t);
    }
    return m;
  }, [tasks, day]);
  // tray: not on this day's timeline — true unscheduled first, then other-day
  // tasks by due time
  const unscheduled = useMemo(() => {
    const ts = (t: Task) => {
      const n = t.due ? new Date(t.due).getTime() : NaN;
      return isNaN(n) ? -Infinity : n;
    };
    return tasks.filter((t) => slotHour(t, day) == null).sort((a, b) => ts(a) - ts(b));
  }, [tasks, day]);
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
        className={`rounded-2xl border p-3 transition ${
          isOver ? "border-acid/60 bg-acid/10" : "border-white/10 bg-white/[0.04]"
        }`}
      >
        <p className="mb-2 font-mono text-[9px] tracking-[0.16em] text-muted">
          UNSCHEDULED — drag onto a slot{isOver ? " · drop to unschedule" : ""}
        </p>
        {unscheduled.length === 0 ? (
          <p className="font-mono text-xs text-muted-deep">nothing unscheduled 🎉</p>
        ) : (
          <div className="flex flex-col gap-2">
            {unscheduled.map((t) => (
              <DraggableTask key={t.id} t={t} day={day} actions={actions} />
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
    <div className="mt-9">
      <div className="mb-3 flex items-center gap-3">
        <span className="font-mono text-[10px] tracking-[0.18em] text-muted">// ACTIVE</span>
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
        {/* timeline left, unscheduled tray right (stacked on small screens) */}
        <div className="mt-4 grid items-start gap-4 sm:grid-cols-[1fr_280px]">
          <div
            ref={scrollRef}
            style={{ maxHeight: PANE }}
            className="scrollbar-soft order-2 overflow-y-auto pr-1 sm:order-1"
          >
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
                    <Slot hour={h} task={byHour.get(h)} day={day} actions={actions} onAdd={(hr) => { setAddHour(hr); setAddTitle(""); }} />
                  </div>
                ))}
              </div>
              {/* spacer so late hours can still scroll to the top of the pane */}
              <div style={{ height: PANE - ROW }} aria-hidden />
            </div>
          </div>
          <div className="order-1 sm:order-2">
            <TrayDrop />
          </div>
        </div>

        <DragOverlay dropAnimation={{ duration: 200, easing: "cubic-bezier(0.22,1,0.36,1)" }}>
          {activeTask ? <div className="w-64"><TaskBlock t={activeTask} day={day} actions={actions} dragging /></div> : null}
        </DragOverlay>
      </DndContext>

      {/* repeat-time dialog: making a task a habit asks what time it repeats */}
      <AnimatePresence>
        {repeatFor && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-40 grid place-items-center bg-black/50 px-6">
            <motion.div initial={{ scale: 0.92, y: 12 }} animate={{ scale: 1, y: 0 }} className="glass w-full max-w-xs rounded-3xl p-6">
              <p className="font-mono text-[10px] tracking-[0.2em] text-acid">↻ REPEAT DAILY</p>
              <p className="mt-2 truncate font-sans text-base font-semibold text-text">{repeatFor.title}</p>
              <label className="mt-4 block font-mono text-[10px] tracking-[0.18em] text-muted">AT WHAT TIME, EVERY DAY?</label>
              <input
                type="time"
                value={repeatTime}
                onChange={(e) => setRepeatTime(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && confirmRepeat()}
                autoFocus
                className="mt-2 w-full rounded-2xl border border-white/10 bg-panel px-4 py-3 text-center font-mono text-xl text-text focus:border-acid/40 focus:outline-none"
              />
              <button onClick={confirmRepeat} className="mt-4 w-full rounded-2xl bg-acid py-3 font-sans font-bold text-bg transition hover:brightness-110 active:scale-[0.98]">
                Repeat daily
              </button>
              <button onClick={() => setRepeatFor(null)} className="mt-2 w-full text-center font-mono text-[11px] tracking-[0.14em] text-muted transition hover:text-text">
                cancel
              </button>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

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
