// Inside app/agent/layout.tsx (Brand new file!)
import { Metadata } from "next";

export const metadata: Metadata = {
  title: "Ledger",
};

// Only ONE export default here!
export default function AgentLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}