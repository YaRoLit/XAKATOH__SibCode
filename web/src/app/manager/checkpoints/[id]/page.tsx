"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { AiReportView } from "@/components/ai-report";
import { Badge, Button, Card, Input, PageHeader } from "@/components/ui";
import { dbFetch, type Alert, type Checkpoint, type Report } from "@/lib/api";
import { alertLabel, alertTone, formatDate, formatDateTime, shootLabel, shootTone } from "@/lib/status";

type CheckpointDetail = Checkpoint & { reports?: Report[]; alerts?: Alert[] };

export default function CheckpointPage() {
  const params = useParams<{ id: string }>();
  const [data, setData] = useState<CheckpointDetail | null>(null);
  const [date, setDate] = useState("");
  const [preview, setPreview] = useState<{ old_date: string; new_date: string; warning: string } | null>(null);
  const [error, setError] = useState("");

  async function load() {
    const next = await dbFetch<CheckpointDetail>(`/api/checkpoints/${params.id}`);
    setData(next);
    setDate(next.planned_date);
  }

  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, [params.id]);

  async function requestMove() {
    const res = await dbFetch<Record<string, string>>(`/api/checkpoints/${params.id}`, {
      method: "PATCH",
      body: JSON.stringify({ planned_date: date, confirm: false }),
    });
    if (res.needs_confirm) setPreview({ old_date: res.old_date, new_date: res.new_date, warning: res.warning });
  }

  async function confirmMove() {
    await dbFetch(`/api/checkpoints/${params.id}`, {
      method: "PATCH",
      body: JSON.stringify({ planned_date: date, confirm: true }),
    });
    setPreview(null);
    await load();
  }

  if (!data) return <p className="text-muted">{error || "Загружаем точку…"}</p>;

  return (
    <div>
      <PageHeader
        eyebrow={data.object_name || ""}
        title={data.title}
        description={`Плановая готовность ${data.expected_readiness}%`}
      />
      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="p-5 lg:col-span-2">
          <Badge className={shootTone[data.shoot_status]}>{shootLabel[data.shoot_status]}</Badge>
          <p className="mt-3 text-sm">Плановая дата: {formatDate(data.planned_date)}</p>
          <p className="text-sm text-muted">Фактическая съёмка: {formatDateTime(data.actual_shot_at)}</p>
          <Link className="mt-3 inline-block text-sm text-forest" href={`/manager/objects/${data.object_id}`}>Карточка объекта</Link>
          <div className="mt-6 space-y-3">
            {(data.reports || []).map((r) => <AiReportView key={r.id} report={r} />)}
          </div>
        </Card>
        <Card className="p-5">
          <h2 className="font-serif text-xl">Перенос даты</h2>
          <p className="mt-2 text-sm text-muted">Изменит график оператора и 7-дневное окно доступности. Выполненные точки не сбрасываются.</p>
          <Input type="date" className="mt-3" value={date} onChange={(e) => setDate(e.target.value)} />
          <Button className="mt-3 w-full" variant="outline" onClick={requestMove}>Проверить перенос</Button>
          {preview ? (
            <div className="mt-4 rounded-xl bg-gold/15 p-3 text-sm">
              <p>Было: {formatDate(preview.old_date)}</p>
              <p>Станет: {formatDate(preview.new_date)}</p>
              <p className="mt-2">{preview.warning}</p>
              <Button className="mt-3 w-full" onClick={confirmMove}>Подтвердить перенос</Button>
            </div>
          ) : null}
          <h3 className="mt-6 text-sm text-muted">История дат</h3>
          {(data.date_history || []).map((h, i) => (
            <p key={i} className="text-xs text-muted">{String(h.old_date)} → {String(h.new_date)}</p>
          ))}
        </Card>
      </div>
      <div className="mt-4 space-y-2">
        {(data.alerts || []).map((a) => (
          <Link key={a.id} href={`/manager/alerts/${a.id}`} className="flex justify-between rounded-xl border border-line bg-card px-4 py-2">
            <span>{a.title}</span>
            <Badge className={alertTone[a.status]}>{alertLabel[a.status]}</Badge>
          </Link>
        ))}
      </div>
    </div>
  );
}
