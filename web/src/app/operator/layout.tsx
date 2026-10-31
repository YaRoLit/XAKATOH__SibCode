import { Shell } from "@/components/shell";

export default function OperatorLayout({ children }: { children: React.ReactNode }) {
  return <Shell role="operator">{children}</Shell>;
}
