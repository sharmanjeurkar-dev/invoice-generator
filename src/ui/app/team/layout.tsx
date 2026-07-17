// app/team/layout.tsx
import { Metadata } from "next";
import AuthGuard from "@/components/AuthGuard"; 

export const metadata: Metadata = {
  title: "Admin Dashboard - Team",
};

export default function TeamLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthGuard>
      {children}
    </AuthGuard>
  );
}