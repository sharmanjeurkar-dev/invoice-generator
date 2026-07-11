// app/settings/layout.tsx
import { Metadata } from "next";

export const metadata: Metadata = {
  title: "Settings | Pentacles",
};

export default function SettingsLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}