"use client";

import { useState, useRef, useEffect } from "react";
import {
  Scale,
  Send,
  Loader2,
  AlertCircle,
  CheckCircle2,
  FileDown,
  Sparkles,
} from "lucide-react";

type Role = "user" | "ai";

interface Message {
  id: string;
  role: Role;
  text: string;
  fileUrl?: string;
  fileName?: string;
}

type Status = "idle" | "thinking" | "rendering" | "success" | "error";

function generateInvoiceId() {
  return `INV-${Math.floor(1000 + Math.random() * 9000)}`; 
}

function buildPromptPayload(messages: Message[], latestUserText: string, sessionId: string): string {
  const systemNote = `\n\n[SYSTEM NOTE: The strict invoice_number for this session is ${sessionId}. You MUST use this exact ID in your JSON.]`;
  
  if (messages.length === 0) return latestUserText + systemNote;

  const history = messages
    .map((m) =>
      m.role === "user" ? `User: ${m.text}` : `AI asked: ${m.text}`
    )
    .join("\n");

  return history + `\nUser answered: ${latestUserText}` + systemNote;
}

function uid() {
  return Math.random().toString(36).slice(2, 9);
}

export default function InvoiceGeneratorPage() {
  const fetchNewInvoiceId = async () => {
    try {
      const res = await fetch("http://127.0.0.1:8000/api/get-next-invoice-id");
      const data = await res.json();
      if (data.invoice_id) {
        setSessionInvoiceId(data.invoice_id);
      }
    } catch (err) {
      console.error("Failed to fetch ID", err);
    }
  };
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [status, setStatus] = useState<Status>("idle");
  const [errorMessage, setErrorMessage] = useState("");
  const [successFile, setSuccessFile] = useState("");
  const [sessionInvoiceId, setSessionInvoiceId] = useState("");
  const chatBottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const isLoading = status === "thinking" || status === "rendering";

  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, status]);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const handleSend = async () => {
    const text = input.trim();
    if (!text || isLoading) return;
    
    const userMsg: Message = { id: uid(), role: "user", text };
    const previousMessages = [...messages];
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setErrorMessage("");
    setSuccessFile("");
    setStatus("thinking");

    if (inputRef.current) inputRef.current.style.height = "44px";

    const promptPayload = buildPromptPayload(previousMessages, text, sessionInvoiceId);;

    try {
      const response = await fetch(
        "http://127.0.0.1:8000/api/prompt-to-invoice",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ prompt: promptPayload }),
        }
      );

      if (!response.ok) {
        let detail = `Server error ${response.status}`;
        try {
          const err = await response.json();
          if (err?.detail) detail = err.detail;
        } catch {}
        throw new Error(detail);
      }

      const contentType = response.headers.get("Content-Type") ?? "";

      if (contentType.includes("application/json")) {
        const data = await response.json();
        
        if (data.status === "success") {
          setStatus("success");
          setSuccessFile(data.message);
        } else {
          const aiMsg: Message = {
            id: uid(),
            role: "ai",
            text: data.message ?? "Could you clarify a few details?",
          };
          setMessages((prev) => [...prev, aiMsg]);
          setStatus("idle");
          setTimeout(() => inputRef.current?.focus(), 50);
        }

      } else if (contentType.includes("application/pdf")) {
        const emailSentTo = response.headers.get("X-Email-Status");
        
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const filename = `invoice_${Date.now()}.pdf`;
        
        let finalMessage = "I have successfully generated your invoice! You can download it below.";
        if (emailSentTo) {
          finalMessage = `I have successfully generated your invoice! A copy has also been securely emailed to ${emailSentTo}. You can download your local copy below.`;
        }
        
        const aiMsg: Message = {
          id: uid(),
          role: "ai",
          text: finalMessage,
          fileUrl: url,
          fileName: filename
        };
        
        setMessages((prev) => [...prev, aiMsg]);
        setStatus("idle");
      } else {
        throw new Error(`Unexpected Content-Type: ${contentType}`);
      }
    } catch (err: unknown) {
      setErrorMessage(
        err instanceof Error ? err.message : "Something went wrong. Please try again."
      );
      setStatus("error");
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

 useEffect(() => {
    inputRef.current?.focus();
    fetchNewInvoiceId();
  }, []);

  const handleReset = () => {
    setMessages([]);
    setInput("");
    setStatus("idle");
    setErrorMessage("");
    setSuccessFile("");
    fetchNewInvoiceId(); // <--- Grabs the NEXT sequence number for the new chat
    setTimeout(() => inputRef.current?.focus(), 50);
  };

  return (
    <main className="min-h-screen bg-[#F7F7F5] flex flex-col items-center justify-center px-4 py-10 font-sans">
      <div className="mb-6 text-center">
        <div className="inline-flex items-center gap-2 mb-2">
          <Scale className="w-5 h-5 text-[#1f3864]" strokeWidth={1.5} />
          <span className="text-xs font-semibold tracking-[0.2em] uppercase text-[#1f3864] opacity-70">
            Pentacles Legal
          </span>
        </div>
        <h1 className="text-2xl font-bold tracking-tight text-[#1a1a1a]">
          AI Invoice Generator
        </h1>
        <p className="mt-1 text-sm text-[#6b7280] max-w-sm mx-auto">
          Describe your invoice in plain English. The AI will ask if it needs anything else.
        </p>
      </div>

      <div className="w-full max-w-2xl bg-white border border-[#e5e7eb] rounded-2xl shadow-sm flex flex-col overflow-hidden">
        <div className="overflow-y-auto px-5 py-5 space-y-4 min-h-[360px] max-h-[480px]">
          {messages.length === 0 && !isLoading && status !== "error" && (
            <div className="h-full flex flex-col items-center justify-center text-center py-10 gap-3">
              <div className="w-12 h-12 rounded-full bg-[#1f3864]/10 flex items-center justify-center">
                <Sparkles className="w-5 h-5 text-[#1f3864] opacity-60" />
              </div>
              <p className="text-sm text-[#9ca3af] max-w-xs leading-relaxed">
                Start by describing your invoice — client, services, amounts, and address.
              </p>
              <div className="mt-1 flex flex-col gap-1.5 w-full max-w-xs">
                {[
                  "Invoice Autobahn Trucking for ₹30k for Legal Opinion…",
                  "Create invoice for Ram Sharma, ₹15,000 for document review…",
                ].map((ex) => (
                  <button
                    key={ex}
                    onClick={() => {
                      setInput(ex);
                      inputRef.current?.focus();
                    }}
                    className="text-xs text-left text-[#6b7280] bg-[#f9fafb] hover:bg-[#f3f4f6] border border-[#e5e7eb] rounded-lg px-3 py-2 transition-colors"
                  >
                    "{ex}"
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              {msg.role === "ai" && (
                <div className="w-6 h-6 rounded-full bg-[#1f3864]/10 flex items-center justify-center mr-2 mt-0.5 shrink-0">
                  <Scale className="w-3 h-3 text-[#1f3864] opacity-70" />
                </div>
              )}
              <div
                className={`max-w-[78%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap
                  ${msg.role === "user"
                    ? "bg-[#1f3864] text-white rounded-tr-sm"
                    : "bg-[#f3f4f6] text-[#374151] rounded-tl-sm border border-[#e5e7eb]"
                  }`}
              >
                {msg.text}
                
                {msg.fileUrl && (
                  <div className="mt-3">
                    <a
                      href={msg.fileUrl}
                      download={msg.fileName}
                      className="inline-flex items-center gap-2 bg-white border border-[#e5e7eb] text-[#1f3864] px-4 py-2 rounded-lg text-xs font-semibold hover:bg-[#f9fafb] transition-colors shadow-sm"
                    >
                      <FileDown className="w-4 h-4" />
                      Download {msg.fileName}
                    </a>
                  </div>
                )}
              </div>
            </div>
          ))}

          {isLoading && (
            <div className="flex justify-start">
              <div className="w-6 h-6 rounded-full bg-[#1f3864]/10 flex items-center justify-center mr-2 mt-0.5 shrink-0">
                <Scale className="w-3 h-3 text-[#1f3864] opacity-70" />
              </div>
              <div className="bg-[#f3f4f6] border border-[#e5e7eb] rounded-2xl rounded-tl-sm px-4 py-3 flex items-center gap-2">
                <Loader2 className="w-3.5 h-3.5 text-[#1f3864] animate-spin" />
                <span className="text-sm text-[#6b7280]">
                  {status === "rendering" ? "Rendering PDF…" : "AI is thinking…"}
                </span>
              </div>
            </div>
          )}

          {status === "success" && (
            <div className="flex justify-start">
              <div className="w-6 h-6 rounded-full bg-emerald-100 flex items-center justify-center mr-2 mt-0.5 shrink-0">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
              </div>
              <div className="bg-emerald-50 border border-emerald-200 rounded-2xl rounded-tl-sm px-4 py-3 max-w-[78%]">
                <p className="text-sm font-medium text-emerald-800 flex items-center gap-1.5">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  Success
                </p>
                <p className="text-xs text-emerald-700 mt-0.5">{successFile}</p>
                <button
                  onClick={handleReset}
                  className="mt-2 text-xs text-emerald-700 underline underline-offset-2 hover:text-emerald-900"
                >
                  Start a new invoice →
                </button>
              </div>
            </div>
          )}

          <div ref={chatBottomRef} />
        </div>

        <div className="border-t border-[#f3f4f6]" />

        {status === "error" && errorMessage && (
          <div className="mx-4 mt-3 flex items-start gap-2.5 rounded-lg border border-red-200 bg-red-50 px-4 py-3">
            <AlertCircle className="w-4 h-4 text-red-500 mt-0.5 shrink-0" />
            <div className="flex-1">
              <p className="text-sm text-red-700 leading-snug">{errorMessage}</p>
              <button
                onClick={() => setStatus("idle")}
                className="mt-1 text-xs text-red-600 underline underline-offset-2 hover:text-red-800"
              >
                Dismiss
              </button>
            </div>
          </div>
        )}
<div className="px-4 py-4 flex items-end gap-3">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => {
              setInput(e.target.value);
              if (status === "error") setStatus("idle");
              e.target.style.height = "auto";
              e.target.style.height = Math.min(e.target.scrollHeight, 120) + "px";
            }}
            onKeyDown={handleKeyDown}
            // 1. REMOVED the success lock here
            disabled={isLoading} 
            placeholder={
              messages.length === 0
                ? "Describe your invoice…"
                : "Reply to the AI…"
            }
            rows={1}
            className={`flex-1 resize-none rounded-xl border px-4 py-3 text-sm text-[#111827]
              placeholder-[#9ca3af] leading-relaxed
              focus:outline-none focus:ring-2 focus:ring-[#1f3864]/25 focus:border-[#1f3864]
              transition-colors duration-150 overflow-hidden
              disabled:bg-[#f9fafb] disabled:cursor-not-allowed
              ${status === "error" ? "border-red-300" : "border-[#d1d5db]"}
            `}
            style={{ height: "44px" }}
          />
          <button
            onClick={handleSend}
            // 2. REMOVED the success lock here
            disabled={isLoading || !input.trim()} 
            className={`shrink-0 inline-flex items-center justify-center w-11 h-11 rounded-xl
              transition-all duration-150
              focus:outline-none focus:ring-2 focus:ring-[#1f3864]/30 focus:ring-offset-1
              ${isLoading || !input.trim()
                ? "bg-[#1f3864]/30 cursor-not-allowed"
                : "bg-[#1f3864] hover:bg-[#162b50] active:scale-95 shadow-sm"
              }`}
          >
            {isLoading
              ? <Loader2 className="w-4 h-4 text-white animate-spin" />
              : <Send className="w-4 h-4 text-white" />
            }
          </button>
        </div>

        <p className="text-center text-[10px] text-[#d1d5db] pb-3">
          Enter to send · Shift+Enter for new line
        </p>
      </div>

      <p className="mt-8 text-xs text-[#d1d5db]">
        Pentacles Legal Partners LLP · AI-assisted tooling
      </p>
    </main>
  );
}