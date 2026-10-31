import { Badge, Card } from "@/components/ui";
import { aiTone, formatDateTime } from "@/lib/status";
import type { Report } from "@/lib/api";

type BBox = { xmin?: unknown; ymin?: unknown; xmax?: unknown; ymax?: unknown };

function num(value: unknown) {
  const n = Number(value);
  return Number.isFinite(n) ? n : 0;
}

function clampPct(value: number) {
  return Math.min(100, Math.max(0, value));
}

function bboxStyle(bbox: BBox) {
  const xmin = num(bbox.xmin);
  const ymin = num(bbox.ymin);
  const xmax = num(bbox.xmax);
  const ymax = num(bbox.ymax);
  const scale = Math.max(xmin, ymin, xmax, ymax) > 100 ? 10 : 1;
  const left = clampPct(xmin / scale);
  const top = clampPct(ymin / scale);
  const width = clampPct((xmax - xmin) / scale);
  const height = clampPct((ymax - ymin) / scale);
  return {
    left: `${left}%`,
    top: `${top}%`,
    width: `${Math.min(width, 100 - left)}%`,
    height: `${Math.min(height, 100 - top)}%`,
  };
}

function cropImageUrl(storageKey: unknown, htmlUrl?: string) {
  if (typeof storageKey !== "string" || !storageKey || !htmlUrl) return null;
  const base = htmlUrl.replace(/\/agent_reports\/.*$/, "");
  return `${base}/${storageKey.replace(/^\/+/, "")}`;
}

export function AiReportView({ report }: { report: Report }) {
  const raw = report.raw_json || {};
  const stages = Array.isArray(raw.stages) ? raw.stages : [];
  const problems = Array.isArray(raw.problems) ? raw.problems : [];
  const comments = Array.isArray(raw.comments) ? raw.comments : [];
  const checklist = Array.isArray(raw.checklist) ? raw.checklist : [];
  const crops = Array.isArray(raw.crops_meta) ? raw.crops_meta : [];
  const overall = raw.overall_status as string | undefined;
  const pct = (raw.overall_readiness_pct ?? raw.progress_percent) as number | undefined;
  const htmlUrl = report.html_url || (raw.html_url as string | undefined);

  return (
    <Card className="min-w-0 max-w-full overflow-hidden p-5">
      <div className="mb-4 flex min-w-0 flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs uppercase tracking-[0.16em] text-muted">
            {report.source === "analysis" ? "Анализ агента" : "AI-отчёт"}
          </p>
          <p className="font-serif text-xl">{pct != null ? `${pct}% готовности` : "Результат агента"}</p>
          <p className="break-words text-xs text-muted">
            {formatDateTime(report.created_at)}
            {report.agent_status ? ` · ${report.agent_status}` : ""}
            {raw.movement_status ? ` · ${String(raw.movement_status)}` : ""}
          </p>
        </div>
        {overall ? <Badge className={aiTone[overall] || "bg-line text-muted"}>{overall}</Badge> : null}
      </div>

      {htmlUrl ? (
        <p className="mb-4">
          <a className="text-sm text-forest underline" href={htmlUrl} target="_blank" rel="noreferrer">
            Открыть HTML-отчёт
          </a>
        </p>
      ) : null}

      {typeof raw.progress_comment === "string" ? (
        <p className="mb-3 break-words text-sm text-muted">{raw.progress_comment}</p>
      ) : null}
      {typeof raw.stage_progress_comment === "string" ? (
        <p className="mb-3 break-words text-sm text-muted">{raw.stage_progress_comment}</p>
      ) : null}

      {stages.length > 0 ? (
        <div className="mb-4 grid min-w-0 gap-2 md:grid-cols-3">
          {stages.map((stage: Record<string, unknown>, i: number) => (
            <div key={i} className="min-w-0 rounded-xl bg-paper px-3 py-2">
              <div className="flex items-center justify-between gap-2">
                <p className="min-w-0 break-words text-sm">{String(stage.name || "Стадия")}</p>
                <Badge className={aiTone[String(stage.status)] || "bg-line text-muted"}>
                  {String(stage.status || "—")}
                </Badge>
              </div>
              <p className="mt-1 font-serif text-2xl">{String(stage.readiness_pct ?? "—")}%</p>
            </div>
          ))}
        </div>
      ) : null}

      {comments.length > 0 ? (
        <ul className="mb-4 list-disc space-y-1 pl-5 text-sm text-muted">
          {comments.map((c, i) => (
            <li key={i} className="break-words">{String(c)}</li>
          ))}
        </ul>
      ) : null}

      {problems.length > 0 ? (
        <div className="mb-4 space-y-2">
          {problems.map((item: Record<string, unknown>, i: number) => (
            <div key={i} className="min-w-0 rounded-xl border border-line px-3 py-2 text-sm">
              <p className="break-words font-medium">{String(item.title || item.code || "Проблема")}</p>
              <p className="break-words text-muted">{String(item.description || item.summary || "")}</p>
            </div>
          ))}
        </div>
      ) : null}

      {checklist.length > 0 ? (
        <div className="mb-4 min-w-0">
          <h3 className="mb-2 text-sm font-medium">Чек-лист маркеров</h3>
          <div className="space-y-2">
            {checklist.map((item: Record<string, unknown>, i: number) => (
              <div key={i} className="min-w-0 rounded-xl border border-line px-3 py-2 text-sm">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="min-w-0 break-words font-medium">{String(item.feature || "Признак")}</p>
                  <Badge className="bg-paper text-muted">{String(item.status || "—")}</Badge>
                </div>
                <p className="mt-1 break-words text-muted">
                  {item.photo_index != null ? `Фото ${String(item.photo_index)}` : ""}
                  {item.photo_index != null && item.location ? " · " : ""}
                  {item.location ? String(item.location) : ""}
                </p>
                {item.note ? <p className="mt-1 break-words text-xs text-muted">{String(item.note)}</p> : null}
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {crops.length > 0 ? (
        <div className="mb-4 min-w-0">
          <h3 className="mb-2 text-sm font-medium">Разметка кропов</h3>
          <div className="grid min-w-0 gap-3 md:grid-cols-2">
            {crops.map((crop: Record<string, unknown>, i: number) => {
              const src = cropImageUrl(crop.storage_key, htmlUrl);
              const bbox = crop.bbox && typeof crop.bbox === "object" ? (crop.bbox as BBox) : null;
              return (
                <div key={i} className="min-w-0 overflow-hidden rounded-xl bg-paper p-3">
                  {src ? (
                    <img src={src} alt={`Кроп ${String(crop.index || i + 1)}`} className="mb-2 max-h-56 w-full rounded-lg object-contain" />
                  ) : null}
                  <p className="break-words text-sm">{String(crop.index || i + 1)}. {String(crop.reason || "Кроп")}</p>
                  {bbox ? (
                    <div className="relative mt-2 h-28 w-full max-w-full overflow-hidden rounded-lg bg-line/70">
                      <i className="absolute rounded-sm border-2 border-forest bg-forest/20" style={bboxStyle(bbox)} />
                    </div>
                  ) : null}
                </div>
              );
            })}
          </div>
        </div>
      ) : null}

      <details className="min-w-0 text-sm">
        <summary className="cursor-pointer text-muted">Исходный JSON агента</summary>
        <pre className="mt-2 max-h-80 max-w-full overflow-auto whitespace-pre-wrap break-all rounded-xl bg-ink p-3 text-xs text-paper">
          {JSON.stringify(raw, null, 2)}
        </pre>
      </details>
    </Card>
  );
}
