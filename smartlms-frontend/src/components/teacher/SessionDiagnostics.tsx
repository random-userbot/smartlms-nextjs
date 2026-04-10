'use client';

import React, { useState, useEffect } from 'react';
import { teacherAPI } from '@/lib/api';
import EngagementHeatmap from '../EngagementHeatmap';
import PerformanceCorrelationChart from './PerformanceCorrelationChart';
import { motion, AnimatePresence } from 'framer-motion';
import { Activity, MessageSquare, Bot, List, Loader2, Info } from 'lucide-react';

interface SessionDiagnosticsProps {
  studentId: string;
  sessionId: string;
}

export default function SessionDiagnostics({ studentId, sessionId }: SessionDiagnosticsProps) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'metrics' | 'activity' | 'interactions'>('metrics');

  useEffect(() => {
    if (!studentId || !sessionId) return;
    
    setLoading(true);
    teacherAPI.getStudentSessionDiagnostics(studentId, sessionId)
      .then(res => {
        setData(res.data);
        setLoading(false);
      })
      .catch(err => {
        console.error("Failed to load diagnostic details:", err);
        setLoading(false);
      });
  }, [studentId, sessionId]);

  if (loading) {
    return (
      <div className="h-96 flex flex-col items-center justify-center space-y-4 bg-surface/50 rounded-[3rem] border border-border">
         <Loader2 className="w-10 h-10 text-primary animate-spin" />
         <div className="text-[10px] font-black uppercase tracking-[0.4em] text-text-muted">Analyzing Session Data...</div>
      </div>
    );
  }

  if (!data) return null;

  return (
    <motion.div 
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="space-y-10"
    >
       {/* Tab Navigation */}
       <div className="flex items-center gap-6 border-b border-border pb-4">
          <button 
            onClick={() => setActiveTab('metrics')}
            className={`flex items-center gap-2 text-xs font-black uppercase tracking-widest transition-colors ${activeTab === 'metrics' ? 'text-primary' : 'text-text-muted hover:text-foreground'}`}
          >
            <Activity size={16} /> Session Metrics
          </button>
          <button 
            onClick={() => setActiveTab('activity')}
            className={`flex items-center gap-2 text-xs font-black uppercase tracking-widest transition-colors ${activeTab === 'activity' ? 'text-primary' : 'text-text-muted hover:text-foreground'}`}
          >
            <List size={16} /> Activity Log
          </button>
          <button 
            onClick={() => setActiveTab('interactions')}
            className={`flex items-center gap-2 text-xs font-black uppercase tracking-widest transition-colors ${activeTab === 'interactions' ? 'text-primary' : 'text-text-muted hover:text-foreground'}`}
          >
            <MessageSquare size={16} /> Interactions
          </button>
       </div>

       <AnimatePresence mode="wait">
          {activeTab === 'metrics' && (
            <motion.div 
              key="metrics"
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 10 }}
              className="grid grid-cols-1 lg:grid-cols-12 gap-10"
            >
              {/* Timeline Analysis */}
              <div className="lg:col-span-12 space-y-6">
                <div className="flex items-center justify-between px-2">
                    <h3 className="text-xl font-black text-foreground tracking-tight flex items-center gap-3 uppercase italic">
                      Performance Dynamics
                    </h3>
                    <div className="text-[10px] font-black text-primary px-3 py-1 bg-primary/10 border border-primary/20 rounded-full uppercase tracking-widest">
                      ICAP State: {data.icap_final?.toUpperCase()}
                    </div>
                </div>
                
                <div className="h-44 glass-card p-6 border-white/5 bg-surface/40">
                    <EngagementHeatmap data={data.timeline} />
                </div>
              </div>

              {/* Feature Correlation */}
              <div className="lg:col-span-7">
                <div className="glass-card p-8 h-full bg-surface/60 border-primary/10">
                    <PerformanceCorrelationChart features={data.biometric_features} />
                </div>
              </div>

              {/* Learning Profile Info */}
              <div className="lg:col-span-5 space-y-6">
                <div className="glass-card p-8 space-y-6 h-full relative overflow-hidden group">
                    <div className="flex items-center gap-3 mb-2">
                      <div className="p-3 bg-surface rounded-2xl border border-border text-primary">
                          <Info size={24} />
                      </div>
                      <div>
                          <div className="text-[10px] font-black text-text-muted uppercase tracking-[0.2em]">Session Stats</div>
                          <div className="text-lg font-black text-foreground">Diagnostic Summary</div>
                      </div>
                    </div>

                    <div className="space-y-4">
                      <div className="p-4 bg-surface rounded-2xl border border-border">
                          <div className="text-[9px] font-bold text-text-muted uppercase tracking-widest mb-1.5">Attention Stability</div>
                          <div className="text-sm font-bold text-foreground">{(data.biometric_features?.gaze_stability || 0.85 * 100).toFixed(0)}% Visual Focus</div>
                      </div>
                      <div className="p-4 bg-surface rounded-2xl border border-border">
                          <div className="text-[9px] font-bold text-text-muted uppercase tracking-widest mb-1.5">Behavioral Mode</div>
                          <div className="text-sm font-bold text-foreground">Aligned with {data.icap_final} pedagogical patterns.</div>
                      </div>
                      <div className="p-4 bg-primary/20 crimson-glow rounded-2xl border border-primary/30">
                          <div className="text-[9px] font-bold text-primary uppercase tracking-widest mb-1.5">Forensic Observation</div>
                          <p className="text-xs font-semibold text-foreground/90 leading-relaxed italic">
                            High consistency detected in non-verbal features. Data points added to research dataset.
                          </p>
                      </div>
                    </div>
                </div>
              </div>
            </motion.div>
          )}

          {activeTab === 'activity' && (
            <motion.div 
              key="activity"
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 10 }}
              className="space-y-4"
            >
              <h3 className="text-lg font-black text-foreground uppercase tracking-widest mb-4">Activity Log (Raw Telemetry)</h3>
              <div className="space-y-3 max-h-[500px] overflow-y-auto pr-4 custom-scrollbar">
                {data.activities?.length > 0 ? (
                  data.activities.map((act: any, idx: number) => (
                    <div key={idx} className="p-4 glass-card bg-surface/30 border-white/5 flex items-start justify-between">
                      <div>
                        <div className="text-xs font-black text-primary uppercase tracking-widest">{act.action.replace(/_/g, ' ')}</div>
                        <div className="text-[10px] text-text-muted mt-1 font-mono">{act.timestamp}</div>
                      </div>
                      {act.details && (
                        <div className="text-[10px] text-text-muted bg-black/20 p-2 rounded-lg font-mono">
                          {JSON.stringify(act.details)}
                        </div>
                      )}
                    </div>
                  ))
                ) : (
                  <div className="text-center py-20 text-text-muted uppercase text-[10px] tracking-widest">No activity nodes recorded</div>
                )}
              </div>
            </motion.div>
          )}

          {activeTab === 'interactions' && (
            <motion.div 
              key="interactions"
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 10 }}
              className="grid grid-cols-1 md:grid-cols-2 gap-10"
            >
              {/* Course Messages */}
              <div className="space-y-6">
                <h4 className="text-sm font-black text-foreground uppercase tracking-widest flex items-center gap-2">
                  <MessageSquare size={16} className="text-primary" /> Course Communication
                </h4>
                <div className="space-y-4 max-h-[400px] overflow-y-auto pr-2 custom-scrollbar">
                  {data.messages?.length > 0 ? (
                    data.messages.map((msg: any, idx: number) => (
                      <div key={idx} className="p-4 bg-surface rounded-2xl border border-border">
                        <div className="flex justify-between items-center mb-2">
                          <span className="text-[10px] font-black text-primary uppercase">{msg.sender}</span>
                          <span className="text-[9px] text-text-muted font-mono">{new Date(msg.timestamp).toLocaleTimeString()}</span>
                        </div>
                        <p className="text-xs text-foreground/90 leading-relaxed">{msg.content}</p>
                      </div>
                    ))
                  ) : (
                    <div className="text-center py-10 text-text-muted uppercase text-[9px] tracking-widest border border-dashed border-border rounded-2xl">No messages tracked</div>
                  )}
                </div>
              </div>

              {/* Aika AI Chats */}
              <div className="space-y-6">
                <h4 className="text-sm font-black text-foreground uppercase tracking-widest flex items-center gap-2">
                  <Bot size={16} className="text-primary" /> Aika Tutor Interactions
                </h4>
                <div className="space-y-4 max-h-[400px] overflow-y-auto pr-2 custom-scrollbar">
                  {data.ai_chats?.length > 0 ? (
                    data.ai_chats.map((chat: any, idx: number) => (
                      <div key={idx} className={`p-4 rounded-2xl border ${chat.role === 'assistant' ? 'bg-primary/5 border-primary/20 ml-4' : 'bg-surface border-border mr-4'}`}>
                        <div className="flex justify-between items-center mb-1">
                          <span className={`text-[9px] font-black uppercase ${chat.role === 'assistant' ? 'text-primary' : 'text-text-muted'}`}>
                            {chat.role === 'assistant' ? 'Aika Tutor' : 'Student'}
                          </span>
                        </div>
                        <p className="text-xs text-foreground/90 leading-relaxed">{chat.content}</p>
                      </div>
                    ))
                  ) : (
                    <div className="text-center py-10 text-text-muted uppercase text-[9px] tracking-widest border border-dashed border-border rounded-2xl">No AI tutor sessions recorded</div>
                  )}
                </div>
              </div>
            </motion.div>
          )}
       </AnimatePresence>

       <div className="flex justify-center border-t border-border pt-10">
          <button className="px-10 py-4 bg-surface border-2 border-border rounded-full text-[10px] font-black text-text-muted uppercase tracking-[0.4em] hover:text-primary hover:border-primary/40 transition-all hover:scale-105 active:scale-95 shadow-xl crimson-glow">
             Export Session Dataset
          </button>
       </div>
    </motion.div>
  );
}
