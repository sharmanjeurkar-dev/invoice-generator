"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, 
  PieChart, Pie, Cell, LineChart, Line 
} from 'recharts';
import html2canvas from 'html2canvas';
import Link from 'next/link';
import { useFirmStore } from "../../store/useFirmStore";
import {
  Scale,
  Send,
  Loader2,
  AlertCircle,
  CheckCircle2,
  FileDown,
  Sparkles,
  Settings
} from "lucide-react";

type Role = "user" | "ai";

const COLORS = ['#10B981', '#EF4444', '#3B82F6', '#F59E0B'];

interface Message {
  id: string;
  role: Role;
  text: string;
  fileUrl?: string;
  fileName?: string;
  dashboardData?: any; 
}

type Status = "idle" | "thinking" | "rendering" | "success" | "error";

function buildPromptPayload(messages: Message[], latestUserText: string, sessionId: string): string {
  
  const safeId = sessionId || "PENDING-ID"; 
  const systemNote = `\n\n[SYSTEM NOTE: IF you are drafting an invoice, the invoice_number for this session is ${safeId}. Ignore this ID if the user is logging an expense or asking for a report.]`;
  
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

function formatYAxisValue(value: number) {
  if (value >= 1000) return `₹${value / 1000}k`;
  return `₹${value}`;
}

export default function InvoiceGeneratorPage() {
  const { firmId, userId, isLoading: isFirmLoading } = useFirmStore();

  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [status, setStatus] = useState<Status>("idle");
  const [errorMessage, setErrorMessage] = useState("");
  const [successFile, setSuccessFile] = useState("");
  
  const invoiceIdRef = useRef<string>("");
  const chatBottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const isLoading = status === "thinking" || status === "rendering";

  const handleDownloadDashboard = async (elementId: string) => {
    const element = document.getElementById(elementId);
    if (!element) return;

    try {
      const canvas = await html2canvas(element, { 
        scale: 2,
        backgroundColor: "#ffffff",
        useCORS: true 
      });
      
      const dataUrl = canvas.toDataURL("image/png");
      const link = document.createElement("a");
      link.download = `Financial_Dashboard_${Date.now()}.png`;
      link.href = dataUrl;
      link.click();
    } catch (err) {
      console.error("Failed to download charts:", err);
    }
  };

   const fetchNewInvoiceId = useCallback(async () => {
    if (!firmId) return; 
    try {
      const res = await fetch(`http://127.0.0.1:8000/api/firms/${firmId}/get-next-invoice-id`);
      const data = await res.json();
      if (data.invoice_id) {
        invoiceIdRef.current = data.invoice_id;
        console.log(invoiceIdRef.current)
      }
    } catch (err) {
      console.error("Failed to fetch ID", err); 
    }
  }, [firmId]);

  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, status]);

  useEffect(() => {
    if (firmId) {
      inputRef.current?.focus();
      fetchNewInvoiceId();
    }
  }, [firmId, fetchNewInvoiceId]);

  const handleSend = async () => {
    const text = input.trim();
    if (!text || isLoading || !firmId) return;
    
    const userMsg: Message = { id: uid(), role: "user", text };
    const previousMessages = [...messages];
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setErrorMessage("");
    setSuccessFile("");
    setStatus("thinking");

    if (inputRef.current) inputRef.current.style.height = "44px";

    const promptPayload = buildPromptPayload(previousMessages, text, invoiceIdRef.current);

    try {
      const response = await fetch(
        `http://127.0.0.1:8000/api/firms/${firmId}/prompt-to-invoice`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ 
            prompt: promptPayload,
            user_id: userId  
          }),
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
        } else if (data.status === "analytics_dashboard") {
          const aiMsg: Message = { 
            id: uid(), 
            role: "ai", 
            text: data.executive_summary,
            dashboardData: data.charts 
          };
          setMessages((prev) => [...prev, aiMsg]);
          setStatus("idle");
        } else {
          const aiMsg: Message = { id: uid(), role: "ai", text: data.message };
          setMessages((prev) => [...prev, aiMsg]);
          setStatus("idle");
        }

      } else if (contentType.includes("application/pdf")) {
        const emailSentTo = response.headers.get("X-Email-Status");
        
        let filename = `invoice_${Date.now()}.pdf`; 
        const contentDisposition = response.headers.get("Content-Disposition");
        
        if (contentDisposition) {
          // This bulletproof regex grabs the filename whether it has quotes around it or not
          const match = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
          if (match && match[1]) {
            // Strip any remaining quotes from the extracted string
            filename = match[1].replace(/['"]/g, ''); 
          }
        }
        
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
       
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
        
        fetchNewInvoiceId(); 
        
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

  const handleReset = () => {
    setMessages([]);
    setInput("");
    setStatus("idle");
    setErrorMessage("");
    setSuccessFile("");
    fetchNewInvoiceId(); 
    setTimeout(() => inputRef.current?.focus(), 50);
  };

  if (isFirmLoading) {
    return (
      <div className="min-h-screen w-full flex justify-center items-center bg-[#F7F7F5]">
        <Loader2 className="h-8 w-8 animate-spin text-[#1f3864]" />
      </div>
    );
  }

  if (!firmId) {
    return (
      <div className="min-h-screen w-full flex flex-col justify-center items-center bg-[#F7F7F5] gap-4">
        <AlertCircle className="h-10 w-10 text-red-500" />
        <h2 className="text-xl font-semibold text-[#1a1a1a]">Authentication Required</h2>
        <p className="text-sm text-[#6b7280]">Please log in to access your ledger.</p>
        <Link 
          href="/login"
          className="mt-2 px-5 py-2.5 bg-[#1f3864] text-white rounded-lg text-sm font-medium hover:bg-[#162b50] transition-colors"
        >
          Go to Login
        </Link>
      </div>
    );
  }

  return (
    <main className="min-h-screen bg-[#F7F7F5] flex flex-col items-center justify-center px-4 py-10 font-sans">
     <div className="mb-6 text-center relative w-full max-w-4xl">
        
        <div className="absolute right-0 top-0">
          <Link 
            href="/settings"
            className="inline-flex items-center gap-2 text-sm font-medium text-[#6b7280] hover:text-[#1f3864] bg-white border border-[#e5e7eb] px-3 py-2 rounded-lg shadow-sm transition-colors"
          >
            <Settings className="w-4 h-4" />
            Firm Settings
          </Link>
        </div>

        <div className="inline-flex items-center gap-2 mb-2">
          <Scale className="w-5 h-5 text-[#1f3864]" strokeWidth={1.5} />
          <span className="text-xs font-semibold tracking-[0.2em] uppercase text-[#1f3864] opacity-70">
            Pentacles Legal
          </span>
        </div>
        <h1 className="text-2xl font-bold tracking-tight text-[#1a1a1a]">
          LEDGER
        </h1>
        <p className="mt-1 text-sm text-[#6b7280] max-w-sm mx-auto">
          Draft invoices, log expenses, and generate financial reports.
        </p>
      </div>

      <div className="w-full max-w-4xl bg-white border border-[#e5e7eb] rounded-2xl shadow-sm flex flex-col overflow-hidden">
        <div className="overflow-y-auto px-5 py-6 space-y-5 min-h-[450px] max-h-[650px]">
          {messages.length === 0 && !isLoading && status !== "error" && (
            <div className="h-full flex flex-col items-center justify-center text-center py-10 gap-3">
              <div className="w-12 h-12 rounded-full bg-[#1f3864]/10 flex items-center justify-center">
                <Sparkles className="w-5 h-5 text-[#1f3864] opacity-60" />
              </div>
              <p className="text-sm text-[#9ca3af] max-w-xs leading-relaxed">
                Start by describing your invoice, logging a firm expense, or asking for a financial report.
              </p>
              <div className="mt-1 flex flex-col gap-1.5 w-full max-w-md">
                {[
                  "Invoice Autobahn Trucking for ₹30,000 for Legal Opinion…",
                  "Log an expense of ₹5000 for the firm electricity bill",
                  "Analyze our financials and give me a complete breakdown."
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
                <div className="w-6 h-6 rounded-full bg-[#1f3864]/10 flex items-center justify-center mr-3 mt-0.5 shrink-0">
                  <Scale className="w-3 h-3 text-[#1f3864] opacity-70" />
                </div>
              )}
              <div
                className={`${msg.dashboardData ? "w-full" : "max-w-[78%]"} rounded-2xl px-5 py-3.5 text-sm leading-relaxed whitespace-pre-wrap
                  ${msg.role === "user"
                    ? "bg-[#1f3864] text-white rounded-tr-sm"
                    : "bg-[#f9fafb] text-[#374151] rounded-tl-sm border border-[#e5e7eb] shadow-sm"
                  }`}
              >
                {msg.text}
                
                {msg.dashboardData && (
                  <div className="mt-5 w-full">
                    <div className="flex justify-between items-center mb-4 px-1">
                      <span className="text-xs font-semibold text-[#1f3864] uppercase tracking-widest opacity-80">
                        Financial Analysis
                      </span>
                      <button
                        onClick={() => handleDownloadDashboard(`dashboard-${msg.id}`)}
                        className="inline-flex items-center gap-1.5 text-xs font-medium text-white bg-[#1f3864] hover:bg-[#162b50] px-3 py-1.5 rounded-lg transition-colors shadow-sm active:scale-95"
                      >
                        <FileDown className="w-3.5 h-3.5" />
                        Save Charts as Image
                      </button>
                    </div>

                    <div 
                      id={`dashboard-${msg.id}`} 
                      className="space-y-6 w-full bg-[#f9fafb] p-4 rounded-xl border border-[#e5e7eb]"
                    >
                      {msg.dashboardData.map((chart: any, index: number) => (
                        <div key={index} className="p-6 bg-white rounded-xl shadow-sm border border-[#e5e7eb]">
                          <h3 className="text-sm font-semibold text-[#1f3864] mb-6 text-center">{chart.title}</h3>
                          <div className="h-[280px] w-full">
                            <ResponsiveContainer width="100%" height="100%">
                              {chart.chart_type === "bar" ? (
                                <BarChart data={chart.data} margin={{ top: 10, right: 10, left: 0, bottom: 5 }}>
                                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f3f4f6" />
                                  <XAxis dataKey={chart.x_key || "period"} stroke="#6b7280" fontSize={11} tickLine={false} axisLine={false} dy={10} />
                                  <YAxis stroke="#6b7280" fontSize={11} tickLine={false} axisLine={false} tickFormatter={formatYAxisValue} width={50}/>
                                  <Tooltip cursor={{ fill: '#f9fafb' }} contentStyle={{ borderRadius: '8px', border: '1px solid #e5e7eb', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)', fontSize: '13px' }} formatter={(v: number) => [`₹${v.toLocaleString()}`, undefined]} />
                                  <Legend wrapperStyle={{ fontSize: '12px', paddingTop: '15px' }} />
                                  {chart.data_keys?.map((key: string, i: number) => (
                                    <Bar key={key} name={key} dataKey={key} fill={COLORS[i % COLORS.length]} radius={[4, 4, 0, 0]} maxBarSize={45} />
                                  ))}
                                </BarChart>
                              ) : chart.chart_type === "line" ? (
                                <LineChart data={chart.data} margin={{ top: 10, right: 10, left: 0, bottom: 5 }}>
                                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f3f4f6" />
                                  <XAxis dataKey={chart.x_key || "period"} stroke="#6b7280" fontSize={11} tickLine={false} axisLine={false} dy={10} />
                                  <YAxis stroke="#6b7280" fontSize={11} tickLine={false} axisLine={false} tickFormatter={formatYAxisValue} width={50}/>
                                  <Tooltip contentStyle={{ borderRadius: '8px', border: '1px solid #e5e7eb', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)', fontSize: '13px' }} formatter={(v: number) => [`₹${v.toLocaleString()}`, undefined]} />
                                  <Legend wrapperStyle={{ fontSize: '12px', paddingTop: '15px' }} />
                                  {chart.data_keys?.map((key: string, i: number) => (
                                    <Line key={key} type="monotone" name={key} dataKey={key} stroke={COLORS[i % COLORS.length]} strokeWidth={2.5} dot={{ r: 4 }} activeDot={{ r: 6 }} />
                                  ))}
                                </LineChart>
                              ) : (
                                <PieChart>
                                  <Pie data={chart.data} cx="50%" cy="50%" innerRadius={70} outerRadius={90} paddingAngle={4} dataKey="value" nameKey="name">
                                    {chart.data.map((entry: any, i: number) => (
                                      <Cell key={`cell-${i}`} fill={COLORS[i % COLORS.length]} />
                                    ))}
                                  </Pie>
                                  <Tooltip contentStyle={{ borderRadius: '8px', border: '1px solid #e5e7eb', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)', fontSize: '13px' }} formatter={(v: number) => `₹${v.toLocaleString()}`} />
                                  <Legend wrapperStyle={{ fontSize: '12px', paddingTop: '15px' }} />
                                </PieChart>
                              )}
                            </ResponsiveContainer>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                
                {msg.fileUrl && (
                  <div className="mt-4">
                    <a
                      href={msg.fileUrl}
                      download={msg.fileName}
                      className="inline-flex items-center gap-2 bg-white border border-[#e5e7eb] text-[#1f3864] px-4 py-2 rounded-lg text-sm font-medium hover:bg-[#f3f4f6] transition-colors shadow-sm"
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
              <div className="w-6 h-6 rounded-full bg-[#1f3864]/10 flex items-center justify-center mr-3 mt-0.5 shrink-0">
                <Scale className="w-3 h-3 text-[#1f3864] opacity-70" />
              </div>
              <div className="bg-[#f9fafb] border border-[#e5e7eb] shadow-sm rounded-2xl rounded-tl-sm px-5 py-3.5 flex items-center gap-3">
                <Loader2 className="w-4 h-4 text-[#1f3864] animate-spin" />
                <span className="text-sm font-medium text-[#6b7280]">
                  {status === "rendering" ? "Rendering PDF…" : "AI is processing…"}
                </span>
              </div>
            </div>
          )}

          {status === "success" && (
            <div className="flex justify-start">
              <div className="w-6 h-6 rounded-full bg-emerald-100 flex items-center justify-center mr-3 mt-0.5 shrink-0">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
              </div>
              <div className="bg-emerald-50 border border-emerald-200 shadow-sm rounded-2xl rounded-tl-sm px-5 py-4 max-w-[78%]">
                <p className="text-sm font-semibold text-emerald-800 flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4" />
                  Success
                </p>
                <p className="text-sm text-emerald-700 mt-1 whitespace-pre-wrap leading-relaxed">{successFile}</p>
                <button
                  onClick={handleReset}
                  className="mt-3 text-sm font-medium text-emerald-700 underline underline-offset-4 hover:text-emerald-900 transition-colors"
                >
                  Start a new request →
                </button>
              </div>
            </div>
          )}

          <div ref={chatBottomRef} />
        </div>

        <div className="border-t border-[#f3f4f6]" />

        {status === "error" && errorMessage && (
          <div className="mx-4 mt-3 flex items-start gap-2.5 rounded-lg border border-red-200 bg-red-50 px-4 py-3 shadow-sm">
            <AlertCircle className="w-4 h-4 text-red-500 mt-0.5 shrink-0" />
            <div className="flex-1">
              <p className="text-sm font-medium text-red-700 leading-snug">{errorMessage}</p>
              <button
                onClick={() => setStatus("idle")}
                className="mt-1 text-xs font-semibold text-red-600 underline underline-offset-2 hover:text-red-800"
              >
                Dismiss
              </button>
            </div>
          </div>
        )}
        <div className="px-5 py-4 flex items-end gap-3 bg-white">
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
            disabled={isLoading} 
            placeholder={
              messages.length === 0
                ? "Describe your invoice, expense, or ask for a report…"
                : "Reply to the AI…"
            }
            rows={1}
            className={`flex-1 resize-none rounded-xl border px-4 py-3 text-sm text-[#111827]
              placeholder-[#9ca3af] leading-relaxed shadow-sm
              focus:outline-none focus:ring-2 focus:ring-[#1f3864]/20 focus:border-[#1f3864]
              transition-all duration-200 overflow-hidden
              disabled:bg-[#f9fafb] disabled:cursor-not-allowed
              ${status === "error" ? "border-red-300 ring-1 ring-red-100" : "border-[#d1d5db]"}
            `}
            style={{ height: "46px" }}
          />
          <button
            onClick={handleSend}
            disabled={isLoading || !input.trim()} 
            className={`shrink-0 inline-flex items-center justify-center w-[46px] h-[46px] rounded-xl
              transition-all duration-200
              focus:outline-none focus:ring-2 focus:ring-[#1f3864]/30 focus:ring-offset-2
              ${isLoading || !input.trim()
                ? "bg-[#f3f4f6] text-[#9ca3af] border border-[#e5e7eb] cursor-not-allowed"
                : "bg-[#1f3864] text-white hover:bg-[#162b50] active:scale-95 shadow-md hover:shadow-lg"
              }`}
          >
            {isLoading
              ? <Loader2 className="w-5 h-5 animate-spin" />
              : <Send className="w-4 h-4 ml-0.5" />
            }
          </button>
        </div>

        <p className="text-center text-[11px] font-medium text-[#9ca3af] pb-4 bg-white">
          Enter to send · Shift+Enter for new line
        </p>
      </div>

      <p className="mt-8 text-xs font-medium text-[#9ca3af]">
        FINANCE AND ACCOUNTING · AI-assisted tooling
      </p>
    </main>
  );
}