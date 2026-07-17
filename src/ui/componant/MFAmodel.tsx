import React, { useState, useEffect } from "react";
import { supabase } from "../app/lib/supabaseClient";
import { Loader2, ShieldCheck, QrCode } from "lucide-react";

interface MfaModalProps {
  onSuccess: () => void;
  onCancel: () => void;
}

export default function MfaModal({ onSuccess, onCancel }: MfaModalProps) {
  const [loading, setLoading] = useState(true);
  const [verifying, setVerifying] = useState(false);
  const [error, setError] = useState("");
  const [qrCode, setQrCode] = useState("");
  const [factorId, setFactorId] = useState("");
  const [code, setCode] = useState("");
  const [isSetupMode, setIsSetupMode] = useState(false);

  useEffect(() => {
    async function checkMfaStatus() {
      try {
        const { data: factors, error: factorsError } = await supabase.auth.mfa.listFactors();
        if (factorsError) throw factorsError;

        const totpFactor = factors.totp[0];

        if (!totpFactor || totpFactor.status !== "verified") {
          // Setup Mode: Generate QR Code
          setIsSetupMode(true);
          const { data, error } = await supabase.auth.mfa.enroll({ factorType: "totp" });
          if (error) throw error;
          
          setFactorId(data.id);
          setQrCode(data.totp.qr_code);
        } else {
          // Verification Mode: User already has MFA setup
          setFactorId(totpFactor.id);
        }
      } catch (err: any) {
        setError(err.message || "Failed to initialize security check.");
      } finally {
        setLoading(false);
      }
    }
    checkMfaStatus();
  }, []);

  const handleVerify = async () => {
    setVerifying(true);
    setError("");
    try {
      // 1. Create a challenge
      const challengeRes = await supabase.auth.mfa.challenge({ factorId });
      if (challengeRes.error) throw challengeRes.error;

      // 2. Verify the 6-digit code against the challenge
      const verifyRes = await supabase.auth.mfa.verify({
        factorId,
        challengeId: challengeRes.data.id,
        code
      });

      if (verifyRes.error) throw verifyRes.error;

      // Success! Proceed to the sensitive action
      onSuccess();
    } catch (err: any) {
      setError("Invalid code. Please try again.");
    } finally {
      setVerifying(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="bg-white w-full max-w-md rounded-2xl p-6 shadow-xl relative">
        <div className="flex justify-center mb-4 text-[#1f3864]">
          {isSetupMode ? <QrCode className="w-10 h-10" /> : <ShieldCheck className="w-10 h-10" />}
        </div>
        
        <h3 className="text-xl font-bold text-center text-[#1a1a1a] mb-2">
          {isSetupMode ? "Set up 2FA to continue" : "Security Verification"}
        </h3>
        
        <p className="text-sm text-center text-[#6b7280] mb-6">
          {isSetupMode 
            ? "Because you are performing an administrative action, you must link an Authenticator App (Google/Apple) first." 
            : "Enter the 6-digit code from your Authenticator App to approve this user."}
        </p>

        {loading ? (
          <div className="flex justify-center py-8">
            <Loader2 className="w-8 h-8 animate-spin text-[#1f3864]" />
          </div>
        ) : (
          <div className="space-y-4">
            {isSetupMode && qrCode && (
              <div className="flex justify-center bg-[#F7F7F5] p-4 rounded-xl border border-[#e5e7eb]">
                <img src={qrCode} alt="QR Code" className="w-48 h-48" />
              </div>
            )}

            {error && <div className="text-sm text-red-600 bg-red-50 p-3 rounded-lg border border-red-100">{error}</div>}

            <input
              type="text"
              maxLength={6}
              placeholder="000000"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              className="w-full text-center tracking-[0.5em] text-2xl font-mono rounded-lg border border-[#e5e7eb] px-4 py-3 outline-none focus:ring-2 focus:ring-[#1f3864]"
            />

            <div className="flex gap-3 pt-2">
              <button 
                onClick={onCancel}
                className="flex-1 py-2.5 rounded-lg border border-[#e5e7eb] text-[#374151] font-medium hover:bg-gray-50"
              >
                Cancel
              </button>
              <button 
                onClick={handleVerify}
                disabled={verifying || code.length < 6}
                className="flex-1 py-2.5 rounded-lg bg-[#1f3864] text-white font-medium hover:bg-[#162b50] disabled:opacity-70 flex justify-center items-center gap-2"
              >
                {verifying && <Loader2 className="w-4 h-4 animate-spin" />}
                Verify Code
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}