"use client";

import React, { useState, useEffect } from "react";
import { useFirmStore } from "../../store/useFirmStore";
import MfaModal from "../../components/MFAmodel";
import { ShieldCheck, UserCheck, Clock, Loader2 } from "lucide-react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export default function TeamDashboard() {
  const { firmId } = useFirmStore();
  const [users, setUsers] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  
  // State to track which user we are trying to approve
  const [approvingUser, setApprovingUser] = useState<string | null>(null);

  useEffect(() => {
    if (firmId) fetchTeam();
  }, [firmId]);

  const fetchTeam = async () => {
    try {
      const res = await fetch(`${API_URL}/api/firms/${firmId}/team`);
      if (res.ok) {
        const data = await res.json();
        setUsers(data);
      }
    } catch (err) {
      console.error("Failed to fetch team", err);
    } finally {
      setLoading(false);
    }
  };

  // Called when the user successfully passes the MFA challenge
  const handleApproveExecute = async () => {
    if (!approvingUser || !firmId) return;

    try {
      const res = await fetch(`${API_URL}/api/firms/${firmId}/users/${approvingUser}/approve`, {
        method: "POST"
      });
      
      if (res.ok) {
        // Refresh the table
        fetchTeam();
      }
    } catch (err) {
      console.error("Approval failed", err);
    } finally {
      setApprovingUser(null);
    }
  };

  if (loading) {
    return <div className="min-h-screen flex items-center justify-center bg-[#F7F7F5]"><Loader2 className="w-8 h-8 animate-spin text-[#1f3864]" /></div>;
  }

  return (
    <div className="min-h-screen bg-[#F7F7F5] py-12 px-6">
      
      {/* Conditionally render the MFA Modal if an approval is pending */}
      {approvingUser && (
        <MfaModal 
          onSuccess={handleApproveExecute} 
          onCancel={() => setApprovingUser(null)} 
        />
      )}

      <div className="max-w-4xl mx-auto bg-white border border-[#e5e7eb] rounded-2xl shadow-sm overflow-hidden">
        <div className="p-6 border-b border-[#e5e7eb] bg-gray-50 flex justify-between items-center">
          <div>
            <h1 className="text-xl font-bold text-[#1a1a1a] flex items-center gap-2">
              <ShieldCheck className="w-5 h-5 text-[#1f3864]" />
              Team Access Management
            </h1>
            <p className="text-sm text-[#6b7280] mt-1">Approve pending members before they can access firm ledgers.</p>
          </div>
        </div>

        <div className="p-0">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-white border-b border-[#e5e7eb] text-[13px] font-semibold text-[#6b7280] uppercase tracking-wider">
                <th className="px-6 py-4">Name</th>
                <th className="px-6 py-4">Email</th>
                <th className="px-6 py-4">Role</th>
                <th className="px-6 py-4 text-right">Status / Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#e5e7eb]">
              {users.map((u: any) => (
                <tr key={u.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-6 py-4 text-sm font-medium text-[#1a1a1a]">{u.full_name}</td>
                  <td className="px-6 py-4 text-sm text-[#6b7280]">{u.email}</td>
                  <td className="px-6 py-4 text-sm text-[#6b7280] capitalize">{u.role}</td>
                  <td className="px-6 py-4 text-right">
                    
                    {u.status === 'approved' ? (
                      <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
                        <UserCheck className="w-3.5 h-3.5" /> Approved
                      </span>
                    ) : (
                      <div className="flex items-center justify-end gap-3">
                        <span className="inline-flex items-center gap-1.5 text-xs font-medium text-amber-600">
                          <Clock className="w-3.5 h-3.5" /> Pending
                        </span>
                        <button
                          onClick={() => setApprovingUser(u.id)}
                          className="px-4 py-1.5 bg-[#1f3864] text-white text-xs font-semibold rounded-lg hover:bg-[#162b50] transition-colors shadow-sm"
                        >
                          Approve
                        </button>
                      </div>
                    )}

                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          
          {users.length === 0 && (
            <div className="p-8 text-center text-sm text-[#6b7280]">No users found for this firm.</div>
          )}
        </div>
      </div>
    </div>
  );
}