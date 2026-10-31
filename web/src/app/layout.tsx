import type { Metadata } from "next";
import { IBM_Plex_Sans, Source_Serif_4 } from "next/font/google";
import "./globals.css";

const sans = IBM_Plex_Sans({
  subsets: ["latin", "cyrillic"],
  weight: ["400", "500", "600"],
  variable: "--font-sans",
});

const serif = Source_Serif_4({
  subsets: ["latin", "cyrillic"],
  weight: ["600"],
  variable: "--font-serif",
});

export const metadata: Metadata = {
  title: "СибКонтур — мониторинг строительства",
  description: "Кабинет банка для контроля строительства частных домов",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru">
      <body className={`${sans.variable} ${serif.variable} font-sans antialiased text-ink`}>{children}</body>
    </html>
  );
}
