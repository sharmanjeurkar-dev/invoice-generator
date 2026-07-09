import { redirect } from "next/navigation";

export default function RootPage() {
  // Automatically bounce users to the login page (or /agent) when they hit the root domain
  redirect("/login"); 
}