"use client";

import { useEffect } from "react";
import { useSession } from "./lib/auth"; // Your new Better Auth client
import { useFirmStore } from "../store/useFirmStore";

export default function AuthProvider({ children }: { children: React.ReactNode }) {
  const setAuth = useFirmStore((state) => state.setAuth);
  
  // Better Auth's hook automatically listens for login/logout events!
  const { data: sessionData, isPending } = useSession();

  useEffect(() => {
    // 👇 Your original retry architecture remains perfectly intact
    const loadUserData = async (userId: string, retries = 3) => {
      try {
        // We ask Python for the firm_id instead of querying the DB directly
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
        const response = await fetch(`${apiUrl}/api/users/${userId}/profile`);

        if (!response.ok) throw new Error("Profile API failed");
        
        const data = await response.json();
        
        // Trigger the retry loop if it's empty
        if (!data || !data.firm_id) throw new Error("Profile not created yet"); 
        
        // Success! We got the firm ID.
        setAuth(userId, data.firm_id);

      } catch (error: any) {
        // If it fails, wait 500ms and try again, up to 3 times.
        if (retries > 0) {
          console.warn(`Profile not ready. Retrying... (${retries} attempts left)`);
          setTimeout(() => loadUserData(userId, retries - 1), 500);
        } else {
          // If it completely fails after 3 tries, log the actual error message
          console.error("Error fetching firm ID:", error.message || error);
          setAuth(userId, null); // Logged in, but no firm found
        }
      }
    };

    // If Better Auth is still booting up, do nothing yet
    if (isPending) return;

    // Check if the user is logged in
    if (sessionData?.user) {
      loadUserData(sessionData.user.id);
    } else {
      // Not logged in, clear everything
      setAuth(null, null);
    }
    
    // We don't need a cleanup subscription return anymore because 
    // the useSession hook manages all the unmounting invisibly!
  }, [sessionData, isPending, setAuth]);

  return <>{children}</>;
}