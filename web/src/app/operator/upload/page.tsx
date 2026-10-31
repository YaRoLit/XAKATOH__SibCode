"use client";

import { useMemo, useState } from "react";
import { Badge, Button, Card, PageHeader } from "@/components/ui";
import { photoFetch } from "@/lib/api";

type FileResult = {
  survey_id: number;
  filename: string;
  status: string;
  object_id?: string | null;
  coverage?: number | null;
  errors?: string[];
};

type Group = {
  object_id: string;
  files: FileResult[];
};

export default function UploadPage() {
  const [files, setFiles] = useState<File[]>([]);
  const [batchId, setBatchId] = useState<string | null>(null);
  const [progress, setProgress] = useState<Record<string, unknown> | null>(null);
  const [results, setResults] = useState<FileResult[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const [confirmed, setConfirmed] = useState<Record<string, string>>({});

  const groups = useMemo(() => {
    const map = new Map<string, FileResult[]>();
    for (const file of results) {
      const key = file.object_id || "unmatched";
      map.set(key, [...(map.get(key) || []), file]);
    }
    return Array.from(map.entries()).map(([object_id, groupFiles]) => ({ object_id, files: groupFiles })) as Group[];
  }, [results]);

  async function start() {
    if (files.length === 0) {
      setError("Выберите фотографии");
      return;
    }
    setError("");
    setBusy("Создаём пачку…");
    try {
      const created = await photoFetch<{ batch_id: string }>("/batches?operator_id=user_operator", { method: "POST" });
      setBatchId(created.batch_id);
      setBusy("Загружаем файлы…");
      const form = new FormData();
      files.forEach((f) => form.append("files", f));
      await photoFetch(`/batches/${created.batch_id}/upload`, { method: "POST", body: form });
      setBusy("Запускаем проверку…");
      await photoFetch(`/batches/${created.batch_id}/process`, { method: "POST" });
      setBusy("Ждём результаты…");
      for (let i = 0; i < 40; i += 1) {
        const p = await photoFetch<Record<string, unknown>>(`/batches/${created.batch_id}/progress`);
        setProgress(p);
        if (p.batch_status === "completed" || p.batch_status === "partially_confirmed" || p.batch_status === "confirmed") break;
        await new Promise((r) => setTimeout(r, 1500));
      }
      const res = await photoFetch<{ files: FileResult[] }>(`/batches/${created.batch_id}/results`);
      setResults(res.files);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка загрузки");
    } finally {
      setBusy("");
    }
  }

  async function confirm(objectId: string) {
    if (!batchId) return;
    setBusy(`Подтверждаем ${objectId}…`);
    try {
      const res = await photoFetch<{ status: string; message?: string; batch_status?: string }>(
        `/batches/${batchId}/objects/${objectId}/confirm`,
        { method: "POST" },
      );
      setConfirmed((prev) => ({ ...prev, [objectId]: res.status === "ok" ? "подтверждено" : res.message || res.status }));
    } catch (e) {
      setConfirmed((prev) => ({ ...prev, [objectId]: e instanceof Error ? e.message : "ошибка" }));
    } finally {
      setBusy("");
    }
  }

  return (
    <div>
      <PageHeader
        eyebrow="Загрузка"
        title="Общая пачка без выбора объекта"
        description="Сервис проверки сам сопоставит GPS с границами участков. Подтверждение — отдельно по каждому объекту."
      />
      <Card className="p-5">
        <input
          type="file"
          accept="image/*"
          multiple
          onChange={(e) => setFiles(Array.from(e.target.files || []))}
        />
        <p className="mt-2 text-sm text-muted">Выбрано файлов: {files.length}</p>
        <Button className="mt-4" onClick={start} disabled={Boolean(busy)}>
          {busy || "Загрузить и проверить"}
        </Button>
        {batchId ? <p className="mt-2 text-xs text-muted">Батч {batchId}</p> : null}
        {progress ? <p className="mt-2 text-sm text-muted">Статус: {String(progress.batch_status)} · всего {String(progress.total ?? 0)}</p> : null}
        {error ? <p className="mt-2 text-sm text-clay">{error}</p> : null}
      </Card>

      <div className="mt-4 space-y-4">
        {groups.map((group) => (
          <Card key={group.object_id} className="p-5">
            <div className="flex items-center justify-between gap-3">
              <h2 className="font-serif text-xl">{group.object_id === "unmatched" ? "Без объекта" : `Объект ${group.object_id}`}</h2>
              {group.object_id !== "unmatched" ? (
                <Button onClick={() => confirm(group.object_id)} disabled={Boolean(busy)}>
                  Подтвердить объект
                </Button>
              ) : null}
            </div>
            {confirmed[group.object_id] ? <p className="mt-2 text-sm text-forest">{confirmed[group.object_id]}</p> : null}
            <div className="mt-3 space-y-2">
              {group.files.map((file) => (
                <FileRow key={file.survey_id} file={file} />
              ))}
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}

function FileRow({ file }: { file: FileResult }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-xl bg-paper px-3 py-2">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-sm">{file.filename}</p>
          <p className="text-xs text-muted">{(file.errors || []).join("; ") || "Ошибок нет"}</p>
        </div>
        <div className="flex items-center gap-2">
          <Badge className="bg-white text-muted">{file.status}</Badge>
          <button className="text-xs text-forest" onClick={() => setOpen((v) => !v)}>Подробности</button>
        </div>
      </div>
      {open ? (
        <div className="mt-2 text-xs text-muted">
          <p>survey {file.survey_id} · coverage {file.coverage ?? "—"}</p>
          {file.status !== "rejected" ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img alt={file.filename} src={`/api/photo/surveys/${file.survey_id}/photo`} className="mt-2 max-h-64 rounded-lg" />
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
