export type Task = {
  id: string;
  title: string;
  status: "active" | "completed";
  type: string;
  created_at?: string;
};

export type TasksResponse = { active: Task[]; completed: Task[] };

const json = async (r: Response) => {
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json();
};

export const api = {
  list: (): Promise<TasksResponse> => fetch("/api/tasks").then(json),
  add: (title: string): Promise<Task> =>
    fetch("/api/tasks", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title }),
    }).then(json),
  setStatus: (id: string, status: "active" | "completed"): Promise<Task> =>
    fetch(`/api/tasks/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    }).then(json),
  remove: (id: string): Promise<{ ok: boolean }> =>
    fetch(`/api/tasks/${id}`, { method: "DELETE" }).then(json),
};
