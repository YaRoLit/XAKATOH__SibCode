"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Badge, Card, PageHeader } from "@/components/ui";
import { dbFetch, type Alert } from "@/lib/api";
import { alertLabel, alertTone, formatDateTime } from "@/lib/status";

export default function AlertsPage() {
  const [status, setStatus] = useState("");
  const [items, setItems] = useState<Alert[]>([]);

  useEffect(() => {
    const q = status ? `?status=${status}` : "";
    dbFetch<{ items: Alert[] }>(`/api/alerts${q}`).then((d) => setItems(d.items));
  }, [status]);

  return (
    <div>
      <PageHeader eyebrow="Центр проблем" title="AI-алерты" description="Исходный JSON агента не меняется. Здесь только действия менеджера." />
      <div className="mb-4 flex flex-wrap gap-2">
        {["", "new", "in_progress", "resolved", "reopened"].map((s) => (
          <button key={s} onClick={() => setStatus(s)} className={`rounded-full px-3 py-1 text-sm ${status === s ? "bg-forest text-white" : "bg-line text-muted"}`}>
            {s ? alertLabel[s] : "Все"}
          </button>
        ))}
      </div>
      <div className="space-y-3">
        {items.map((alert) => (
          <Link key={alert.id} href={`/manager/alerts/${alert.id}`}>
            <Card className="p-4 hover:bg-paper/70">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="font-medium">{alert.title}</p>
                  <p className="text-sm text-muted">{alert.object_name} · {formatDateTime(alert.created_at)}</p>
                </div>
                <Badge className={alertTone[alert.status]}>{alertLabel[alert.status]}</Badge>
              </div>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
