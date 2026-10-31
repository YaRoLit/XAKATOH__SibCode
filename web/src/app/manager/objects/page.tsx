"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Badge, Button, Card, Input, PageHeader } from "@/components/ui";
import { dbFetch, type BuildingObject } from "@/lib/api";
import { materials, objectStatusLabel, formatDate } from "@/lib/status";

type ListResponse = { items: BuildingObject[]; total: number; page: number; page_size: number };

export default function ObjectsPage() {
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("active");
  const [material, setMaterial] = useState("");
  const [hasProblems, setHasProblems] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<ListResponse | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const params = new URLSearchParams({ page: String(page), page_size: "10", sort: "created_at", order: "desc" });
    if (q) params.set("q", q);
    if (status) params.set("status", status);
    if (material) params.set("material", material);
    if (hasProblems) params.set("has_problems", hasProblems);
    dbFetch<ListResponse>(`/api/objects?${params}`)
      .then(setData)
      .catch((e) => setError(e.message));
  }, [q, status, material, hasProblems, page]);

  return (
    <div>
      <PageHeader
        eyebrow="Реестр"
        title="Строительные объекты"
        description="Поиск по кадастру и адресу, в том числе с опечатками."
        action={<Link href="/manager/objects/new"><Button>Создать объект</Button></Link>}
      />
      <Card className="mb-4 p-4">
        <div className="grid gap-3 md:grid-cols-4">
          <Input placeholder="Кадастр или адрес" value={q} onChange={(e) => { setPage(1); setQ(e.target.value); }} />
          <select className="rounded-xl border border-line bg-white px-3 py-2 text-sm" value={status} onChange={(e) => { setPage(1); setStatus(e.target.value); }}>
            <option value="">Все статусы</option>
            <option value="active">В работе</option>
            <option value="archived">Архив</option>
          </select>
          <select className="rounded-xl border border-line bg-white px-3 py-2 text-sm" value={material} onChange={(e) => { setPage(1); setMaterial(e.target.value); }}>
            <option value="">Все материалы</option>
            {materials.map((m) => <option key={m}>{m}</option>)}
          </select>
          <select className="rounded-xl border border-line bg-white px-3 py-2 text-sm" value={hasProblems} onChange={(e) => { setPage(1); setHasProblems(e.target.value); }}>
            <option value="">Проблемы: все</option>
            <option value="true">Только с проблемами</option>
            <option value="false">Без проблем</option>
          </select>
        </div>
      </Card>
      {error ? <p className="text-clay">{error}</p> : null}
      <Card className="overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-paper text-left text-muted">
            <tr>
              <th className="px-4 py-3 font-medium">Объект</th>
              <th className="px-4 py-3 font-medium">Кадастр</th>
              <th className="px-4 py-3 font-medium">Материал</th>
              <th className="px-4 py-3 font-medium">Завершение</th>
              <th className="px-4 py-3 font-medium">Статус</th>
            </tr>
          </thead>
          <tbody>
            {data?.items.map((obj) => (
              <tr key={obj.id} className="border-t border-line hover:bg-paper/70">
                <td className="px-4 py-3">
                  <Link href={`/manager/objects/${obj.id}`} className="font-medium hover:text-forest">
                    {obj.name}
                  </Link>
                  <p className="text-xs text-muted">{obj.address}</p>
                </td>
                <td className="px-4 py-3">{obj.cadastral_number}</td>
                <td className="px-4 py-3">{obj.material || "—"}</td>
                <td className="px-4 py-3">{formatDate(obj.planned_completion_at)}</td>
                <td className="px-4 py-3">
                  <div className="flex flex-wrap gap-1">
                    <Badge className="bg-line text-muted">{objectStatusLabel[obj.status] || obj.status}</Badge>
                    {obj.has_problems ? <Badge className="bg-clay/10 text-clay">Проблемы</Badge> : null}
                    {obj.is_demo ? <Badge className="bg-gold/20 text-[#7A5A1E]">Демо</Badge> : null}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="flex items-center justify-between border-t border-line px-4 py-3 text-sm text-muted">
          <span>Всего {data?.total ?? 0}</span>
          <div className="flex gap-2">
            <Button variant="outline" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>Назад</Button>
            <Button variant="outline" disabled={!data || page * data.page_size >= data.total} onClick={() => setPage((p) => p + 1)}>Далее</Button>
          </div>
        </div>
      </Card>
    </div>
  );
}
