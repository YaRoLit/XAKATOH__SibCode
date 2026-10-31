"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Badge, Card, PageHeader } from "@/components/ui";
import { dbFetch, type Checkpoint } from "@/lib/api";
import { formatDate, shootLabel, shootTone } from "@/lib/status";

export default function CalendarPage() {
  const [items, setItems] = useState<Checkpoint[]>([]);
  const [cursor, setCursor] = useState(() => {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), 1);
  });

  useEffect(() => {
    const from = new Date(cursor.getFullYear(), cursor.getMonth(), 1);
    const to = new Date(cursor.getFullYear(), cursor.getMonth() + 1, 0);
    const q = `date_from=${from.toISOString().slice(0, 10)}&date_to=${to.toISOString().slice(0, 10)}`;
    dbFetch<{ items: Checkpoint[] }>(`/api/calendar?${q}`).then((d) => setItems(d.items));
  }, [cursor]);

  const days = useMemo(() => {
    const first = new Date(cursor.getFullYear(), cursor.getMonth(), 1);
    const start = (first.getDay() + 6) % 7;
    const count = new Date(cursor.getFullYear(), cursor.getMonth() + 1, 0).getDate();
    return { start, count };
  }, [cursor]);

  const byDay = useMemo(() => {
    const map = new Map<string, Checkpoint[]>();
    for (const item of items) {
      const key = item.planned_date;
      map.set(key, [...(map.get(key) || []), item]);
    }
    return map;
  }, [items]);

  const title = cursor.toLocaleDateString("ru-RU", { month: "long", year: "numeric" });

  return (
    <div>
      <PageHeader
        eyebrow="Календарь"
        title={title}
        action={
          <div className="flex gap-2">
            <button className="rounded-xl border border-line px-3 py-2 text-sm" onClick={() => setCursor(new Date(cursor.getFullYear(), cursor.getMonth() - 1, 1))}>←</button>
            <button className="rounded-xl border border-line px-3 py-2 text-sm" onClick={() => setCursor(new Date(cursor.getFullYear(), cursor.getMonth() + 1, 1))}>→</button>
          </div>
        }
      />
      <Card className="overflow-hidden p-4">
        <div className="grid grid-cols-7 gap-2 text-center text-xs uppercase tracking-wider text-muted">
          {["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"].map((d) => <div key={d}>{d}</div>)}
        </div>
        <div className="mt-2 grid grid-cols-7 gap-2">
          {Array.from({ length: days.start }).map((_, i) => <div key={`e${i}`} />)}
          {Array.from({ length: days.count }).map((_, i) => {
            const day = i + 1;
            const key = `${cursor.getFullYear()}-${String(cursor.getMonth() + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
            const events = byDay.get(key) || [];
            return (
              <div key={key} className="min-h-28 rounded-xl bg-paper p-2">
                <p className="text-xs text-muted">{day}</p>
                <div className="mt-1 space-y-1">
                  {events.map((ev) => (
                    <Link key={ev.id} href={`/manager/checkpoints/${ev.id}`} className="block rounded-lg bg-white px-1.5 py-1 text-left">
                      <p className="truncate text-[11px]">{ev.object_name}</p>
                      <Badge className={`${shootTone[ev.shoot_status]} mt-0.5`}>{shootLabel[ev.shoot_status]}</Badge>
                    </Link>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </Card>
      <div className="mt-4 space-y-2">
        {items.map((ev) => (
          <Link key={ev.id} href={`/manager/objects/${ev.object_id}`} className="flex justify-between rounded-xl border border-line bg-card px-4 py-2 text-sm">
            <span>{formatDate(ev.planned_date)} · {ev.object_name} · {ev.title}</span>
            <Badge className={shootTone[ev.shoot_status]}>{shootLabel[ev.shoot_status]}</Badge>
          </Link>
        ))}
      </div>
    </div>
  );
}
