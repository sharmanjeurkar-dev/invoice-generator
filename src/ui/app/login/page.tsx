"use client";

import { useState } from "react";
import { supabase } from "../lib/supabaseClient"; // Adjust path if your lib is elsewhere
import { Mail, Lock, Loader2 } from "lucide-react";

export default function LoginPage() {
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");
  const [successMsg, setSuccessMsg] = useState("");

  const handleAuth = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setErrorMsg("");
    setSuccessMsg("");

    try {
      if (isLogin) {
        // --- LOGIN FLOW ---
        const { error } = await supabase.auth.signInWithPassword({
          email,
          password,
        });
        if (error) throw error;
        
        window.location.href = "/settings"; // Redirect on success
      } else {
        // --- REGISTRATION FLOW ---
        const { error } = await supabase.auth.signUp({
          email,
          password,
        });
        if (error) throw error;
        
        setSuccessMsg("Registration successful! You can now log in.");
        setIsLogin(true); // Switch back to login view
      }
    } catch (err: any) {
      setErrorMsg(err.message || "Authentication failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 p-4">
      <div className="max-w-md w-full bg-white rounded-xl shadow-lg p-8 border border-gray-100">
        <h2 className="text-2xl font-bold text-center mb-6" style={{ color: "#1f3864" }}>
          {isLogin ? "Welcome Back" : "Register Your Firm"}
        </h2>

        {errorMsg && (
          <div className="mb-4 p-3 bg-red-50 text-red-700 text-sm rounded-md border border-red-200">
            {errorMsg}
          </div>
        )}

        {successMsg && (
          <div className="mb-4 p-3 bg-green-50 text-green-700 text-sm rounded-md border border-green-200">
            {successMsg}
          </div>
        )}

        <form onSubmit={handleAuth} className="space-y-5">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Email Address</label>
            <div className="relative">
              <Mail className="absolute left-3 top-2.5 h-5 w-5 text-gray-400" />
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full pl-10 pr-4 py-2 border rounded-md focus:ring-2 focus:ring-[#1f3864] focus:border-transparent outline-none"
                placeholder="admin@firm.com"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
            <div className="relative">
              <Lock className="absolute left-3 top-2.5 h-5 w-5 text-gray-400" />
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full pl-10 pr-4 py-2 border rounded-md focus:ring-2 focus:ring-[#1f3864] focus:border-transparent outline-none"
                placeholder="••••••••"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full text-white py-2.5 rounded-md hover:opacity-90 transition-opacity flex items-center justify-center font-medium"
            style={{ backgroundColor: "#1f3864" }}
          >
            {loading ? <Loader2 className="animate-spin h-5 w-5" /> : (isLogin ? "Sign In" : "Create Account")}
          </button>
        </form>

        <div className="mt-6 text-center">
          <button
            type="button"
            onClick={() => {
              setIsLogin(!isLogin);
              setErrorMsg("");
              setSuccessMsg("");
            }}
            className="text-sm font-medium hover:underline"
            style={{ color: "#1f3864" }}
          >
            {isLogin ? "Need to register your firm? Sign up" : "Already have an account? Sign in"}
          </button>
        </div>
      </div>
    </div>
  );
}