import { getToken } from "./auth";

const DB_API = process.env.NEXT_PUBLIC_DB_API_URL || "http://127.0.0.1:8001";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function parseError(res: Response) {
  try {
    const data = await res.json();
    const detail = data.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) return detail.map((i) => i.msg || JSON.stringify(i)).join("; ");
    return JSON.stringify(data);
  } catch {
    return res.statusText;
  }
}

export async function dbFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const res = await fetch(`${DB_API}${path}`, { ...init, headers });
  if (!res.ok) throw new ApiError(res.status, await parseError(res));
  return res.json() as Promise<T>;
}

export async function photoFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`/api/photo${path}`, init);
  if (!res.ok) throw new ApiError(res.status, await parseError(res));
  if (res.headers.get("content-type")?.includes("application/json")) {
    return res.json() as Promise<T>;
  }
  return res as T;
}

export type Corner = { lat: number; lon: number };

export type Checkpoint = {
  id: string;
  object_id: string;
  object_name?: string | null;
  title: string;
  planned_date: string;
  expected_readiness: number;
  sort_order: number;
  shoot_status: "scheduled" | "available" | "overdue" | "completed" | string;
  actual_shot_at?: string | null;
  date_history?: Array<Record<string, unknown>>;
  address?: string;
  cadastral_number?: string;
  plot_corners?: Corner[];
};

export type BuildingObject = {
  id: string;
  name: string | null;
  cadastral_number: string;
  address: string;
  plot_corners: Corner[];
  status: string;
  material: string | null;
  credit_issued_at: string | null;
  planned_completion_at: string | null;
  is_demo: boolean;
  has_problems: boolean;
  checkpoints: Checkpoint[];
  reports?: Report[];
  created_at?: string | null;
};

export type Report = {
  id: string;
  object_id: string;
  checkpoint_id?: string | null;
  agent_run_id?: string | null;
  raw_json: Record<string, unknown>;
  created_at: string;
};

export type Alert = {
  id: string;
  object_id: string;
  object_name?: string | null;
  report_id?: string | null;
  title: string;
  summary?: string | null;
  severity?: string | null;
  status: string;
  raw_item?: Record<string, unknown> | null;
  created_at: string;
  actions: Array<{
    id: number;
    action: string;
    comment?: string | null;
    actor_name?: string | null;
    created_at: string;
  }>;
};

export type Dashboard = {
  objects_in_progress: number;
  objects_with_problems: number;
  overdue_checkpoints: number;
  upcoming_checkpoints: Checkpoint[];
  recent_alerts: Alert[];
};
