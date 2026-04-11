'use client';

import React from 'react';
import { 
  BarChart3, 
  Brain, 
  Zap, 
  Activity, 
  TrendingUp, 
  Target, 
  Compass, 
  LayoutDashboard,
  CheckCircle2,
  ChevronRight,
  ArrowRight
} from 'lucide-react';
import { useRouter } from 'next/navigation';

interface SessionSummaryProps {
  data: any;
  lectureId: string;
  nextLectureId?: string | null;
}

export default function SessionSummary({ data, lectureId, nextLectureId }: SessionSummaryProps) {
  const router = useRouter();
  
  const score = data?.overall_score ?? data?.engagement_score ?? 0;
  const icap = data?.icap_classification || 'Passive';
  const points = data?.points_awarded || 0;
  
  // Extract real metrics from session features if available
  const explainability = data?.explanation_breakdown || [
    { factor: 'Focused Gaze', weight: data?.features?.gaze_stability || 0, color: 'success' },
    { factor: 'Interaction Rate', weight: data?.features?.interaction_frequency || 0, color: 'primary' },
    { factor: 'Sync Consistency', weight: data?.features?.sync_quality || 0, color: 'warning' }
  ];

  const momentum = data?.scores_timeline?.map((t: any) => t.engagement) || [0, 0, 0, 0, 0, 0, 0];

  return (
    <div className="max-w-6xl mx-auto space-y-12 animate-fade-in py-12 px-8">
      {/* Header Splash */}
      <div className="text-center space-y-4">
        <div className="inline-flex items-center gap-2 px-6 py-2 bg-success/10 text-success border border-success/20 rounded-full text-[10px] font-black uppercase tracking-[0.3em]">
          <CheckCircle2 size={12} /> Synchronization Successful
        </div>
        <h1 className="text-6xl font-black text-white tracking-tighter">Session Summary</h1>
        <p className="text-xl font-medium text-text-muted">Your cognitive resonance signatures have been archived.</p>
      </div>

      {/* Hero Stats */}
      <div className="grid grid-cols-12 gap-8">
        <div className="col-span-12 lg:col-span-4 glass-card p-12 text-center flex flex-col items-center justify-center space-y-6 crimson-glow">
          <div className="relative">
            <div className="w-56 h-56 rounded-full border-8 border-primary/20 flex items-center justify-center">
              <div className="text-7xl font-black text-white shimmer">{score.toFixed(0)}%</div>
            </div>
            <div className="absolute -bottom-4 left-1/2 -translate-x-1/2 px-6 py-2 bg-primary rounded-full text-[10px] font-black text-white uppercase tracking-widest whitespace-nowrap">
              Efficiency Index
            </div>
          </div>
          <div className="space-y-2">
            <h3 className="text-2xl font-black text-white">{icap} Level</h3>
            <p className="text-xs font-bold text-text-muted uppercase tracking-widest">Cognitive Depth Classification</p>
          </div>
        </div>

        <div className="col-span-12 lg:col-span-8 grid grid-cols-2 gap-8">
          <div className="glass-card p-8 space-y-4 hover:border-primary/20 transition-all border-white/5">
            <div className="flex items-center gap-3">
              <Brain size={24} className="text-primary" />
              <h4 className="text-sm font-black text-white uppercase tracking-widest">Neuro-Explainability</h4>
            </div>
            <div className="space-y-4">
               {explainability.map((f: any, i: number) => (
                 <div key={i} className="space-y-2">
                   <div className="flex justify-between text-[10px] font-black uppercase tracking-widest text-text-muted">
                     <span>{f.factor}</span>
                     <span>{f.weight.toFixed(0)}%</span>
                   </div>
                   <div className="h-1.5 bg-white/5 rounded-full overflow-hidden">
                     <div className={`h-full bg-${f.color} rounded-full transition-all duration-1000`} style={{ width: `${f.weight}%` }} />
                   </div>
                 </div>
               ))}
            </div>
          </div>

          <div className="glass-card p-8 space-y-4 hover:border-primary/20 transition-all border-white/5">
             <div className="flex items-center gap-3">
               <TrendingUp size={24} className="text-success" />
               <h4 className="text-sm font-black text-white uppercase tracking-widest">Learning Momentum</h4>
             </div>
             <div className="flex-1 flex items-end justify-between h-32 gap-2">
               {(momentum || []).slice(-7).map((h: number, i: number) => (
                 <div key={i} className="flex-1 bg-primary/20 hover:bg-primary transition-all rounded-t-lg relative group" style={{ height: `${Math.max(5, h)}%` }}>
                   <div className="absolute -top-8 left-1/2 -translate-x-1/2 bg-black text-white text-[8px] font-black px-2 py-1 rounded opacity-0 group-hover:opacity-100 transition-opacity">
                     {h.toFixed(0)}%
                   </div>
                 </div>
               ))}
             </div>
             <div className="text-[8px] font-black text-text-muted uppercase tracking-widest text-center mt-2 flex justify-between">
               <span>Start</span>
               <span>Segment Performance</span>
               <span>End</span>
             </div>
          </div>
        </div>
      </div>

      {/* Next Steps & Gamification */}
      <div className="grid grid-cols-1 gap-8 lg:grid-cols-3">
        <div className="glass-card p-8 bg-primary/5 border-primary/20 flex flex-col gap-4">
           <div className="w-12 h-12 bg-primary/20 rounded-2xl flex items-center justify-center text-primary">
             <Zap size={24} />
           </div>
           <div>
             <h4 className="text-xl font-black text-white">{points} XP</h4>
             <p className="text-[10px] font-black text-primary uppercase tracking-widest">Points Synchronized</p>
           </div>
        </div>
        
        {nextLectureId ? (
          <button 
            onClick={() => router.push(`/lectures/${nextLectureId}`)}
            className="lg:col-span-2 bg-gradient-to-r from-primary to-primary-dark p-8 rounded-[2.5rem] flex items-center justify-between group relative overflow-hidden shadow-2xl hover:scale-[1.02] transition-all"
          >
            <div className="absolute inset-0 bg-white/10 opacity-0 group-hover:opacity-100 transition-opacity" />
            <div className="flex items-center gap-6 relative z-10">
              <div className="w-20 h-20 bg-white/10 backdrop-blur-xl rounded-2xl flex items-center justify-center text-white border border-white/20 shadow-inner">
                <Compass size={40} className="animate-spin-slow" />
              </div>
              <div className="text-left">
                <span className="text-[10px] font-black text-white/60 uppercase tracking-[0.4em] mb-1 block">Sequence Protocol</span>
                <h4 className="text-3xl font-black text-white tracking-tighter leading-none mb-2">Proceed to Next Module</h4>
                <p className="text-xs font-bold text-white/70">Continuous learning flow initialized. Resume synchronization.</p>
              </div>
            </div>
            <ArrowRight size={40} className="text-white group-hover:translate-x-4 transition-transform relative z-10" />
          </button>
        ) : (
          <button 
            onClick={() => router.push('/dashboard')}
            className="lg:col-span-2 glass-card p-8 flex items-center justify-between group hover:bg-white/5"
          >
            <div className="flex items-center gap-6">
              <div className="w-16 h-16 bg-surface rounded-3xl flex items-center justify-center text-white border border-white/10 group-hover:crimson-glow transition-all">
                <LayoutDashboard size={32} />
              </div>
              <div className="text-left">
                <h4 className="text-2xl font-black text-white tracking-tight">Return to Command Dash</h4>
                <p className="text-xs font-bold text-text-muted">Review your global learning trajectory and goals.</p>
              </div>
            </div>
            <ChevronRight size={32} className="text-primary group-hover:translate-x-4 transition-transform" />
          </button>
        )}
      </div>

      {/* Aika Closing Note */}
      <div className="p-8 bg-white/5 border border-white/5 rounded-4xl flex gap-6 items-center italic">
         <div className="w-14 h-14 bg-surface rounded-2xl border border-white/10 flex items-center justify-center text-primary shrink-0">
           <Compass size={24} />
         </div>
         <div>
           <span className="text-[10px] font-black text-primary uppercase tracking-widest block mb-1">Aika Sensei Strategy</span>
           <p className="text-sm text-white/80 leading-relaxed">
             "Your concentration peaked during the second segment. I've noted a slight plateau in Constructive behavior toward the end. Consider deep-work intervals of 25 minutes for the next module."
           </p>
         </div>
      </div>
    </div>
  );
}
