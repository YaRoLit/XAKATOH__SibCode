"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AiReportView } from "@/components/ai-report";
import { Badge, Button, Card, PageHeader } from "@/components/ui";
import { dbFetch, type BuildingObject, type ConstructionPlan } from "@/lib/api";
import { formatDate, objectStatusLabel, shootLabel, shootTone } from "@/lib/status";

export default function ObjectCardPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [obj, setObj] = useState<BuildingObject | null>(null);
  const [plan, setPlan] = useState("");
  const [planSaved, setPlanSaved] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const data = await dbFetch<BuildingObject & { construction_plan?: ConstructionPlan }>(`/api/objects/${params.id}`);
        if (cancelled) return;
        setObj(data);
        setPlan((prev) => (prev === "" ? data.construction_plan?.description || "" : prev));
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Ошибка");
      }
    }
    void load();
    const timer = setInterval(load, 8000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [params.id]);

  async function archive() {
    if (!confirm("Архивировать объект?")) return;
    const next = await dbFetch<BuildingObject>(`/api/objects/${params.id}/archive`, { method: "POST" });
    setObj(next);
  }

  if (error) return <p className="text-clay">{error}</p>;
  if (!obj) return <p className="text-muted">Загружаем карточку…</p>;

  return (
    <div className="min-w-0 max-w-full">
      <PageHeader
        eyebrow={obj.cadastral_number}
        title={obj.name || "Объект"}
        description={obj.address}
        action={
          <div className="flex gap-2">
            <Link href={`/manager/objects/${obj.id}/edit`}><Button variant="outline">Редактировать</Button></Link>
            <Button variant="danger" onClick={archive} disabled={obj.status === "archived"}>Архивировать</Button>
          </div>
        }
      />
      <div className="grid min-w-0 gap-4 lg:grid-cols-3">
        <Card className="min-w-0 overflow-hidden p-5 lg:col-span-2">
          <div className="flex flex-wrap gap-2">
            <Badge className="bg-line text-muted">{objectStatusLabel[obj.status]}</Badge>
            {obj.material ? <Badge className="bg-paper text-muted">{obj.material}</Badge> : null}
            {obj.is_demo ? <Badge className="bg-gold/20 text-[#7A5A1E]">Демонстрационные данные</Badge> : null}
          </div>
          <dl className="mt-4 grid gap-3 text-sm md:grid-cols-2">
            <div><dt className="text-muted">Кредит выдан</dt><dd>{formatDate(obj.credit_issued_at)}</dd></div>
            <div><dt className="text-muted">Плановое завершение</dt><dd>{formatDate(obj.planned_completion_at)}</dd></div>
          </dl>
          <h2 className="mt-6 font-serif text-xl">Контрольные точки</h2>
          <div className="mt-3 space-y-2">
            {obj.checkpoints.map((cp) => (
              <Link key={cp.id} href={`/manager/checkpoints/${cp.id}`} className="flex items-center justify-between rounded-xl bg-paper px-3 py-2 hover:bg-line/50">
                <div>
                  <p className="text-sm">{cp.title} · {cp.expected_readiness}%</p>
                  <p className="text-xs text-muted">{formatDate(cp.planned_date)}</p>
                </div>
                <Badge className={shootTone[cp.shoot_status]}>{shootLabel[cp.shoot_status] || cp.shoot_status}</Badge>
              </Link>
            ))}
          </div>
        </Card>
        <Card className="min-w-0 overflow-hidden p-5">
          <h2 className="font-serif text-xl">Границы участка</h2>
          <p className="mt-1 text-xs text-muted">
            {(obj.plot_corners || []).length === 0
              ? "Координаты не заданы. Их нет в банковском реестре — добавьте в редактировании."
              : obj.plot_corners.length === 1
                ? "Одна точка участка"
                : `Полигон, ${obj.plot_corners.length} точек`}
          </p>
          <ol className="mt-3 space-y-2 text-sm">
            {(obj.plot_corners || []).map((c, i) => (
              <li key={i} className="rounded-xl bg-paper px-3 py-2">Точка {i + 1}: {c.lat}, {c.lon}</li>
            ))}
          </ol>
        </Card>
      </div>
      <Card className="mt-4 min-w-0 overflow-hidden p-5">
        <h2 className="font-serif text-xl">План строительства для агента</h2>
        <p className="mt-1 text-sm text-muted">Свободный текст. Если пусто — агент работает в режиме без плана.</p>
        <textarea
          className="mt-3 min-h-32 w-full rounded-xl border border-line px-3 py-2 text-sm"
          value={plan}
          onChange={(e) => setPlan(e.target.value)}
        />
        <div className="mt-3 flex items-center gap-3">
          <Button
            onClick={async () => {
              await dbFetch(`/api/objects/${obj.id}/plan`, { method: "PUT", body: JSON.stringify({ description: plan }) });
              setPlanSaved("Сохранено");
            }}
          >
            Сохранить план
          </Button>
          {planSaved ? <p className="text-sm text-forest">{planSaved}</p> : null}
        </div>
      </Card>
      <div className="mt-4 min-w-0 space-y-4">
        <h2 className="font-serif text-2xl">AI-отчёты</h2>
        {(obj.analysis_jobs || []).some((job) => job.status === "pending" || job.status === "processing") ? (
          <p className="text-sm text-forest">Фото в хранилище, агент готовит отчёт. Страница обновляется сама.</p>
        ) : null}
        {(obj.reports || []).length === 0 && !(obj.analysis_jobs || []).length ? (
          <p className="text-sm text-muted">
            {(obj.recent_surveys || []).some((s) => !s.s3_key)
              ? "Оператор загрузил фото, но батч ещё не согласован — в хранилище и к агенту они не попали."
              : "Агент ещё не записал отчёт."}
          </p>
        ) : null}
        {(obj.reports || []).map((report) => <AiReportView key={report.id} report={report} />)}
      </div>
      <button className="mt-6 text-sm text-muted" onClick={() => router.push("/manager/objects")}>← К реестру</button>
    </div>
  );
}
