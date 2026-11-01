"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Badge, Button, Card, PageHeader } from "@/components/ui";
import { dbFetch, type Checkpoint } from "@/lib/api";
import { formatDate, shootLabel, shootTone } from "@/lib/status";

type Survey = {
  survey_id: number;
  filename: string;
  status: string;
  object_id?: string | null;
  object_name?: string | null;
  errors: string[];
  created_at: string;
};

export default function OperatorHome() {
  const [tasks, setTasks] = useState<Checkpoint[]>([]);
  const [rejected, setRejected] = useState<Survey[]>([]);
  const [recent, setRecent] = useState<Survey[]>([]);

  useEffect(() => {
    dbFetch<{ items: Checkpoint[] }>("/api/operator/tasks").then((d) => setTasks(d.items));
    dbFetch<{ items: Survey[] }>("/api/operator/rejected").then((d) => setRejected(d.items));
    dbFetch<{ surveys: Survey[] }>("/api/operator/recent").then((d) => setRecent(d.surveys));
  }, []);

  return (
    <div>
      <PageHeader
        eyebrow="Оператор БПЛА"
        title="Смены и съёмка"
        description="В смену попадают только объекты с координатами участка. Без точек пилот задачу не видит."
        action={<Link href="/operator/upload"><Button>Загрузить фото</Button></Link>}
      />
      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="p-5 lg:col-span-2">
          <h2 className="font-serif text-xl">Задачи на съёмку</h2>
          <div className="mt-3 space-y-2">
            {tasks.length === 0 ? <p className="text-sm text-muted">Нет доступных задач в 7-дневном окне</p> : null}
            {tasks.map((task) => (
              <div key={task.id} className="rounded-xl bg-paper px-3 py-3">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-medium">{task.object_name}</p>
                    <p className="text-xs text-muted">{task.cadastral_number} · {task.address}</p>
                    <p className="text-xs text-muted">
                      {(task.checkpoint_titles || [task.title]).join(" · ")}
                      {task.planned_date ? ` · ближайший план ${formatDate(task.planned_date)}` : ""}
                    </p>
                  </div>
                  <Badge className={shootTone[task.shoot_status]}>{shootLabel[task.shoot_status]}</Badge>
                </div>
              </div>
            ))}
          </div>
        </Card>
        <Card className="p-5">
          <h2 className="font-serif text-xl">Отклонённые фото</h2>
          <div className="mt-3 space-y-2">
            {rejected.map((s) => (
              <div key={s.survey_id} className="rounded-xl bg-paper px-3 py-2 text-sm">
                <p>{s.filename}</p>
                <p className="text-xs text-clay">{(s.errors || []).join("; ")}</p>
              </div>
            ))}
            {rejected.length === 0 ? <p className="text-sm text-muted">Отказов нет</p> : null}
            <Link href="/operator/upload"><Button variant="outline" className="mt-2 w-full">Повторить загрузку</Button></Link>
          </div>
        </Card>
      </div>
      <Card className="mt-4 p-5">
        <h2 className="font-serif text-xl">Последние выполненные съёмки</h2>
        <div className="mt-3 space-y-2">
          {recent.length === 0 ? <p className="text-sm text-muted">Пока нет принятых съёмок</p> : null}
          {recent.map((s) => (
            <div key={s.survey_id} className="flex justify-between rounded-xl bg-paper px-3 py-2 text-sm">
              <span>{s.filename} · {s.object_name || s.object_id || "без объекта"}</span>
              <span className="text-muted">{formatDate(s.created_at)} · {s.status}</span>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
