"use client";

import { useState } from "react";
import { supabase } from "../lib/supabaseClient"; 
import { Scale, Mail, Lock, Loader2, Eye, EyeOff, User } from "lucide-react";

export default function LoginPage() {
  const [isLogin, setIsLogin] = useState(true);
  const [name, setName] = useState(""); // 👈 Added state for Name
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
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
        const { error } = await supabase.auth.signInWithPassword({ email, password });
        if (error) throw error;
        window.location.href = "/agent";
      } else {
        // 👈 Passed the name securely into Supabase's user_metadata
        const { error } = await supabase.auth.signUp({ 
          email, 
          password,
          options: {
            data: {
              full_name: name 
            }
          }
        });
        if (error) throw error;
        window.location.href = "/settings";
      }
    } catch (err: any) {
      setErrorMsg(err.message || "Authentication failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="min-h-screen w-full flex flex-col items-center justify-center p-6"
      style={{ backgroundColor: "#F5F4F0" }}
    >
      <style>{`
        .field-input {
          background-color: #F8F8F6;
          border: 1px solid #E5E7EB;
          transition: border-color 0.15s ease, box-shadow 0.15s ease, background-color 0.15s ease;
        }
        .field-input:focus {
          outline: none;
          background-color: #FFFFFF;
          border-color: #47597A;
          box-shadow: 0 0 0 3px rgba(71, 89, 122, 0.12);
        }
      `}</style>

      {/* Brand mark */}
      <div className="flex justify-center mb-8">
        <Scale className="h-[28px] w-[28px]" style={{ color: "#47597A" }} strokeWidth={2} />
      </div>

      {/* Card */}
      <div
        className="w-full max-w-[420px] rounded-2xl p-8 sm:p-9"
        style={{
          backgroundColor: "#FFFFFF",
          border: "1px solid #ECEBE7",
          boxShadow: "0 1px 2px rgba(0,0,0,0.03), 0 12px 32px -12px rgba(20,20,20,0.08)",
        }}
      >
        <div className="mb-7">
          <h2 className="text-[22px] font-semibold tracking-tight mb-1.5" style={{ color: "#1A1A1A" }}>
            {isLogin ? "Welcome back" : "Register your firm"}
          </h2>
          <p className="text-[13.5px]" style={{ color: "#6B7280" }}>
            {isLogin
              ? "Sign in to access your firm's workspace."
              : "Set up your firm's account in under a minute."}
          </p>
        </div>

        {errorMsg && (
          <div
            className="mb-5 px-3.5 py-2.5 text-[13px] rounded-lg"
            style={{ backgroundColor: "#FBEEEE", color: "#9B4040", border: "1px solid #F0DADA" }}
          >
            {errorMsg}
          </div>
        )}
        {successMsg && (
          <div
            className="mb-5 px-3.5 py-2.5 text-[13px] rounded-lg"
            style={{ backgroundColor: "#EDF2EF", color: "#3F6B54", border: "1px solid #DAE6DE" }}
          >
            {successMsg}
          </div>
        )}

        <form onSubmit={handleAuth} className="space-y-4">
          
          {/* 👈 Conditionally render the Name field ONLY during registration */}
          {!isLogin && (
            <div>
              <label className="block text-[13px] font-medium mb-1.5" style={{ color: "#374151" }}>
                Full Name
              </label>
              <div className="relative">
                <User
                  className="absolute left-3.5 top-1/2 -translate-y-1/2 h-[16px] w-[16px]"
                  style={{ color: "#9CA3AF" }}
                />
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="field-input w-full rounded-lg pl-10 pr-3.5 py-2.5 text-[14px]"
                  style={{ color: "#1A1A1A" }}
                  placeholder="Sanjay Jeurkar"
                />
              </div>
            </div>
          )}

          <div>
            <label className="block text-[13px] font-medium mb-1.5" style={{ color: "#374151" }}>
              Email address
            </label>
            <div className="relative">
              <Mail
                className="absolute left-3.5 top-1/2 -translate-y-1/2 h-[16px] w-[16px]"
                style={{ color: "#9CA3AF" }}
              />
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="field-input w-full rounded-lg pl-10 pr-3.5 py-2.5 text-[14px]"
                style={{ color: "#1A1A1A" }}
                placeholder="admin@firm.com"
              />
            </div>
          </div>

          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="block text-[13px] font-medium" style={{ color: "#374151" }}>
                Password
              </label>
              {isLogin && (
                <button
                  type="button"
                  className="text-[12px] font-medium hover:underline"
                  style={{ color: "#47597A" }}
                >
                  Forgot password?
                </button>
              )}
            </div>
            <div className="relative">
              <Lock
                className="absolute left-3.5 top-1/2 -translate-y-1/2 h-[16px] w-[16px]"
                style={{ color: "#9CA3AF" }}
              />
              <input
                type={showPassword ? "text" : "password"}
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="field-input w-full rounded-lg pl-10 pr-10 py-2.5 text-[14px]"
                style={{ color: "#1A1A1A" }}
                placeholder="••••••••"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3.5 top-1/2 -translate-y-1/2"
                style={{ color: "#9CA3AF" }}
                tabIndex={-1}
              >
                {showPassword ? <EyeOff className="h-[16px] w-[16px]" /> : <Eye className="h-[16px] w-[16px]" />}
              </button>
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 rounded-lg transition-all duration-150 flex items-center justify-center font-medium text-[14px] shadow-sm hover:shadow-md active:scale-[0.99] disabled:opacity-70 disabled:cursor-not-allowed mt-1"
            style={{ backgroundColor: "#47597A", color: "#FFFFFF" }}
            onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = "#3B4A66")}
            onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = "#47597A")}
          >
            {loading ? (
              <Loader2 className="animate-spin h-[17px] w-[17px]" />
            ) : isLogin ? (
              "Sign in"
            ) : (
              "Create account"
            )}
          </button>
        </form>

        <div className="mt-6 text-center text-[13px]" style={{ color: "#6B7280" }}>
          {isLogin ? "Don't have an account? " : "Already have an account? "}
          <button
            type="button"
            onClick={() => {
              setIsLogin(!isLogin);
              setErrorMsg("");
              setSuccessMsg("");
            }}
            className="font-semibold hover:underline transition-colors"
            style={{ color: "#47597A" }}
          >
            {isLogin ? "Register your firm" : "Sign in"}
          </button>
        </div>
      </div>

      <p
        className="mt-7 text-[11px] tracking-[0.14em] uppercase"
        style={{ color: "#9CA3AF" }}
      >
        Finance and accounting · AI-assisted tooling
      </p>
    </div>
  );
}