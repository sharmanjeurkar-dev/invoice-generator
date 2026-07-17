"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { supabase } from "./../app/lib/supabaseClient";

export default function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [isAuthorized, setIsAuthorized] = useState(false);

  useEffect(() => {
    const enforceRoutes = async () => {
      // 1. Check if they are logged in at all
      const { data: { session } } = await supabase.auth.getSession();
      
      if (!session) {
        router.push("/login");
        return;
      }

      // 2. Fetch their role and status from our database
      const { data: profile } = await supabase
        .from("profiles")
        .select("role, status")
        .eq("id", session.user.id)
        .single();

      if (!profile) return;

      // 3. Rule A: Kick Pending users to the waiting room
      if (profile.status === "pending" && pathname !== "/pending") {
        router.push("/pending");
        return;
      }

      // 4. Rule B: Kick Standard Members out of the Admin Team page
      if (profile.role === "member" && pathname.startsWith("/team")) {
        router.push("/"); // Redirect them back to the main dashboard/agent
        return;
      }

      // If they pass the checks, let the page load
      setIsAuthorized(true);
    };

    enforceRoutes();
  }, [pathname, router]);

  // Don't render the page's HTML until we know they are allowed to see it
  if (!isAuthorized) return null; 

  return <>{children}</>;
}