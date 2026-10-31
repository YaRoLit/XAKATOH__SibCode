"use client";

import { useParams, useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { Button, Card, Field, Input, PageHeader } from "@/components/ui";
import { dbFetch, type BuildingObject, type Corner } from "@/lib/api";
import { materials } from "@/lib/status";

export default function EditObjectPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [form, setForm] = useState<Record<string, string>>({});
  const [corners, setCorners] = useState<Corner[]>([]);
  const [lat, setLat] = useState("");
  const [lon, setLon] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    dbFetch<BuildingObject>(`/api/objects/${params.id}`).then((obj) => {
      setForm({
        name: obj.name || "",
        cadastral_number: obj.cadastral_number,
        address: obj.address,
        material: obj.material || "кирпич",
        credit_issued_at: obj.credit_issued_at || "",
        planned_completion_at: obj.planned_completion_at || "",
      });
      setCorners(obj.plot_corners || []);
    }).catch((e) => setError(e.message));
  }, [params.id]);

  function addCorner() {
    const a = Number(lat);
    const b = Number(lon);
    if (Number.isNaN(a) || Number.isNaN(b)) {
      setError("Введите широту и долготу числами");
      return;
    }
    setError("");
    setCorners((prev) => [...prev, { lat: a, lon: b }]);
    setLat("");
    setLon("");
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (corners.length === 2 || corners.length === 3) {
      setError("Укажите одну точку участка или не меньше четырёх углов");
      return;
    }
    try {
      await dbFetch(`/api/objects/${params.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          ...form,
          plot_corners: corners.length ? corners : undefined,
        }),
      });
      router.replace(`/manager/objects/${params.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка");
    }
  }

  return (
    <div>
      <PageHeader title="Редактирование объекта" />
      <Card className="p-6">
        <form onSubmit={onSubmit} className="grid gap-4 md:grid-cols-2">
          <Field label="Название"><Input value={form.name || ""} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field>
          <Field label="Кадастр"><Input value={form.cadastral_number || ""} onChange={(e) => setForm({ ...form, cadastral_number: e.target.value })} /></Field>
          <Field label="Адрес"><Input value={form.address || ""} onChange={(e) => setForm({ ...form, address: e.target.value })} /></Field>
          <Field label="Материал">
            <select className="w-full rounded-xl border border-line bg-white px-3 py-2 text-sm" value={form.material} onChange={(e) => setForm({ ...form, material: e.target.value })}>
              {materials.map((m) => <option key={m}>{m}</option>)}
            </select>
          </Field>
          <Field label="Дата кредита"><Input type="date" value={form.credit_issued_at || ""} onChange={(e) => setForm({ ...form, credit_issued_at: e.target.value })} /></Field>
          <Field label="Плановое завершение"><Input type="date" value={form.planned_completion_at || ""} onChange={(e) => setForm({ ...form, planned_completion_at: e.target.value })} /></Field>
          <div className="md:col-span-2 space-y-3">
            <p className="text-sm text-muted">Границы участка: одна точка или 4+ углов. В банковском реестре координат нет.</p>
            <div className="grid gap-3 md:grid-cols-[1fr_1fr_auto]">
              <Field label="Широта"><Input value={lat} onChange={(e) => setLat(e.target.value)} placeholder="54.7442888" /></Field>
              <Field label="Долгота"><Input value={lon} onChange={(e) => setLon(e.target.value)} placeholder="83.0844121" /></Field>
              <div className="flex items-end"><Button type="button" onClick={addCorner}>Добавить точку</Button></div>
            </div>
            {corners.map((c, i) => (
              <div key={`${c.lat}-${c.lon}-${i}`} className="flex items-center justify-between rounded-xl bg-paper px-3 py-2 text-sm">
                <span>Точка {i + 1}: {c.lat}, {c.lon}</span>
                <Button type="button" variant="ghost" onClick={() => setCorners((prev) => prev.filter((_, idx) => idx !== i))}>Удалить</Button>
              </div>
            ))}
          </div>
          {error ? <p className="text-sm text-clay md:col-span-2">{error}</p> : null}
          <div className="md:col-span-2"><Button>Сохранить</Button></div>
        </form>
      </Card>
    </div>
  );
}
