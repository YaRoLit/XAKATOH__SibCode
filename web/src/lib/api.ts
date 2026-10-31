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
  overdue_count?: number;
  open_count?: number;
  checkpoint_titles?: string[];
};

export type PriceComparable = {
  title?: string;
  address?: string;
  price?: number;
  area_m2?: number | null;
  land_sotka?: number | null;
  condition?: string;
  completion_percent?: number | null;
  source_name?: string;
  url?: string | null;
  note?: string | null;
  is_mock?: boolean;
};

export type PriceReport = {
  id: number;
  task_id: number;
  object_id: string;
  value_min: number;
  value_point: number;
  value_max: number;
  currency: string;
  justification: string;
  comparables: PriceComparable[];
  confidence?: number | null;
  data_source?: string;
  is_mock: boolean;
  prompt_version?: string;
  created_at?: string;
};

export type PriceEstimate = {
  can_estimate: boolean;
  has_active_task?: boolean;
  task?: {
    id: number;
    status: string;
    error_message?: string | null;
    created_at?: string;
    completed_at?: string | null;
  } | null;
  report?: PriceReport | null;
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
  last_photo_at?: string | null;
  new_photo?: boolean;
  checkpoints: Checkpoint[];
  reports?: Report[];
  created_at?: string | null;
  recent_surveys?: Array<{
    survey_id: number;
    filename: string;
    status: string;
    s3_key?: string | null;
    created_at?: string;
  }>;
  analysis_jobs?: Array<{
    id: number;
    survey_id: number;
    status: string;
    created_at?: string;
    completed_at?: string | null;
  }>;
  price_estimate?: PriceEstimate;
};

export type Report = {
  id: string;
  object_id: string;
  source?: string;
  checkpoint_id?: string | null;
  agent_run_id?: string | null;
  raw_json: Record<string, unknown>;
  created_at: string;
  html_url?: string | null;
  agent_status?: string | null;
};

export type ConstructionPlan = {
  description: string;
};

export type RegistryImportResult = {
  created: Array<{ id: string; name: string | null; cadastral_number: string; row: number }>;
  skipped: Array<{ row: number; cadastral_number: string; reason: string }>;
  errors: Array<{ row: number; cadastral_number?: string; error: string }>;
  created_count: number;
  skipped_count: number;
  error_count: number;
  total_rows: number;
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
  recent_photos?: Alert[];
};
