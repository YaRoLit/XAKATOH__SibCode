"use client";

import { Badge, Button, Card } from "@/components/ui";
import { dbFetch, type PriceEstimate } from "@/lib/api";
import { formatDateTime } from "@/lib/status";

function money(value: number | null | undefined, currency = "RUB") {
  if (value == null || !Number.isFinite(Number(value))) return "—";
  const suffix = currency === "RUB" ? "₽" : currency;
  return `${new Intl.NumberFormat("ru-RU").format(Number(value))} ${suffix}`;
}

function statusText(status?: string) {
  if (status === "pending") return "Оценка в очереди";
  if (status === "processing") return "Оценка формируется";
  if (status === "completed") return "Демо-оценка готова";
  if (status === "failed") return "Оценка не удалась";
  return "";
}

export function PriceEstimateCard({
  objectId,
  estimate,
  onChanged,
}: {
  objectId: string;
  estimate?: PriceEstimate | null;
  onChanged: (next: PriceEstimate) => void;
}) {
  const canEstimate = Boolean(estimate?.can_estimate);
  const task = estimate?.task;
  const report = estimate?.report;
  const busy = task?.status === "pending" || task?.status === "processing";

  async function requestEstimate() {
    const next = await dbFetch<PriceEstimate>(`/api/objects/${objectId}/price-estimate`, { method: "POST" });
    onChanged(next);
  }

  return (
    <Card className="mt-4 min-w-0 overflow-hidden p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-serif text-xl">Оценка стоимости</h2>
          <p className="mt-1 text-sm text-muted">
            Демонстрационный диапазон по последнему отчёту агента. Это не рыночная выборка и не официальная оценка.
          </p>
        </div>
        <Badge className="bg-gold/20 text-[#7A5A1E]">ДЕМО / МОК</Badge>
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <Button onClick={() => void requestEstimate()} disabled={!canEstimate || busy}>
          {task?.status === "failed" ? "Повторить оценку" : "Сделать оценку"}
        </Button>
        {!canEstimate ? (
          <p className="text-sm text-muted">Сначала дождитесь отчёта агента по последней съёмке</p>
        ) : null}
        {task ? <p className="text-sm text-forest">{statusText(task.status)}</p> : null}
      </div>
      {task?.status === "failed" && task.error_message ? (
        <p className="mt-3 text-sm text-clay">{task.error_message}</p>
      ) : null}
      {report ? (
        <div className="mt-5 space-y-4">
          <div className="grid gap-3 md:grid-cols-3">
            <div className="rounded-xl bg-paper px-3 py-2">
              <p className="text-xs text-muted">Диапазон</p>
              <p className="text-sm">{money(report.value_min, report.currency)} — {money(report.value_max, report.currency)}</p>
            </div>
            <div className="rounded-xl bg-paper px-3 py-2">
              <p className="text-xs text-muted">Точечная оценка</p>
              <p className="text-sm">{money(report.value_point, report.currency)}</p>
            </div>
            <div className="rounded-xl bg-paper px-3 py-2">
              <p className="text-xs text-muted">Уверенность</p>
              <p className="text-sm">{report.confidence == null ? "—" : `${Math.round(Number(report.confidence) * 100)}%`}</p>
            </div>
          </div>
          <p className="text-sm whitespace-pre-wrap">{report.justification}</p>
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead>
                <tr className="text-xs text-muted">
                  <th className="py-2 pr-3">Аналог</th>
                  <th className="py-2 pr-3">Цена</th>
                  <th className="py-2 pr-3">Площадь</th>
                  <th className="py-2 pr-3">Участок</th>
                  <th className="py-2 pr-3">Состояние</th>
                </tr>
              </thead>
              <tbody>
                {(report.comparables || []).map((item, index) => (
                  <tr key={`${item.title || "c"}-${index}`} className="border-t border-line align-top">
                    <td className="py-2 pr-3">
                      <p>{item.title}</p>
                      <p className="text-xs text-muted">{item.address}</p>
                      {item.note ? <p className="mt-1 text-xs text-muted">{item.note}</p> : null}
                    </td>
                    <td className="py-2 pr-3 whitespace-nowrap">{money(item.price, report.currency)}</td>
                    <td className="py-2 pr-3">{item.area_m2 != null ? `${item.area_m2} м²` : "—"}</td>
                    <td className="py-2 pr-3">{item.land_sotka != null ? `${item.land_sotka} сот.` : "—"}</td>
                    <td className="py-2 pr-3">
                      {item.condition || "—"}
                      {item.completion_percent != null ? ` · ${item.completion_percent}%` : ""}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-xs text-muted">
            Создано {formatDateTime(report.created_at)}. Демонстрационная оценка. Аналоги и цены сгенерированы мок-агентом,
            не являются реальной рыночной выборкой или официальной оценкой.
          </p>
        </div>
      ) : null}
    </Card>
  );
}
