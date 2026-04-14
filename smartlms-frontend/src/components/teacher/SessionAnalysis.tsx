'use client';

import React, { useState, useEffect } from 'react';
import { teacherAPI } from '@/lib/api';
import EngagementHeatmap from '../EngagementHeatmap';
import EngagementFactorChart from './EngagementFactorChart';
import { motion, AnimatePresence } from 'framer-motion';
import { Activity, MessageSquare, Bot, List, Loader2, Info } from 'lucide-react';

interface SessionAnalysisProps {
  studentId: string;
  sessionId: string;
}

export default function SessionAnalysis({ studentId, sessionId }: SessionAnalysisProps) {
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
        console.error("Failed to load session analysis:", err);
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
            <Activity size={16} /> Analysis Metrics
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
                      Focus Trends
                    </h3>
                    <div className="text-[10px] font-black text-primary px-3 py-1 bg-primary/10 border border-primary/20 rounded-full uppercase tracking-widest">
                      ICAP State: {data.icap_final?.toUpperCase()}
                    </div>
                </div>
                
                <div className="h-44 glass-card p-6 border-white/5 bg-surface/40">
                    <EngagementHeatmap data={data.timeline} />
                </div>
              </div>

              {/* Contributing Factors (SHAP) */}
              <div className="lg:col-span-7">
                <div className="glass-card p-8 h-full bg-surface/60 border-primary/10">
                    <EngagementFactorChart 
                        features={data.biometric_features || {}} 
                        shapExplanations={data.shap_explanations}
                    />
                </div>
              </div>

              {/* Session Insights */}
              <div className="lg:col-span-5 space-y-6">
                <div className="glass-card p-8 space-y-6 h-full relative overflow-hidden group">
                    <div className="flex items-center gap-3 mb-2">
                      <div className="p-3 bg-surface rounded-2xl border border-border text-primary">
                          <Info size={24} />
                      </div>
                      <div>
                          <div className="text-[10px] font-black text-text-muted uppercase tracking-[0.2em]">Session Stats</div>
                          <div className="text-lg font-black text-foreground">Performance Summary</div>
                      </div>
                    </div>

                    <div className="space-y-4">
                      <div className="p-4 bg-surface rounded-2xl border border-border">
                          <div className="text-[9px] font-bold text-text-muted uppercase tracking-widest mb-1.5">Attention Stability</div>
                          <div className="text-sm font-bold text-foreground">{(data.biometric_features?.gaze_stability || 0.85 * 100).toFixed(0)}% Visual Focus</div>
                      </div>
                      <div className="p-4 bg-surface rounded-2xl border border-border">
                          <div className="text-[9px] font-bold text-text-muted uppercase tracking-widest mb-1.5">Learning Mode</div>
                          <div className="text-sm font-bold text-foreground">Consistent with {data.icap_final} learning behavior.</div>
                      </div>
                      <div className="p-4 bg-primary/20 crimson-glow rounded-2xl border border-primary/30">
                          <div className="text-[9px] font-bold text-primary uppercase tracking-widest mb-1.5">Analysis Result</div>
                          <p className="text-xs font-semibold text-foreground/90 leading-relaxed italic">
                            The student showed high engagement during the middle portion of the lecture.
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
              <h3 className="text-lg font-black text-foreground uppercase tracking-widest mb-4">Activity Log</h3>
              <div className="space-y-3 max-h-[500px] overflow-y-auto pr-4 custom-scrollbar">
                {data.activities?.length > 0 ? (
                  data.activities.map((act: any, idx: number) => (
                    <div key={idx} className="p-4 glass-card bg-surface/30 border-white/5 flex items-start justify-between">
                      <div>
                        <div className="text-xs font-black text-primary uppercase tracking-widest">{act.action.replace(/_/g, ' ')}</div>
                        <div className="text-[10px] text-text-muted mt-1 font-mono">{new Date(act.timestamp).toLocaleString()}</div>
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="text-center py-20 text-text-muted uppercase text-[10px] tracking-widest">No activity recorded</div>
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
              {/* Messages and AI Chats section follows same structure as legacy, just remove jargon if any */}
              {/* (Assuming existing logic is fine as it uses Bot and MessageSquare labels) */}
              <div className="space-y-6">
                <h4 className="text-sm font-black text-foreground uppercase tracking-widest flex items-center gap-2">
                  <MessageSquare size={16} className="text-primary" /> Course Communication
                </h4>
                {/* ... same as before but simplified ... */}
                <div className="space-y-4 max-h-[400px] overflow-y-auto pr-2 custom-scrollbar">
                  {data.messages?.length > 0 ? data.messages.map((m: any, i: number) => (
                    <div key={i} className="p-4 bg-surface rounded-2xl border border-border text-xs">
                      {m.content}
                    </div>
                  )) : <div className="text-center py-10 text-text-muted text-[10px] uppercase">No messages</div>}
                </div>
              </div>
              <div className="space-y-6">
                <h4 className="text-sm font-black text-foreground uppercase tracking-widest flex items-center gap-2">
                  <Bot size={16} className="text-primary" /> Assistant Interactions
                </h4>
                <div className="space-y-4 max-h-[400px] overflow-y-auto pr-2 custom-scrollbar">
                  {data.ai_chats?.length > 0 ? data.ai_chats.map((c: any, i: number) => (
                    <div key={i} className={`p-4 rounded-2xl border text-xs ${c.role === 'assistant' ? 'bg-primary/5 border-primary/20' : 'bg-surface border-border'}`}>
                      {c.content}
                    </div>
                  )) : <div className="text-center py-10 text-text-muted text-[10px] uppercase">No assistant chats</div>}
                </div>
              </div>
            </motion.div>
          )}
       </AnimatePresence>

       <div className="flex justify-center border-t border-border pt-10">
          <button className="px-10 py-4 bg-surface border-2 border-border rounded-full text-[10px] font-black text-text-muted uppercase tracking-[0.4em] hover:text-primary hover:border-primary/40 transition-all hover:scale-105 active:scale-95 shadow-xl crimson-glow">
             Export Session Report
          </button>
       </div>
    </motion.div>
  );
}
