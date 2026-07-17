import { Metadata } from "next";
import AuthGuard from "@/components/AuthGuard";

export const metadata: Metadata = {
  title: "Ledger",
};

// Only ONE export default here!
export default function AgentLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthGuard>
      {children}
    </AuthGuard>
  );
}