"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { dbFetch } from "@/lib/api";
import { saveSession, type AuthUser } from "@/lib/auth";
import { Button, Field, Input } from "@/components/ui";

export default function LoginPage() {
  const router = useRouter();
  const [login, setLogin] = useState("manager");
  const [password, setPassword] = useState("manager");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const data = await dbFetch<{ token: string; user: AuthUser }>("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ login, password }),
      });
      saveSession(data.token, data.user);
      router.replace(data.user.role === "manager" ? "/manager" : "/operator");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось войти");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-6xl items-center px-4">
      <div className="grid w-full gap-10 lg:grid-cols-2">
        <div className="hidden lg:block">
          <p className="text-xs uppercase tracking-[0.22em] text-muted">Банк · залог строящегося дома</p>
          <h1 className="mt-3 font-serif text-5xl leading-tight">СибКонтур следит за стройкой, пока кредит в работе.</h1>
          <p className="mt-4 max-w-md text-muted">
            Менеджер видит контрольные точки и отчёты агента. Оператор загружает снимки — система сама
            сопоставляет их с участками.
          </p>
        </div>
        <form onSubmit={onSubmit} className="rounded-3xl border border-line bg-card p-8 shadow-card">
          <p className="font-serif text-2xl">Вход в кабинет</p>
          <p className="mt-1 text-sm text-muted">Регистрации нет. Роль определяется на сервере.</p>
          <div className="mt-6 space-y-4">
            <Field label="Логин">
              <Input value={login} onChange={(e) => setLogin(e.target.value)} autoComplete="username" />
            </Field>
            <Field label="Пароль">
              <Input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
              />
            </Field>
            {error ? <p className="text-sm text-clay">{error}</p> : null}
            <Button className="w-full" disabled={loading}>
              {loading ? "Входим…" : "Войти"}
            </Button>
          </div>
          <div className="mt-6 grid grid-cols-2 gap-2 text-xs text-muted">
            <button type="button" className="rounded-xl bg-paper px-3 py-2 text-left" onClick={() => { setLogin("manager"); setPassword("manager"); }}>
              manager / manager
            </button>
            <button type="button" className="rounded-xl bg-paper px-3 py-2 text-left" onClick={() => { setLogin("operator"); setPassword("operator"); }}>
              operator / operator
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
