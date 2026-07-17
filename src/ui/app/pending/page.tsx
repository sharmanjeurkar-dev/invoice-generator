"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabaseClient";
import { Clock, LogOut, RefreshCw } from "lucide-react";

export default function PendingPage() {
  const router = useRouter();
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Allows users to manually force a re-check if their admin just approved them
  const handleCheckStatus = async () => {
    setIsRefreshing(true);
    try {
      // Refresh the active session token to pick up any database changes
      const { data, error } = await supabase.auth.refreshSession();
      
      if (error) throw error;

      if (data?.session?.user?.id) {
        // Query the profiles table to see if their status flipped to approved
        const { data: profile } = await supabase
          .from("profiles")
          .select("status")
          .eq("id", data.session.user.id)
          .single();

        if (profile && profile.status === "approved") {
          // If approved, kick them straight to the main app dashboard
          router.push("/");
          return;
        }
      }
    } catch (err) {
      console.error("Error refreshing status:", err);
    } finally {
      // Artificial delay just so the button spinner feels natural
      setTimeout(() => setIsRefreshing(false), 800);
    }
  };

  // Safe logout so users aren't permanently locked out if they logged into the wrong account
  const handleSignOut = async () => {
    await supabase.auth.signOut();
    router.push("/login");
  };

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-[#F7F7F5] p-6">
      <div className="bg-white p-8 rounded-2xl shadow-sm border border-[#e5e7eb] max-w-md w-full text-center">
        
        {/* Visual Cue: Animated Clock Icon */}
        <div className="flex justify-center mb-5">
          <div className="w-14 h-14 bg-amber-50 border border-amber-200 rounded-full flex items-center justify-center text-amber-600 animate-pulse">
            <Clock className="w-7 h-7" />
          </div>
        </div>

        <h2 className="text-2xl font-bold text-[#1a1a1a] mb-3">
          Verification Pending
        </h2>
        
        <p className="text-sm text-[#6b7280] leading-relaxed mb-6">
          Your profile has been successfully linked to your firm. An administrator must explicitly verify your account before you can access financial ledgers, settings, or the agent interface.
        </p>

        {/* Action Buttons Container */}
        <div className="space-y-3">
          <button
            onClick={handleCheckStatus}
            disabled={isRefreshing}
            className="w-full flex items-center justify-center gap-2 py-2.5 px-4 bg-[#1f3864] text-white rounded-lg text-sm font-semibold hover:bg-[#162b50] transition-colors shadow-sm disabled:opacity-75"
          >
            <RefreshCw className={`w-4 h-4 ${isRefreshing ? "animate-spin" : ""}`} />
            {isRefreshing ? "Checking Status..." : "Check Status Again"}
          </button>

          <button
            onClick={handleSignOut}
            className="w-full flex items-center justify-center gap-2 py-2.5 px-4 border border-[#e5e7eb] text-[#374151] rounded-lg text-sm font-medium hover:bg-gray-50 transition-colors"
          >
            <LogOut className="w-4 h-4 text-[#6b7280]" />
            Sign Out / Switch Account
          </button>
        </div>

        {/* Tiny metadata stamp footer */}
        <div className="mt-8 pt-4 border-t border-[#f3f4f6] text-[11px] text-[#9ca3af]">
          Secured Financial Ledger Access Control System
        </div>

      </div>
    </div>
  );
}