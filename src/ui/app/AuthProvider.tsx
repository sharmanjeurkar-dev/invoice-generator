"use client";

import { useEffect } from "react";
import { supabase } from "./lib/supabaseClient"; // Adjust path if needed
import { useFirmStore } from "../store/useFirmStore"; // Adjust path if needed

export default function AuthProvider({ children }: { children: React.ReactNode }) {
  const setAuth = useFirmStore((state) => state.setAuth);

  useEffect(() => {
    // 👇 Added a "retries" parameter to handle the database delay
    const loadUserData = async (userId: string, retries = 3) => {
      try {
        const { data, error } = await supabase
          .from("profiles")
          .select("firm_id")
          .eq("id", userId)
          .maybeSingle(); 

        if (error) throw error;
        
        // 👇 Add this check to trigger the retry loop if it's empty
        if (!data) throw new Error("Profile not created yet"); 
        
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

    // Check if already logged in on initial load
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (session?.user) {
        loadUserData(session.user.id);
      } else {
        setAuth(null, null);
      }
    });

    // Listen for login/logout events
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      if (session?.user) {
        loadUserData(session.user.id);
      } else {
        setAuth(null, null);
      }
    });

    return () => subscription.unsubscribe();
  }, [setAuth]);

  return <>{children}</>;
}