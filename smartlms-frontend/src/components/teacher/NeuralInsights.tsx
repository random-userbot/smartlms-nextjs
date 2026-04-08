'use client';

import React, { useState, useEffect } from 'react';
import { teacherAPI } from '@/lib/api';
import EngagementHeatmap from '../EngagementHeatmap';
import AuraCorrelationChart from './AuraCorrelationChart';
import { motion, AnimatePresence } from 'framer-motion';
import { Activity, Zap, BrainCircuit, Loader2 } from 'lucide-react';

interface NeuralInsightsProps {
  studentId: string;
  sessionId: string;
}

export default function NeuralInsights({ studentId, sessionId }: NeuralInsightsProps) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!studentId || !sessionId) return;
    
    setLoading(true);
    teacherAPI.getStudentSessionDiagnostics(studentId, sessionId)
      .then(res => {
        setData(res.data);
        setLoading(false);
      })
      .catch(err => {
        console.error("Failed to load study details:", err);
        setLoading(false);
      });
  }, [studentId, sessionId]);

  if (loading) {
    return (
      <div className="h-96 flex flex-col items-center justify-center space-y-4 bg-surface/50 rounded-[3rem] border border-border">
         <Loader2 className="w-10 h-10 text-primary animate-spin" />
         <div className="text-[10px] font-black uppercase tracking-[0.4em] text-text-muted">Loading Data...</div>
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
       <div className="grid grid-cols-1 lg:grid-cols-12 gap-10">
          {/* Timeline Analysis */}
          <div className="lg:col-span-12 space-y-6">
             <div className="flex items-center justify-between px-2">
                <h3 className="text-xl font-black text-foreground tracking-tight flex items-center gap-3 uppercase italic">
                   <Activity className="text-primary" /> Study Activity History
                </h3>
                <div className="text-[10px] font-black text-primary px-3 py-1 bg-primary/10 border border-primary/20 rounded-full uppercase tracking-widest">
                   Status: {data.icap_final?.toUpperCase()} State
                </div>
             </div>
             
             <div className="h-40 glass-card p-6 border-white/5 bg-surface/40">
                <EngagementHeatmap data={data.timeline} />
             </div>
          </div>

          {/* Focus Analysis */}
          <div className="lg:col-span-7">
             <div className="glass-card p-8 h-full bg-surface/60 border-primary/10">
                <AuraCorrelationChart features={data.aura_features} />
             </div>
          </div>

          {/* Learning Profile Info */}
          <div className="lg:col-span-5 space-y-6">
             <div className="glass-card p-8 space-y-6 h-full relative overflow-hidden group">
                {/* Background Accent */}
                <div className="absolute -top-10 -right-10 w-40 h-40 bg-primary/5 rounded-full blur-[40px] group-hover:bg-primary/10 transition-colors" />
                
                <div className="flex items-center gap-3 mb-2">
                   <div className="p-3 bg-surface rounded-2xl border border-border text-primary">
                      <BrainCircuit size={24} />
                   </div>
                   <div>
                      <div className="text-[10px] font-black text-text-muted uppercase tracking-[0.2em]">Smart Stats</div>
                      <div className="text-lg font-black text-foreground">Learning Profile</div>
                   </div>
                </div>

                <div className="space-y-4">
                   <div className="p-4 bg-surface rounded-2xl border border-border">
                      <div className="text-[9px] font-bold text-text-muted uppercase tracking-widest mb-1.5">Main Focus</div>
                      <div className="text-sm font-bold text-foreground">Gaze Stability - 88% Lock</div>
                   </div>
                   <div className="p-4 bg-surface rounded-2xl border border-border">
                      <div className="text-[9px] font-bold text-text-muted uppercase tracking-widest mb-1.5">Learning Level Analysis</div>
                      <div className="text-sm font-bold text-foreground">Changes match {data.icap_final} mode levels.</div>
                   </div>
                   <div className="p-4 bg-primary/20 crimson-glow rounded-2xl border border-primary/30">
                      <div className="text-[9px] font-bold text-primary uppercase tracking-widest mb-1.5">Helpful Tip</div>
                      <p className="text-xs font-semibold text-foreground/90 leading-relaxed italic">
                        Student shows high concentration when paying attention to the video during timestamps 04:20 - 05:45.
                      </p>
                   </div>
                </div>
             </div>
          </div>
       </div>

       <div className="flex justify-center">
          <button className="px-10 py-4 bg-surface border-2 border-border rounded-full text-[10px] font-black text-text-muted uppercase tracking-[0.4em] hover:text-primary hover:border-primary/40 transition-all hover:scale-105 active:scale-95 shadow-xl crimson-glow">
             Download Study Report
          </button>
       </div>
    </motion.div>
  );
}
