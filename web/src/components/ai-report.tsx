import { Badge, Card } from "@/components/ui";
import { aiTone, formatDateTime } from "@/lib/status";
import type { Report } from "@/lib/api";

export function AiReportView({ report }: { report: Report }) {
  const raw = report.raw_json || {};
  const stages = Array.isArray(raw.stages) ? raw.stages : [];
  const problems = Array.isArray(raw.problems) ? raw.problems : [];
  const comments = Array.isArray(raw.comments) ? raw.comments : [];
  const overall = raw.overall_status as string | undefined;
  const pct = raw.overall_readiness_pct as number | undefined;

  return (
    <Card className="p-5">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.16em] text-muted">AI-отчёт</p>
          <p className="font-serif text-xl">{pct != null ? `${pct}% готовности` : "Результат агента"}</p>
          <p className="text-xs text-muted">{formatDateTime(report.created_at)}</p>
        </div>
        {overall ? <Badge className={aiTone[overall] || "bg-line text-muted"}>{overall}</Badge> : null}
      </div>

      {stages.length > 0 ? (
        <div className="mb-4 grid gap-2 md:grid-cols-3">
          {stages.map((stage: Record<string, unknown>, i: number) => (
            <div key={i} className="rounded-xl bg-paper px-3 py-2">
              <div className="flex items-center justify-between">
                <p className="text-sm">{String(stage.name || "Стадия")}</p>
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
            <li key={i}>{String(c)}</li>
          ))}
        </ul>
      ) : null}

      {problems.length > 0 ? (
        <div className="mb-4 space-y-2">
          {problems.map((item: Record<string, unknown>, i: number) => (
            <div key={i} className="rounded-xl border border-line px-3 py-2 text-sm">
              <p className="font-medium">{String(item.title || item.code || "Проблема")}</p>
              <p className="text-muted">{String(item.description || item.summary || "")}</p>
            </div>
          ))}
        </div>
      ) : null}

      <details className="text-sm">
        <summary className="cursor-pointer text-muted">Исходный JSON агента</summary>
        <pre className="mt-2 overflow-auto rounded-xl bg-ink p-3 text-xs text-paper">
          {JSON.stringify(raw, null, 2)}
        </pre>
      </details>
    </Card>
  );
}
