export const shootLabel: Record<string, string> = {
  scheduled: "Запланирована",
  available: "Доступна к съёмке",
  overdue: "Съёмка просрочена",
  completed: "Съёмка выполнена",
};

export const shootTone: Record<string, string> = {
  scheduled: "bg-line text-muted",
  available: "bg-forest/10 text-forestDark",
  overdue: "bg-clay/10 text-clay",
  completed: "bg-forest text-white",
};

export const alertLabel: Record<string, string> = {
  new: "Новый",
  in_progress: "В работе",
  resolved: "Решён",
  reopened: "Повторно выявлен",
};

export const alertTone: Record<string, string> = {
  new: "bg-clay/10 text-clay",
  in_progress: "bg-gold/20 text-[#7A5A1E]",
  resolved: "bg-forest/10 text-forestDark",
  reopened: "bg-clay/15 text-clay",
};

export const objectStatusLabel: Record<string, string> = {
  active: "В работе",
  archived: "Архив",
};

export const aiTone: Record<string, string> = {
  green: "bg-forest/10 text-forestDark",
  yellow: "bg-gold/20 text-[#7A5A1E]",
  red: "bg-clay/10 text-clay",
};

export function formatDate(value?: string | null) {
  if (!value) return "—";
  return new Date(value).toLocaleDateString("ru-RU");
}

export function formatDateTime(value?: string | null) {
  if (!value) return "—";
  return new Date(value).toLocaleString("ru-RU", { dateStyle: "short", timeStyle: "short" });
}

export const materials = ["кирпич", "газобетон", "дерево", "каркас", "иное"];
