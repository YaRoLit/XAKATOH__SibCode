import { Shell } from "@/components/shell";

export default function ManagerLayout({ children }: { children: React.ReactNode }) {
  return <Shell role="manager">{children}</Shell>;
}
