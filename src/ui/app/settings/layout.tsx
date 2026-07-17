import { Metadata } from "next";
import AuthGuard from "@/components/AuthGuard";

export const metadata: Metadata = {
  title: "Settings",
};

export default function SettingsLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthGuard>
      {children}
    </AuthGuard>
  );
}