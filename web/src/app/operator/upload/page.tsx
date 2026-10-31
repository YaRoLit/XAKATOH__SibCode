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

type SurveyDetails = {
  survey_id: number;
  batch_id: string;
  filename: string;
  status: string;
  errors?: string[] | null;
  metadata?: Record<string, unknown> | null;
  coverage?: number | null;
  duplicate_of?: number | null;
  has_preview?: boolean;
  object?: {
    object_id: string;
    cadastral_number?: string;
    address?: string;
    plot_corners?: Array<{ lat: number; lon: number }>;
  } | null;
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
  const [batchConfirm, setBatchConfirm] = useState("");

  const groups = useMemo(() => {
    const map = new Map<string, FileResult[]>();
    for (const file of results) {
      const key = file.object_id || "unmatched";
      map.set(key, [...(map.get(key) || []), file]);
    }
    return Array.from(map.entries()).map(([object_id, groupFiles]) => ({ object_id, files: groupFiles })) as Group[];
  }, [results]);

  const canConfirm = Boolean(batchId) && results.some((f) => f.status === "validated") && !batchConfirm.startsWith("отправлено");

  async function start() {
    if (files.length === 0) {
      setError("Выберите фотографии");
      return;
    }
    setError("");
    setBatchConfirm("");
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

  async function confirmBatch() {
    if (!batchId) return;
    setBusy("Согласовываем батч…");
    try {
      const res = await photoFetch<{ status: string; message?: string; uploaded_to_storage?: number }>(
        `/batches/${batchId}/confirm`,
        { method: "POST" },
      );
      if (res.status === "ok") {
        setBatchConfirm(`отправлено в хранилище: ${res.uploaded_to_storage ?? 0} файл(ов). Агент возьмёт их в работу.`);
      } else {
        setBatchConfirm(res.message || res.status);
      }
    } catch (e) {
      setBatchConfirm(e instanceof Error ? e.message : "ошибка согласования");
    } finally {
      setBusy("");
    }
  }

  return (
    <div>
      <PageHeader
        eyebrow="Загрузка"
        title="Общая пачка без выбора объекта"
        description="После проверки откройте подробности каждого фото. В хранилище и к агенту файлы уходят только после согласования батча."
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

      {results.length > 0 ? (
        <Card className="mt-4 p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="font-serif text-xl">Согласование батча</h2>
              <p className="text-sm text-muted">Проверьте миниатюры и метаданные, затем отправьте validated-фото в хранилище.</p>
            </div>
            <Button onClick={confirmBatch} disabled={!canConfirm || Boolean(busy)}>
              Согласовать батч
            </Button>
          </div>
          {batchConfirm ? (
            <p className={`mt-3 text-sm ${batchConfirm.startsWith("отправлено") ? "text-forest" : "text-clay"}`}>
              {batchConfirm}
            </p>
          ) : null}
        </Card>
      ) : null}

      <div className="mt-4 space-y-4">
        {groups.map((group) => (
          <Card key={group.object_id} className="p-5">
            <h2 className="font-serif text-xl">{group.object_id === "unmatched" ? "Без объекта" : `Объект ${group.object_id}`}</h2>
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
  const [details, setDetails] = useState<SurveyDetails | null>(null);
  const [loadError, setLoadError] = useState("");
  const [imgBroken, setImgBroken] = useState(false);
  const failed = file.status === "rejected" || file.status === "needs_manual_match";
  const showThumb = open && !failed && !imgBroken && (details?.has_preview !== false);

  async function toggle() {
    const next = !open;
    setOpen(next);
    if (!next || details) return;
    try {
      setDetails(await photoFetch<SurveyDetails>(`/surveys/${file.survey_id}/details`));
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : "Не удалось загрузить подробности");
    }
  }

  const meta = details?.metadata || {};
  const corners = details?.object?.plot_corners || [];

  return (
    <div className="rounded-xl bg-paper px-3 py-2">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-sm">{file.filename}</p>
          <p className="text-xs text-muted">{(file.errors || []).join("; ") || "Ошибок нет"}</p>
        </div>
        <div className="flex items-center gap-2">
          <Badge className="bg-white text-muted">{file.status}</Badge>
          <button className="text-xs text-forest" onClick={() => void toggle()}>{open ? "Скрыть" : "Подробнее"}</button>
        </div>
      </div>
      {open ? (
        <div className={`mt-3 grid gap-4 ${showThumb ? "md:grid-cols-[minmax(0,22rem)_1fr]" : ""}`}>
          {showThumb ? (
            <div>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                alt={file.filename}
                src={`/api/photo/surveys/${file.survey_id}/photo`}
                className="max-h-80 w-full rounded-lg object-contain bg-white"
                onError={() => setImgBroken(true)}
              />
              <p className="mt-2 text-xs text-muted">
                {corners.length >= 4
                  ? "На миниатюре красный контур участка и синие углы."
                  : corners.length === 1
                    ? "На миниатюре отмечена одна точка участка."
                    : "Границ нет: у объекта меньше четырёх точек."}
              </p>
            </div>
          ) : failed ? (
            <p className="text-xs text-muted">Миниатюра скрыта: проверка фото не пройдена.</p>
          ) : null}
          <div className="space-y-1 text-xs text-muted">
            {loadError ? <p className="text-clay">{loadError}</p> : null}
            <p>survey {file.survey_id} · статус {details?.status || file.status}</p>
            <p>покрытие {details?.coverage ?? file.coverage ?? "—"}</p>
            {details?.object ? (
              <p>
                объект {details.object.object_id} · {details.object.cadastral_number} · {details.object.address}
              </p>
            ) : <p>объект не привязан</p>}
            <MetaLines meta={meta} />
            {(details?.errors || file.errors || []).length ? (
              <p className="text-clay">{(details?.errors || file.errors || []).join("; ")}</p>
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function MetaLines({ meta }: { meta: Record<string, unknown> }) {
  const coords = (meta.coordinates || {}) as Record<string, unknown>;
  const alt = (meta.altitude || {}) as Record<string, unknown>;
  const cam = (meta.camera || {}) as Record<string, unknown>;
  const ori = (meta.orientation || {}) as Record<string, unknown>;
  const image = (meta.image || {}) as Record<string, unknown>;
  return (
    <>
      {meta.datetime_original ? <p>снято {String(meta.datetime_original)}</p> : null}
      {coords.lat != null ? <p>GPS {String(coords.lat)}, {String(coords.lon)}</p> : <p>GPS нет</p>}
      {alt.relative != null ? <p>высота {String(alt.relative)} м</p> : null}
      {cam.model ? <p>камера {String(cam.model)} · фокус {String(cam.focal_length)} мм</p> : null}
      {ori.yaw != null ? <p>yaw {String(ori.yaw)} · pitch {String(ori.pitch)} · roll {String(ori.roll)}</p> : null}
      {image.width ? <p>кадр {String(image.width)}×{String(image.height)}</p> : null}
    </>
  );
}
