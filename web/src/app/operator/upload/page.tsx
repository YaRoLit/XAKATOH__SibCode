"use client";

import { useEffect, useMemo, useState } from "react";
import { Badge, Button, Card, PageHeader } from "@/components/ui";
import { dbFetch, photoFetch, type BuildingObject } from "@/lib/api";

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

function haversineM(lat1: number, lon1: number, lat2: number, lon2: number) {
  const toRad = (d: number) => (d * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
  return 2 * 6371000 * Math.asin(Math.sqrt(a));
}

function progressLabel(status: string) {
  const labels: Record<string, string> = {
    created: "создана",
    uploading: "загрузка файлов",
    processing: "проверка",
    completed: "проверка завершена",
    partially_confirmed: "частично отправлено",
    confirmed: "отправлено в работу",
    ready: "готово к анализу",
  };
  return labels[status] || status;
}

function formatDist(meters: number) {
  return meters < 1000 ? `${Math.round(meters)} м` : `${(meters / 1000).toFixed(1)} км`;
}

function objectCentroid(obj: BuildingObject) {
  const corners = obj.plot_corners || [];
  if (!corners.length) return null;
  return {
    lat: corners.reduce((sum, c) => sum + Number(c.lat), 0) / corners.length,
    lon: corners.reduce((sum, c) => sum + Number(c.lon), 0) / corners.length,
  };
}

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

  const unmatchedCount = results.filter((f) => f.status === "needs_manual_match").length;
  const canConfirm = Boolean(batchId) && results.some((f) => f.status === "validated") && !batchConfirm.startsWith("отправлено");

  async function start() {
    if (files.length === 0) {
      setError("Выберите фотографии");
      return;
    }
    setError("");
    setBatchConfirm("");
    setBusy("Готовим загрузку…");
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
        if (p.batch_status === "completed" || p.batch_status === "partially_confirmed" || p.batch_status === "confirmed" || p.batch_status === "ready") break;
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
    setBusy("Отправляем фото…");
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
      setBatchConfirm(e instanceof Error ? e.message : "ошибка отправки");
    } finally {
      setBusy("");
    }
  }

  function onAssigned(surveyId: number, objectId: string) {
    setResults((prev) => prev.map((file) => (
      file.survey_id === surveyId
        ? { ...file, status: "validated", object_id: objectId, errors: [] }
        : file
    )));
  }

  return (
    <div>
      <PageHeader
        eyebrow="Загрузка"
        title="Загрузка фото"
        description="Можно загрузить несколько ракурсов одного объекта за раз. В хранилище уйдут все уникальные файлы за актуальный день съёмки. Полные дубликаты и фото прошлых дней отсекаются. Если GPS не совпал — привяжите объект вручную."
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
        {progress ? (
          <p className="mt-2 text-sm text-muted">
            Статус: {progressLabel(String(progress.batch_status))} · всего {String(progress.total ?? 0)}
          </p>
        ) : null}
        {error ? <p className="mt-2 text-sm text-clay">{error}</p> : null}
      </Card>

      {results.length > 0 ? (
        <Card className="mt-4 p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="font-serif text-xl">Отправка в работу</h2>
              <p className="text-sm text-muted">
                Проверьте миниатюры и привязку к объекту, затем отправьте проверенные фото в хранилище.
                {unmatchedCount ? ` ${unmatchedCount} фото без объекта — привяжите вручную.` : ""}
              </p>
            </div>
            <Button onClick={confirmBatch} disabled={!canConfirm || Boolean(busy)}>
              Отправить в работу
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
            <h2 className="font-serif text-xl">{group.object_id === "unmatched" ? "Без объекта — нужна ручная привязка" : `Объект ${group.object_id}`}</h2>
            <div className="mt-3 space-y-2">
              {group.files.map((file) => (
                <FileRow key={file.survey_id} file={file} onAssigned={onAssigned} />
              ))}
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}

function FileRow({ file, onAssigned }: { file: FileResult; onAssigned: (surveyId: number, objectId: string) => void }) {
  const [open, setOpen] = useState(false);
  const [details, setDetails] = useState<SurveyDetails | null>(null);
  const [loadError, setLoadError] = useState("");
  const [imgBroken, setImgBroken] = useState(false);
  const failed = file.status === "rejected";
  const needsMatch = file.status === "needs_manual_match" || !file.object_id;
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
            <p>фото {file.survey_id} · статус {details?.status || file.status}</p>
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
            {needsMatch && file.status !== "rejected" ? (
              <ManualMatch
                surveyId={file.survey_id}
                photoGps={(meta.coordinates || null) as { lat?: number; lon?: number } | null}
                onAssigned={async (objectId) => {
                  onAssigned(file.survey_id, objectId);
                  try {
                    setDetails(await photoFetch<SurveyDetails>(`/surveys/${file.survey_id}/details`));
                  } catch {
                    /* список уже обновлён */
                  }
                }}
              />
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function ManualMatch({
  surveyId,
  photoGps,
  onAssigned,
}: {
  surveyId: number;
  photoGps: { lat?: number; lon?: number } | null;
  onAssigned: (objectId: string) => void;
}) {
  const [query, setQuery] = useState("");
  const [items, setItems] = useState<BuildingObject[]>([]);
  const [picked, setPicked] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    void search();
    // первый список объектов при открытии подробностей
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function search() {
    setBusy(true);
    setMessage("");
    try {
      const data = await dbFetch<{ items: BuildingObject[] }>(`/api/objects?page_size=100&q=${encodeURIComponent(query)}`);
      const lat = Number(photoGps?.lat);
      const lon = Number(photoGps?.lon);
      const ranked = [...data.items].map((obj) => {
        const center = objectCentroid(obj);
        const dist = center && Number.isFinite(lat) && Number.isFinite(lon)
          ? haversineM(lat, lon, center.lat, center.lon)
          : Number.POSITIVE_INFINITY;
        return { obj, dist };
      }).sort((a, b) => a.dist - b.dist);
      setItems(ranked.map((row) => row.obj));
      if (!picked && ranked[0]) setPicked(ranked[0].obj.id);
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Не удалось загрузить объекты");
    } finally {
      setBusy(false);
    }
  }

  async function assign() {
    if (!picked) {
      setMessage("Выберите объект");
      return;
    }
    setBusy(true);
    setMessage("");
    try {
      await photoFetch(`/surveys/${surveyId}/assign`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ object_id: picked }),
      });
      onAssigned(picked);
      setMessage("привязано");
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Не удалось привязать");
    } finally {
      setBusy(false);
    }
  }

  const lat = Number(photoGps?.lat);
  const lon = Number(photoGps?.lon);

  return (
    <div className="mt-3 rounded-xl border border-line bg-white p-3">
      <p className="text-sm text-ink">Ручная привязка к объекту</p>
      <p className="mt-1 text-xs text-muted">
        Автопоиск не нашёл участок по GPS. Выберите объект сами — даже если координаты сильно расходятся.
      </p>
      <div className="mt-2 flex flex-wrap gap-2">
        <input
          className="min-w-48 flex-1 rounded-xl border border-line px-3 py-2 text-sm"
          placeholder="Адрес, кадастр или имя"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <Button type="button" variant="outline" onClick={() => void search()} disabled={busy}>
          Найти
        </Button>
      </div>
      {items.length > 0 ? (
        <select
          className="mt-2 w-full rounded-xl border border-line px-3 py-2 text-sm"
          value={picked}
          onChange={(e) => setPicked(e.target.value)}
        >
          {items.map((obj) => {
            const center = objectCentroid(obj);
            const dist = center && Number.isFinite(lat) && Number.isFinite(lon)
              ? formatDist(haversineM(lat, lon, center.lat, center.lon))
              : "нет координат";
            return (
              <option key={obj.id} value={obj.id}>
                {obj.name || obj.cadastral_number} · {obj.address} · {dist}
              </option>
            );
          })}
        </select>
      ) : null}
      <Button className="mt-2" type="button" onClick={() => void assign()} disabled={busy || !picked}>
        Привязать к объекту
      </Button>
      {message ? (
        <p className={`mt-2 text-xs ${message === "привязано" ? "text-forest" : "text-clay"}`}>{message}</p>
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
