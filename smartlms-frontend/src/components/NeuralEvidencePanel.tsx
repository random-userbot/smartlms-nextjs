'use client';

import React, { useState, useEffect } from 'react';
import { 
  Activity, 
  Clock, 
  Monitor, 
  ExternalLink, 
  ShieldCheck, 
  Fingerprint,
  Zap,
  Layout,
  Terminal,
  MousePointer2,
  Keyboard
} from 'lucide-react';
import { api } from '@/lib/api';

interface EvidenceLog {
  id: string;
  action: string;
  details: any;
  created_at: string;
}

export default function NeuralEvidencePanel() {
  const [logs, setLogs] = useState<EvidenceLog[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Fetch real activity logs from the backend
    const fetchLogs = async () => {
      try {
        const res = await api.get('/api/activity/recent');
        const logEntries = Array.isArray(res.data) ? res.data : [];
        setLogs(logEntries.slice(0, 15));
      } catch (err) {
        console.error("Activity Update Failure:", err);
      } finally {
        setLoading(false);
      }
    };

    fetchLogs();
    const interval = setInterval(fetchLogs, 10000); // Live poll every 10s
    return () => clearInterval(interval);
  }, []);

  const getLogIcon = (action: string) => {
    switch (action) {
      case 'tab_switch': return <Layout size={14} className="text-warning" />;
      case 'idle_detected': return <Clock size={14} className="text-text-muted" />;
      case 'lecture_start': return <Activity size={14} className="text-success" />;
      case 'quiz_submit': return <ShieldCheck size={14} className="text-primary" />;
      case 'mouse_activity': return <MousePointer2 size={14} className="text-info" />;
      case 'keyboard_activity': return <Keyboard size={14} className="text-info" />;
      default: return <Fingerprint size={14} className="text-primary" />;
    }
  };

  if (loading) return (
    <div className="glass-card p-12 flex flex-col items-center justify-center gap-4 border-white/5 bg-surface/30">
       <Terminal size={40} className="text-primary/20 animate-pulse" />
       <div className="text-[10px] font-black text-text-muted uppercase tracking-[0.5em]">Updating Activity...</div>
    </div>
  );

  const handleExportCSV = () => {
    if (logs.length === 0) return;
    
    const headers = ["Timestamp", "Action", "Context"];
    const validLogs = Array.isArray(logs) ? logs : [];
    const rows = validLogs.map(log => [
      new Date(log.created_at).toLocaleString(),
      log.action,
      JSON.stringify(log.details).replace(/"/g, '""')
    ]);

    const csvContent = [
      headers.join(","),
      ...(rows || []).map(r => `"${r[0]}","${r[1]}","${r[2]}"`)
    ].join("\n");

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute("download", `study_activity_log_${new Date().toISOString().slice(0, 10)}.csv`);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="glass-card border-primary/20 overflow-hidden flex flex-col bg-surface/50 backdrop-blur-3xl h-full shadow-2xl relative shadow-primary/5">
      <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-primary/50 via-accent/50 to-primary/50"></div>
      
      <div className="p-8 border-b border-white/5 flex items-center justify-between bg-primary/5">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-2xl bg-primary flex items-center justify-center text-white crimson-glow">
            <Fingerprint size={24} />
          </div>
          <div>
            <h3 className="text-xl font-black text-white tracking-tighter uppercase">Study Activity Log</h3>
            <div className="flex items-center gap-2 text-[10px] font-black text-primary uppercase tracking-widest mt-1">
              <div className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse" /> Live Activity Track
            </div>
          </div>
        </div>
        <div className="px-4 py-2 bg-white/5 rounded-xl border border-white/10 text-[10px] font-black text-text-muted uppercase tracking-widest">
          Simple History Mode: ON
        </div>
      </div>

      <div className="flex-1 overflow-y-auto max-h-[450px] p-4 space-y-3 custom-scrollbar">
        {!Array.isArray(logs) || logs.length === 0 ? (
          <div className="p-20 text-center opacity-40">
             <div className="text-sm font-bold text-white mb-2">No activity detected here yet.</div>
             <p className="text-xs text-text-muted">Start a lesson to see some results.</p>
          </div>
        ) : (
          logs.map((log: any, i: number) => (
            <div 
              key={log.id || i} 
              className="group flex flex-col gap-3 p-5 rounded-[2rem] bg-background/40 border border-white/5 hover:border-primary/40 hover:bg-primary/5 transition-all animate-fade-in"
              style={{ animationDelay: `${i * 50}ms` }}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-white/5 rounded-lg border border-white/5 group-hover:scale-110 transition-transform">
                    {getLogIcon(log.action)}
                  </div>
                  <span className="text-xs font-black text-white uppercase tracking-widest">{log.action.replace('_', ' ')}</span>
                </div>
                <span className="text-[9px] font-black text-text-muted uppercase tracking-widest">
                  {new Date(log.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                </span>
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                 <div className="flex flex-col gap-1">
                    <span className="text-[8px] font-black text-text-muted uppercase tracking-widest opacity-40">Context</span>
                    <div className="text-[10px] font-bold text-white/70 truncate">
                       {JSON.stringify(log.details || {}).length > 2 ? JSON.stringify(log.details) : 'Active'}
                    </div>
                 </div>
                 <div className="flex flex-col gap-1 items-end">
                    <span className="text-[8px] font-black text-text-muted uppercase tracking-widest opacity-40">Verification</span>
                    <div className="flex items-center gap-1.5 text-[10px] font-black text-success uppercase">
                       <ShieldCheck size={10} /> Trusted Node
                    </div>
                 </div>
              </div>
            </div>
          ))
        )}
      </div>

      <div className="p-6 bg-primary/5 border-t border-white/5 flex items-center justify-between">
         <div className="flex items-center gap-3">
            <Monitor size={16} className="text-text-muted" />
            <span className="text-[10px] font-black text-text-muted uppercase tracking-[0.2em]">Source: Local System</span>
         </div>
         <button 
          onClick={handleExportCSV}
          className="flex items-center gap-2 text-[10px] font-black text-primary uppercase tracking-widest hover:text-white transition-colors"
         >
            Download Full Log <ExternalLink size={12} />
         </button>
      </div>
    </div>
  );
}
