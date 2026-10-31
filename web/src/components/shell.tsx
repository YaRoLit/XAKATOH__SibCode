"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Building2, CalendarRange, LayoutDashboard, LogOut, Plane, ShieldAlert, Upload } from "lucide-react";
import { clearSession, getUser, type AuthUser } from "@/lib/auth";

const managerLinks = [
  { href: "/manager", label: "Обзор", icon: LayoutDashboard },
  { href: "/manager/objects", label: "Объекты", icon: Building2 },
  { href: "/manager/calendar", label: "Календарь", icon: CalendarRange },
  { href: "/manager/alerts", label: "Проблемы", icon: ShieldAlert },
];

const operatorLinks = [
  { href: "/operator", label: "Задачи", icon: Plane },
  { href: "/operator/upload", label: "Загрузка", icon: Upload },
];

export function Shell({ role, children }: { role: "manager" | "operator"; children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<AuthUser | null>(null);

  useEffect(() => {
    const current = getUser();
    if (!current || (role === "manager" && current.role !== "manager")) {
      router.replace("/login");
      return;
    }
    if (role === "operator" && current.role !== "operator" && current.role !== "manager") {
      router.replace("/login");
      return;
    }
    setUser(current);
  }, [role, router]);

  const links = role === "manager" ? managerLinks : operatorLinks;

  return (
    <div className="min-h-screen overflow-x-hidden lg:grid lg:grid-cols-[240px_1fr]">
      <aside className="border-b border-line bg-card/80 px-4 py-4 backdrop-blur lg:border-b-0 lg:border-r lg:px-5 lg:py-6">
        <div className="mb-6">
          <p className="font-serif text-xl">СибКонтур</p>
          <p className="text-xs text-muted">{role === "manager" ? "Кредитный контроль" : "Съёмка объектов"}</p>
        </div>
        <nav className="flex gap-2 overflow-auto lg:flex-col">
          {links.map((link) => {
            const active = pathname === link.href || (link.href !== `/${role}` && pathname.startsWith(link.href));
            const Icon = link.icon;
            return (
              <Link
                key={link.href}
                href={link.href}
                className={`flex items-center gap-2 rounded-xl px-3 py-2 text-sm ${
                  active ? "bg-forest text-white" : "text-muted hover:bg-paper"
                }`}
              >
                <Icon size={16} />
                {link.label}
              </Link>
            );
          })}
        </nav>
        <div className="mt-6 hidden border-t border-line pt-4 lg:block">
          <p className="text-sm">{user?.display_name}</p>
          <p className="text-xs text-muted">{user?.login}</p>
          <button
            className="mt-3 flex items-center gap-2 text-sm text-muted hover:text-ink"
            onClick={() => {
              clearSession();
              router.replace("/login");
            }}
          >
            <LogOut size={14} />
            Выйти
          </button>
        </div>
      </aside>
      <main className="min-w-0 overflow-x-hidden px-4 py-6 lg:px-8 lg:py-8">{user ? children : null}</main>
    </div>
  );
}
