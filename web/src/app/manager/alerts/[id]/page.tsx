"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { Badge, Button, Card, PageHeader } from "@/components/ui";
import { dbFetch, type Alert } from "@/lib/api";
import { alertLabel, alertTone, formatDateTime } from "@/lib/status";

export default function AlertDetailPage() {
  const params = useParams<{ id: string }>();
  const [alert, setAlert] = useState<Alert | null>(null);
  const [comment, setComment] = useState("");
  const [status, setStatus] = useState("in_progress");
  const [error, setError] = useState("");

  useEffect(() => {
    dbFetch<Alert>(`/api/alerts/${params.id}`).then((a) => {
      setAlert(a);
      setStatus(a.status);
    });
  }, [params.id]);

  async function submit() {
    try {
      const next = await dbFetch<Alert>(`/api/alerts/${params.id}/actions`, {
        method: "POST",
        body: JSON.stringify({ status, comment: comment || null }),
      });
      setAlert(next);
      setComment("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка");
    }
  }

  if (!alert) return <p className="text-muted">Загружаем проблему…</p>;

  return (
    <div>
      <PageHeader eyebrow="Проблема" title={alert.title} description={alert.summary || ""} />
      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="p-5 lg:col-span-2">
          <Badge className={alertTone[alert.status]}>{alertLabel[alert.status]}</Badge>
          <p className="mt-3 text-sm text-muted">{formatDateTime(alert.created_at)}</p>
          <Link className="mt-2 inline-block text-sm text-forest" href={`/manager/objects/${alert.object_id}`}>
            {alert.object_name}
          </Link>
          {alert.raw_item ? (
            <pre className="mt-4 overflow-auto rounded-xl bg-paper p-3 text-xs">{JSON.stringify(alert.raw_item, null, 2)}</pre>
          ) : null}
          <h2 className="mt-6 font-serif text-xl">История действий</h2>
          <div className="mt-3 space-y-2">
            {alert.actions.length === 0 ? <p className="text-sm text-muted">Пока нет комментариев</p> : null}
            {alert.actions.map((a) => (
              <div key={a.id} className="rounded-xl bg-paper px-3 py-2 text-sm">
                <p className="text-xs text-muted">{a.actor_name || "менеджер"} · {formatDateTime(a.created_at)}</p>
                <p>{a.comment || a.action}</p>
              </div>
            ))}
          </div>
        </Card>
        <Card className="p-5">
          <h2 className="font-serif text-xl">Обработка</h2>
          <select className="mt-3 w-full rounded-xl border border-line px-3 py-2 text-sm" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="new">Новый</option>
            <option value="in_progress">В работе</option>
            <option value="resolved">Решён</option>
            <option value="reopened">Повторно выявлен</option>
          </select>
          <textarea className="mt-3 min-h-28 w-full rounded-xl border border-line px-3 py-2 text-sm" placeholder="Комментарий" value={comment} onChange={(e) => setComment(e.target.value)} />
          {error ? <p className="mt-2 text-sm text-clay">{error}</p> : null}
          <Button className="mt-3 w-full" onClick={submit}>Сохранить действие</Button>
        </Card>
      </div>
    </div>
  );
}
