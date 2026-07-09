"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@supabase/supabase-js";
import { useFirmStore } from "../../store/useFirmStore"; // Adjust path if needed

import {
  Building2,
  Landmark,
  Mail,
  Image as ImageIcon,
  UploadCloud,
  Loader2,
  CheckCircle2,
  AlertCircle,
} from "lucide-react";

// --- Supabase client -------------------------------------------------------
const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL;
const SUPABASE_ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

const supabase = createClient(SUPABASE_URL as string, SUPABASE_ANON_KEY as string);

const ACCENT = "#1f3864";

// --- Small building blocks ---------------------------------------------------

function SectionHeader({ icon: Icon, title, description }: any) {
  return (
    <div className="flex items-start gap-3 mb-5">
      <div
        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg"
        style={{ backgroundColor: `${ACCENT}0D` }}
      >
        <Icon className="h-4.5 w-4.5" style={{ color: ACCENT }} strokeWidth={2} />
      </div>
      <div>
        <h2 className="text-[15px] font-semibold text-[#1a1a1a]">{title}</h2>
        {description && (
          <p className="text-[13px] text-[#6b7280] mt-0.5">{description}</p>
        )}
      </div>
    </div>
  );
}

function Field({ label, name, value, onChange, placeholder, type = "text" }: any) {
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={name} className="text-[13px] font-medium text-[#374151]">
        {label}
      </label>
      <input
        id={name}
        name={name}
        type={type}
        value={value ?? ""}
        onChange={onChange}
        placeholder={placeholder}
        className="w-full rounded-lg border border-[#e5e7eb] bg-white px-3.5 py-2.5 text-[14px] text-[#1a1a1a] placeholder:text-[#9ca3af] outline-none transition-shadow duration-150 focus:ring-2 focus:ring-[#1f3864]/20 focus:border-[#1f3864]"
      />
    </div>
  );
}

// --- Main component ----------------------------------------------------------

export default function SettingsPage() {
  const router = useRouter();
  
  // 👇 Pull the dynamic firmId and loading state from Zustand
  const { firmId, isLoading: isFirmLoading } = useFirmStore();

  const [form, setForm] = useState({
    firm_name: "",
    address_line1: "", 
    address_line2: "", 
    bank_name: "",
    account_number: "",
    ifsc_code: "",
    email_sender: "", 
    logo_url: "",
  });

  const [loadingSettings, setLoadingSettings] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [showSuccess, setShowSuccess] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  // Fetch existing settings on mount (only runs when firmId is ready)
  useEffect(() => {
    let cancelled = false;

    async function fetchSettings() {
      if (!firmId) return; // Wait until we have the ID

      try {
        // 👇 Fixed the template literal to use the dynamic ${firmId}
        const res = await fetch(`http://127.0.0.1:8000/api/firms/${firmId}/settings`, { 
          method: "GET" 
        });
        
        if (!res.ok) throw new Error(`Failed to load settings (${res.status})`);
        
        const data = await res.json();
        if (!cancelled && Object.keys(data).length > 0) {
          setForm((prev) => ({ ...prev, ...data }));
        }
      } catch (err) {
        if (!cancelled) {
          setErrorMsg("Could not load existing settings. Starting from a blank form.");
        }
      } finally {
        if (!cancelled) setLoadingSettings(false);
      }
    }

    if (!isFirmLoading) {
      fetchSettings();
    }

    return () => {
      cancelled = true;
    };
  }, [firmId, isFirmLoading]);

  const handleChange = useCallback((e: any) => {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  }, []);

  const handleLogoUpload = useCallback(async (e: any) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    setErrorMsg("");

    try {
      const fileExt = file.name.split(".").pop();
      const fileName = `logo-${Date.now()}.${fileExt}`;

      const { error: uploadError } = await supabase.storage
        .from("Logos")
        .upload(fileName, file);

      if (uploadError) throw uploadError;

      const { data: publicUrlData } = supabase.storage
        .from("Logos")
        .getPublicUrl(fileName);

      setForm((prev) => ({ ...prev, logo_url: publicUrlData.publicUrl }));
    } catch (err) {
      console.error("SUPABASE UPLOAD ERROR:", err);
      setErrorMsg("Logo upload failed. Please ensure your Supabase storage bucket is public.");
    } finally {
      setUploading(false);
    }
  }, []);

  const handleSave = useCallback(async () => {
    if (!firmId) {
      setErrorMsg("Authentication error. Please log in again.");
      return;
    }

    setSaving(true);
    setErrorMsg("");

    try {
      const res = await fetch(`http://127.0.0.1:8000/api/firms/${firmId}/settings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });

      if (!res.ok) throw new Error(`Save failed (${res.status})`);

      setShowSuccess(true);
      
      // 👇 Wait 1 second to show success message, then redirect to /agent
      setTimeout(() => {
        router.push("/agent");
      }, 1000);

    } catch (err) {
      setErrorMsg("Could not save settings. Please check your connection and try again.");
    } finally {
      setSaving(false);
    }
  }, [form, firmId, router]);

  // Show a loading screen while Zustand connects to Supabase
  if (isFirmLoading) {
    return (
      <div className="min-h-screen w-full flex justify-center items-center bg-[#F7F7F5]">
        <Loader2 className="h-8 w-8 animate-spin text-[#1f3864]" />
      </div>
    );
  }

  return (
    <div
      className="min-h-screen w-full flex justify-center px-4 py-10 sm:py-14"
      style={{ backgroundColor: "#F7F7F5" }}
    >
      <div className="w-full max-w-3xl">
        {/* Page heading */}
        <div className="mb-6 px-1">
          <h1 className="text-[22px] font-semibold text-[#1a1a1a]">
            Firm Settings & Setup
          </h1>
          <p className="text-[14px] text-[#6b7280] mt-1">
            These details are used to generate your firm's invoices. Keep them accurate and up to date.
          </p>
        </div>

        {/* Card */}
        <div className="relative bg-white border border-[#e5e7eb] rounded-2xl shadow-sm overflow-hidden">
          {loadingSettings && (
            <div className="absolute inset-0 z-10 flex items-center justify-center bg-white/70 backdrop-blur-[1px]">
              <Loader2 className="h-5 w-5 animate-spin" style={{ color: ACCENT }} />
            </div>
          )}

          <div className="p-6 sm:p-8 space-y-9">
            {/* Section 1: Firm Details */}
            <section>
              <SectionHeader
                icon={Building2}
                title="Firm Details"
                description="Your firm's name and registered address."
              />
              <div className="grid grid-cols-1 gap-4">
                <Field
                  label="Firm Name"
                  name="firm_name"
                  value={form.firm_name}
                  onChange={handleChange}
                  placeholder="Pentacles Legal Partners LLP"
                />
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <Field
                    label="Address Line 1"
                    name="address_line1"
                    value={form.address_line1}
                    onChange={handleChange}
                    placeholder="4th Floor, Lexington Tower"
                  />
                  <Field
                    label="Address Line 2"
                    name="address_line2"
                    value={form.address_line2}
                    onChange={handleChange}
                    placeholder="MG Road, Bengaluru 560001"
                  />
                </div>
              </div>
            </section>

            <div className="border-t border-[#e5e7eb]" />

            {/* Section 2: Banking Information */}
            <section>
              <SectionHeader
                icon={Landmark}
                title="Banking Information"
                description="Used to display payment details on invoices."
              />
              <div className="grid grid-cols-1 gap-4">
                <Field
                  label="Bank Name"
                  name="bank_name"
                  value={form.bank_name}
                  onChange={handleChange}
                  placeholder="HDFC Bank"
                />
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <Field
                    label="Account Number"
                    name="account_number"
                    value={form.account_number}
                    onChange={handleChange}
                    placeholder="50100123456789"
                  />
                  <Field
                    label="IFSC Code"
                    name="ifsc_code"
                    value={form.ifsc_code}
                    onChange={handleChange}
                    placeholder="HDFC0001234"
                  />
                </div>
              </div>
            </section>

            <div className="border-t border-[#e5e7eb]" />

            {/* Section 3: System Config */}
            <section>
              <SectionHeader
                icon={Mail}
                title="System Config"
                description="The address invoices and notifications are sent from."
              />
              <Field
                label="Outbound Email Address"
                name="email_sender"
                type="email"
                value={form.email_sender}
                onChange={handleChange}
                placeholder="billing@pentacleslegal.com"
              />
            </section>

            <div className="border-t border-[#e5e7eb]" />

            {/* Section 4: Logo Upload */}
            <section>
              <SectionHeader
                icon={ImageIcon}
                title="Firm Logo"
                description="Appears on the header of every generated invoice."
              />
              <div className="flex items-center gap-4">
                <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-lg border border-dashed border-[#e5e7eb] bg-[#F7F7F5] overflow-hidden">
                  {form.logo_url ? (
                    <img
                      src={form.logo_url}
                      alt="Firm logo preview"
                      className="h-full w-full object-contain"
                    />
                  ) : (
                    <ImageIcon className="h-5 w-5 text-[#9ca3af]" />
                  )}
                </div>

                <label
                  htmlFor="logo-upload"
                  className="inline-flex items-center gap-2 cursor-pointer rounded-lg border border-[#e5e7eb] bg-white px-4 py-2.5 text-[13px] font-medium text-[#374151] transition-colors hover:bg-[#F7F7F5] focus-within:ring-2 focus-within:ring-[#1f3864]/20"
                >
                  {uploading ? (
                    <Loader2 className="h-4 w-4 animate-spin" style={{ color: ACCENT }} />
                  ) : (
                    <UploadCloud className="h-4 w-4" style={{ color: ACCENT }} />
                  )}
                  {uploading ? "Uploading…" : form.logo_url ? "Replace logo" : "Upload logo"}
                  <input
                    id="logo-upload"
                    type="file"
                    accept="image/*"
                    className="hidden"
                    onChange={handleLogoUpload}
                    disabled={uploading}
                  />
                </label>
              </div>
            </section>
          </div>

          {/* Footer / Save bar */}
          <div className="flex items-center justify-between gap-4 border-t border-[#e5e7eb] bg-[#F7F7F5]/60 px-6 sm:px-8 py-4">
            <div className="min-h-[20px] flex items-center gap-2">
              {errorMsg && (
                <div className="flex items-center gap-1.5 text-[13px] text-red-600">
                  <AlertCircle className="h-3.5 w-3.5" />
                  {errorMsg}
                </div>
              )}
              {showSuccess && !errorMsg && (
                <div className="flex items-center gap-1.5 text-[13px] text-emerald-600 animate-[fadeIn_0.15s_ease-out]">
                  <CheckCircle2 className="h-3.5 w-3.5" />
                  Settings saved successfully! Redirecting...
                </div>
              )}
            </div>

            <button
              type="button"
              onClick={handleSave}
              disabled={saving || uploading || loadingSettings}
              className="inline-flex items-center gap-2 rounded-lg px-5 py-2.5 text-[13px] font-medium text-white transition-opacity disabled:opacity-60 hover:opacity-90"
              style={{ backgroundColor: ACCENT }}
            >
              {saving && <Loader2 className="h-4 w-4 animate-spin" />}
              {saving ? "Saving…" : "Save Settings"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}