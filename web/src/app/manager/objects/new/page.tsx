"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { motion } from "framer-motion";
import { Badge, Button, Card, Field, Input, PageHeader } from "@/components/ui";
import { dbFetch, type BuildingObject, type Corner } from "@/lib/api";
import { materials } from "@/lib/status";

export default function NewObjectPage() {
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [error, setError] = useState("");
  const [form, setForm] = useState({
    name: "",
    cadastral_number: "",
    address: "",
    material: "кирпич",
    credit_issued_at: "",
    planned_completion_at: "",
  });
  const [corners, setCorners] = useState<Corner[]>([]);
  const [lat, setLat] = useState("");
  const [lon, setLon] = useState("");

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

  async function submit() {
    if (corners.length < 4) {
      setError("Нужно минимум четыре точки");
      return;
    }
    setError("");
    try {
      const obj = await dbFetch<BuildingObject>("/api/objects", {
        method: "POST",
        body: JSON.stringify({ ...form, plot_corners: corners }),
      });
      router.replace(`/manager/objects/${obj.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка сохранения");
    }
  }

  return (
    <div>
      <PageHeader eyebrow="Новый объект" title="Мастер создания" description="Сначала паспорт объекта, затем границы участка по точкам." />
      <div className="mb-4 flex gap-2 text-sm">
        {[1, 2, 3].map((n) => (
          <Badge key={n} className={step === n ? "bg-forest text-white" : "bg-line text-muted"}>
            {n === 1 ? "Паспорт" : n === 2 ? "Границы" : "Проверка"}
          </Badge>
        ))}
      </div>
      <Card className="p-6">
        <motion.div key={step} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
          {step === 1 ? (
            <div className="grid gap-4 md:grid-cols-2">
              <Field label="Название объекта"><Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field>
              <Field label="Кадастровый номер"><Input value={form.cadastral_number} onChange={(e) => setForm({ ...form, cadastral_number: e.target.value })} /></Field>
              <Field label="Адрес"><Input value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} /></Field>
              <Field label="Материал">
                <select className="w-full rounded-xl border border-line bg-white px-3 py-2 text-sm" value={form.material} onChange={(e) => setForm({ ...form, material: e.target.value })}>
                  {materials.map((m) => <option key={m}>{m}</option>)}
                </select>
              </Field>
              <Field label="Дата выдачи кредита"><Input type="date" value={form.credit_issued_at} onChange={(e) => setForm({ ...form, credit_issued_at: e.target.value })} /></Field>
              <Field label="Плановое завершение"><Input type="date" value={form.planned_completion_at} onChange={(e) => setForm({ ...form, planned_completion_at: e.target.value })} /></Field>
            </div>
          ) : null}
          {step === 2 ? (
            <div>
              <p className="mb-3 text-sm text-muted">Добавьте угловые точки по часовой стрелке. Минимум четыре. Карты в MVP нет.</p>
              <div className="mb-3 grid gap-3 md:grid-cols-[1fr_1fr_auto]">
                <Field label="Широта"><Input value={lat} onChange={(e) => setLat(e.target.value)} placeholder="54.7442888" /></Field>
                <Field label="Долгота"><Input value={lon} onChange={(e) => setLon(e.target.value)} placeholder="83.0844121" /></Field>
                <div className="flex items-end"><Button type="button" onClick={addCorner}>Добавить точку</Button></div>
              </div>
              <Button type="button" variant="outline" disabled className="mb-4 opacity-70">Загрузить границы из документов · в будущем</Button>
              <div className="space-y-2">
                {corners.map((c, i) => (
                  <div key={`${c.lat}-${c.lon}-${i}`} className="flex items-center justify-between rounded-xl bg-paper px-3 py-2 text-sm">
                    <span>Точка {i + 1}: {c.lat}, {c.lon}</span>
                    <div className="flex gap-2">
                      <Button variant="ghost" onClick={() => {
                        const nextLat = prompt("Широта", String(c.lat));
                        const nextLon = prompt("Долгота", String(c.lon));
                        if (!nextLat || !nextLon) return;
                        setCorners((prev) => prev.map((item, idx) => idx === i ? { lat: Number(nextLat), lon: Number(nextLon) } : item));
                      }}>Изменить</Button>
                      <Button variant="ghost" onClick={() => setCorners((prev) => prev.filter((_, idx) => idx !== i))}>Удалить</Button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
          {step === 3 ? (
            <div className="space-y-3 text-sm">
              <p><b>{form.name}</b> · {form.cadastral_number}</p>
              <p className="text-muted">{form.address}</p>
              <p>{form.material} · кредит {form.credit_issued_at} · план {form.planned_completion_at}</p>
              <p className="text-muted">После сохранения система создаст 4 контрольные точки.</p>
              {corners.map((c, i) => <p key={i}>Точка {i + 1}: {c.lat}, {c.lon}</p>)}
            </div>
          ) : null}
        </motion.div>
        {error ? <p className="mt-4 text-sm text-clay">{error}</p> : null}
        <div className="mt-6 flex justify-between">
          <Button variant="outline" disabled={step === 1} onClick={() => setStep((s) => s - 1)}>Назад</Button>
          {step < 3 ? (
            <Button onClick={() => {
              if (step === 2 && corners.length < 4) {
                setError("Нужно минимум четыре точки");
                return;
              }
              setError("");
              setStep((s) => s + 1);
            }}>Далее</Button>
          ) : (
            <Button onClick={submit}>Сохранить объект</Button>
          )}
        </div>
      </Card>
    </div>
  );
}
