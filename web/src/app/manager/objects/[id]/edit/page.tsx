"use client";

import { useParams, useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { Button, Card, Field, Input, PageHeader } from "@/components/ui";
import { dbFetch, type BuildingObject } from "@/lib/api";
import { materials } from "@/lib/status";

export default function EditObjectPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [form, setForm] = useState<Record<string, string>>({});
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
    }).catch((e) => setError(e.message));
  }, [params.id]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    try {
      await dbFetch(`/api/objects/${params.id}`, { method: "PATCH", body: JSON.stringify(form) });
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
          {error ? <p className="text-sm text-clay md:col-span-2">{error}</p> : null}
          <div className="md:col-span-2"><Button>Сохранить</Button></div>
        </form>
      </Card>
    </div>
  );
}
