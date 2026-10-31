"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Badge, Card, PageHeader } from "@/components/ui";
import { dbFetch, type Dashboard } from "@/lib/api";
import { alertLabel, alertTone, formatDate, shootLabel, shootTone } from "@/lib/status";

export default function ManagerDashboard() {
  const [data, setData] = useState<Dashboard | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    dbFetch<Dashboard>("/api/dashboard")
      .then(setData)
      .catch((e) => setError(e.message));
  }, []);

  if (error) return <p className="text-clay">{error}</p>;
  if (!data) return <p className="text-muted">Загружаем обзор…</p>;

  const stats = [
    { label: "Объекты в работе", value: data.objects_in_progress },
    { label: "С проблемами AI", value: data.objects_with_problems },
    { label: "Просроченные съёмки", value: data.overdue_checkpoints },
  ];

  return (
    <div>
      <PageHeader eyebrow="Кабинет менеджера" title="Сегодня по портфелю" description="Сводка по объектам, срокам и новым алертам агента." />
      <div className="grid gap-4 md:grid-cols-3">
        {stats.map((item) => (
          <Card key={item.label} className="p-5">
            <p className="text-sm text-muted">{item.label}</p>
            <p className="mt-2 font-serif text-4xl">{item.value}</p>
          </Card>
        ))}
      </div>
      {(data.recent_photos || []).length > 0 ? (
        <Card className="mt-6 p-5">
          <h2 className="font-serif text-xl">Новые фото от оператора</h2>
          <div className="mt-4 space-y-3">
            {(data.recent_photos || []).map((alert) => (
              <Link key={alert.id} href={`/manager/objects/${alert.object_id}`} className="block rounded-xl bg-paper px-3 py-2 hover:bg-line/50">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm">{alert.object_name || alert.title}</p>
                    <p className="text-xs text-muted">{alert.summary}</p>
                  </div>
                  <Badge className="bg-forest/10 text-forestDark">Новое фото</Badge>
                </div>
              </Link>
            ))}
          </div>
        </Card>
      ) : null}
      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        <Card className="p-5">
          <h2 className="font-serif text-xl">Ближайшие контрольные точки</h2>
          <div className="mt-4 space-y-3">
            {data.upcoming_checkpoints.length === 0 ? <p className="text-sm text-muted">Нет ближайших точек</p> : null}
            {data.upcoming_checkpoints.map((cp) => (
              <Link key={cp.id} href={`/manager/checkpoints/${cp.id}`} className="block rounded-xl bg-paper px-3 py-2 hover:bg-line/50">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm">{cp.object_name}</p>
                    <p className="text-xs text-muted">{cp.title} · {formatDate(cp.planned_date)}</p>
                  </div>
                  <Badge className={shootTone[cp.shoot_status]}>{shootLabel[cp.shoot_status] || cp.shoot_status}</Badge>
                </div>
              </Link>
            ))}
          </div>
        </Card>
        <Card className="p-5">
          <h2 className="font-serif text-xl">Последние проблемы</h2>
          <div className="mt-4 space-y-3">
            {data.recent_alerts.length === 0 ? <p className="text-sm text-muted">Пока тихо</p> : null}
            {data.recent_alerts.map((alert) => (
              <Link key={alert.id} href={`/manager/alerts/${alert.id}`} className="block rounded-xl bg-paper px-3 py-2 hover:bg-line/50">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm">{alert.title}</p>
                    <p className="text-xs text-muted">{alert.object_name}</p>
                  </div>
                  <Badge className={alertTone[alert.status]}>{alertLabel[alert.status]}</Badge>
                </div>
              </Link>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
