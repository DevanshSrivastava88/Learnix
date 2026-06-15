export type Task = {
  id: string;
  title: string;
  status: "active" | "completed";
  type: string;
  due?: string | null;
  recurrence?: number | null;
  created_at?: string;
};

export type TasksResponse = { active: Task[]; completed: Task[] };
export type Stats = { streak: number; week_done: number; week_rate: number; cleared: number };
export type DayCell = { date: string; done: number; skipped: number };

export class AuthError extends Error {}

const json = async (r: Response) => {
  if (r.status === 401) throw new AuthError("unauthorized");
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json();
};

// credentials: include so the session cookie rides along
const opts = (extra: RequestInit = {}): RequestInit => ({ credentials: "include", ...extra });

export const api = {
  me: (): Promise<{ uid: number }> => fetch("/api/me", opts()).then(json),
  verify: (code: string): Promise<{ ok: boolean; uid: number }> =>
    fetch("/api/auth/verify", opts({
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code }),
    })).then(json),
  logout: (): Promise<{ ok: boolean }> =>
    fetch("/api/logout", opts({ method: "POST" })).then(json),

  stats: (): Promise<Stats> => fetch("/api/stats", opts()).then(json),
  activity: (): Promise<{ days: DayCell[] }> => fetch("/api/activity", opts()).then(json),

  list: (): Promise<TasksResponse> => fetch("/api/tasks", opts()).then(json),
  add: (title: string): Promise<Task> =>
    fetch("/api/tasks", opts({
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title }),
    })).then(json),
  setStatus: (id: string, status: "active" | "completed"): Promise<Task> =>
    fetch(`/api/tasks/${id}`, opts({
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    })).then(json),
  reschedule: (id: string, dueISO: string | null): Promise<Task> =>
    fetch(`/api/tasks/${id}`, opts({
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ due: dueISO ?? "" }),
    })).then(json),
  remove: (id: string): Promise<{ ok: boolean }> =>
    fetch(`/api/tasks/${id}`, opts({ method: "DELETE" })).then(json),
};
