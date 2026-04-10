'use client';

import React, { useState, useEffect } from 'react';
import { analyticsAPI, gamificationAPI, coursesAPI } from '@/lib/api';
import { useAuth } from '@/context/AuthContext';
import { 
  Activity, 
  Play, 
  BookOpen, 
  TrendingUp, 
  Bot, 
  Sparkles, 
  ArrowUpRight, 
  Target,
  Clock,
  Brain,
  Zap,
  AlertCircle,
  ChevronRight,
  LayoutDashboard,
  Download,
  X,
  Check
} from 'lucide-react';
import { 
  ResponsiveContainer, 
  LineChart, 
  Line, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  AreaChart,
  Area
} from 'recharts';
import EngagementWaveform from '@/components/EngagementWaveform';
import Sidebar from '@/components/Sidebar';
import NavigationHeader from '@/components/NavigationHeader';
import NeuralEvidencePanel from '@/components/NeuralEvidencePanel';

export default function AnalyticsPage() {
  const [data, setData] = useState<any>(null);
  const [history, setHistory] = useState<any>(null);
  const [gamification, setGamification] = useState<any>(null);
  const [icapDist, setIcapDist] = useState<any>(null);
  const [myCourses, setMyCourses] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showExportModal, setShowExportModal] = useState(false);
  const [selectedCourseExport, setSelectedCourseExport] = useState<string>('');
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    const fetchData = () => {
      Promise.all([
        analyticsAPI.getStudentDashboard().catch(() => ({ data: null })),
        analyticsAPI.getStudentEngagementHistory(30).catch(() => ({ data: null })),
        analyticsAPI.getStudentICAP().catch(() => ({ data: null })),
        gamificationAPI.getStats().catch(() => ({ data: null })),
        coursesAPI.getMyCourses().catch(() => ({ data: [] })),
      ]).then(([analyticsRes, historyRes, icapRes, gamificationRes, coursesRes]) => {
        setData(analyticsRes.data);
        setHistory(historyRes.data);
        setIcapDist(icapRes.data);
        setGamification(gamificationRes.data);
        setMyCourses(coursesRes.data || []);
      }).finally(() => setLoading(false));
    };

    fetchData();
    const interval = setInterval(fetchData, 10000); // Poll every 10s for live ensemble updates
    return () => clearInterval(interval);
  }, []);

  const handleExport = async () => {
    setExporting(true);
    try {
      const res = await analyticsAPI.exportData(selectedCourseExport || undefined);
      const blob = new Blob([JSON.stringify(res.data, null, 2)], { type: 'application/json' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `study-report-${selectedCourseExport || 'global'}-${new Date().toISOString().split('T')[0]}.json`;
      a.click();
      setShowExportModal(false);
    } catch (err) {
      console.error(err);
    } finally {
      setExporting(false);
    }
  };

  const handleAikaSync = async () => {
    setLoading(true);
    // Simulate AI deep analysis logic
    await new Promise(r => setTimeout(r, 1500));
    window.location.reload();
  };

  if (loading) {
    return (
      <div className="flex min-h-screen bg-background">
        <Sidebar />
        <main className="flex-1 ml-64 p-12 flex items-center justify-center">
          <div className="w-12 h-12 border-4 border-primary/20 border-t-primary rounded-full animate-spin"></div>
        </main>
      </div>
    );
  }

  const engagementScore = data?.average_focus || 0;
  const recentHistory = history?.history || data?.focus_pulse || [];

  return (
    <div className="flex h-screen bg-background overflow-hidden font-sans text-foreground">
      <Sidebar />
      <main className="flex-1 ml-64 p-12 overflow-y-auto space-y-12 animate-fade-in custom-scrollbar">
        
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-8">
          <NavigationHeader 
            title="Study Analytics"
            subtitle="Overall Learning Stats"
          />
          <div className="flex gap-4">
            <button 
              onClick={() => setShowExportModal(true)}
              className="flex items-center gap-3 px-8 py-3 bg-surface-alt border border-border rounded-2xl font-black text-xs text-foreground hover:border-primary/40 hover:text-primary transition-all group h-min"
            >
              <Download size={18} className="group-hover:translate-y-0.5 transition-transform" />
              Download Study Report
            </button>
            <button 
              onClick={handleAikaSync}
              className="bg-primary hover:bg-primary-hover text-white py-3 px-8 text-xs font-black uppercase tracking-widest flex items-center gap-3 rounded-2xl transition-all shadow-lg shadow-primary/20 h-min"
            >
              Aika Sync
            </button>
          </div>
        </div>

        {/* Hero Bento Grid */}
        <div className="grid grid-cols-12 gap-6">
          
          {/* Main Focus Pulse (Bento 8) */}
          <section className="col-span-12 lg:col-span-8 glass-card p-8 flex flex-col h-[500px] hover:border-primary/30 transition-all group relative overflow-hidden">
            <div className="flex items-center justify-between mb-10 relative z-10">
              <div>
                <h3 className="text-2xl font-black text-foreground flex items-center gap-2">
                  <Activity className="text-primary" size={24} /> Focus Graph
                </h3>
                <p className="text-[10px] font-black text-text-muted mt-1 uppercase tracking-widest">How focused you are during lessons</p>
              </div>
              <div className="flex items-center gap-6">
                <div className="text-right">
                  <div className="text-3xl font-black text-foreground">{(engagementScore).toFixed(1)}%</div>
                  <div className="text-[10px] font-black text-primary uppercase tracking-widest">{data?.growth_percent || 0}% Growth</div>
                </div>
              </div>
            </div>
            
            <div className="flex-1 min-h-[200px] mb-6">
              <EngagementWaveform data={(Array.isArray(recentHistory) ? recentHistory : []).map((h: any) => ({ engagement: h.engagement_score || 0 }))} />
            </div>

            <div className="grid grid-cols-4 gap-4 pt-8 border-t border-border">
              {[
                { label: 'Avg Index', value: `${data?.average_focus || 0}%`, icon: Target },
                { label: 'Attention', value: (data?.average_focus || 0) > 70 ? 'High' : 'Moderate', icon: Zap },
                { label: 'Session Time', value: `${data?.active_time_hours || 0}h`, icon: Clock },
                { label: 'Daily Goal', value: `${data?.daily_goal_progress || 0}%`, icon: TrendingUp },
              ].map((stat, i) => (
                <div key={i} className="flex flex-col gap-1">
                  <div className="flex items-center gap-2 text-[10px] font-black text-text-muted uppercase tracking-widest">
                    <stat.icon size={12} className="text-primary" /> {stat.label}
                  </div>
                  <div className="text-xl font-black text-foreground">{stat.value}</div>
                </div>
              ))}
            </div>
          </section>

          {/* ICAP Depth Meter (Bento 4) */}
          <section className="col-span-12 lg:col-span-4 glass-card p-8 flex flex-col items-center justify-between h-[500px] hover:border-primary/30 transition-all">
            <div className="w-full">
              <h3 className="text-2xl font-black text-foreground flex items-center gap-2">
                <Brain className="text-primary" size={24} /> Learning Mode
              </h3>
              <p className="text-[10px] font-black text-text-muted mt-1 uppercase tracking-widest">How you learn best</p>
            </div>

            <div className="relative w-48 h-48 flex items-center justify-center my-8">
              <svg className="w-full h-full transform -rotate-90">
                <circle cx="96" cy="96" r="88" stroke="rgba(255,255,255,0.05)" strokeWidth="12" fill="none" />
                <circle cx="96" cy="96" r="88" stroke="var(--primary)" strokeWidth="12" fill="none" strokeDasharray="552.92" strokeDashoffset={552.92 * (1 - (icapDist?.distribution?.[(icapDist?.dominant || 'constructive').toLowerCase()] || 0) / 100)} strokeLinecap="round" className="drop-shadow-[0_0_8px_var(--primary-glow)]" />
              </svg>
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <div className="text-4xl font-black text-foreground tracking-tighter">{icapDist?.distribution?.[(icapDist?.dominant || 'constructive').toLowerCase()] || 0}%</div>
                <div className="text-[10px] font-black text-primary uppercase tracking-widest">{icapDist?.dominant || 'Constructive'}</div>
              </div>
            </div>

            <div className="w-full space-y-4">
              {[
                { name: 'Interactive', weight: icapDist?.distribution?.interactive || 0 },
                { name: 'Constructive', weight: icapDist?.distribution?.constructive || 0 },
                { name: 'Active', weight: icapDist?.distribution?.active || 0 },
                { name: 'Passive', weight: icapDist?.distribution?.passive || 0 }
              ].map((level, i) => (
                <div key={level.name} className="flex items-center justify-between">
                  <span className="text-xs font-bold text-text-muted uppercase tracking-widest">{level.name}</span>
                  <div className="flex-1 mx-4 h-1 bg-surface-alt rounded-full overflow-hidden border border-border">
                    <div className="h-full bg-primary rounded-full transition-all" style={{ width: `${level.weight}%` }}></div>
                  </div>
                  <span className="text-xs font-black text-foreground">{level.weight}%</span>
                </div>
              ))}
            </div>
          </section>

        </div>

        {/* Learning History */}
        <section className="grid grid-cols-12 gap-8 h-[600px]">
           <div className="col-span-12 lg:col-span-7">
              <NeuralEvidencePanel />
           </div>
           
           <div className="col-span-12 lg:col-span-5 flex flex-col gap-6">
              {/* Aika AI Insight */}
              <div className="glass-card p-10 bg-primary/5 border-primary/20 hover:border-primary/40 transition-all flex flex-col gap-6 flex-1 relative overflow-hidden">
                <Sparkles className="absolute -right-10 -top-10 text-primary/10" size={200} />
                <div className="flex items-center gap-4 relative z-10">
                  <div className="w-12 h-12 rounded-2xl bg-primary flex items-center justify-center text-white crimson-glow">
                    <Bot size={24} />
                  </div>
                  <h4 className="text-xl font-black text-foreground">Sensei's Logic</h4>
                </div>
                <p className="text-sm font-bold text-foreground/80 leading-relaxed relative z-10 italic">
                  "{data?.aika_insight || 'I see a change in your recent study habits. The learning history shows you are staying focused even when you switch tabs.'}"
                </p>
                <div className="mt-auto relative z-10 p-6 bg-background/50 border border-white/5 rounded-3xl">
                   <div className="text-[10px] font-black text-text-muted uppercase tracking-widest mb-2">Confidence Alignment</div>
                   <div className="flex items-center gap-4">
                      <div className="flex-1 h-3 bg-white/5 rounded-full overflow-hidden border border-border">
                         <div className="h-full bg-primary crimson-glow rounded-full transition-all duration-1000" style={{ width: '94%' }}></div>
                      </div>
                      <span className="text-sm font-black text-primary">94%</span>
                   </div>
                </div>
              </div>

               {/* System Signals Card */}
               <div className="glass-card p-10 border-yellow-500/20 hover:border-yellow-500/40 transition-all flex flex-col gap-6 flex-1 shadow-2xl shadow-warning/5">
                <h4 className="text-xl font-black text-foreground flex items-center gap-3">
                  <AlertCircle className="text-warning" size={24} /> Behavioral Signals
                </h4>
                  <div className="space-y-4">
                    <div className="flex items-start gap-4 p-5 bg-warning/5 rounded-3xl border border-warning/10">
                      <div className="w-2 h-2 rounded-full bg-warning mt-2 shadow-[0_0_8px_var(--warning)]"></div>
                      <div className="flex-1">
                        <div className="text-xs font-black text-white uppercase tracking-widest mb-1">Gaze Lapse Pattern</div>
                        <p className="text-[11px] font-bold text-text-muted leading-relaxed">Frequent rapid eye movements detected during Video 2. Aika suggests increasing playback speed for optimal resonance.</p>
                      </div>
                    </div>
                    <div className="flex items-start gap-4 p-5 bg-primary/5 rounded-3xl border border-primary/10">
                      <div className="w-2 h-2 rounded-full bg-primary mt-2 shadow-[0_0_8px_var(--primary)]"></div>
                      <div className="flex-1">
                        <div className="text-xs font-black text-white uppercase tracking-widest mb-1">Engage Forecast</div>
                        <p className="text-[11px] font-bold text-text-muted leading-relaxed">Prediction: Next-Window engagement forecast at 82% (Positive Trend).</p>
                      </div>
                    </div>
                  </div>
              </div>
           </div>
        </section>
      </main>

      {showExportModal && (
         <div className="fixed inset-0 z-[200] flex items-center justify-center p-8 bg-background/80 backdrop-blur-sm animate-fade-in">
           <div className="glass-card w-full max-w-lg p-10 space-y-8 animate-scale-up border-primary/20">
             <div className="flex items-center justify-between">
               <h3 className="text-3xl font-black text-white tracking-tighter">Download Stats</h3>
               <button onClick={() => setShowExportModal(false)} className="text-white/40 hover:text-white"><X /></button>
             </div>
             
             <div className="space-y-4">
               <label className="text-[10px] font-black text-text-muted uppercase tracking-widest">Select Course Scope</label>
               <div className="grid grid-cols-1 gap-3">
                 <button 
                  onClick={() => setSelectedCourseExport('')}
                  className={`p-4 rounded-2xl border text-left flex items-center justify-between transition-all ${selectedCourseExport === '' ? 'bg-primary/20 border-primary shadow-xl shadow-primary/10' : 'bg-surface border-border hover:border-white/20'}`}
                 >
                    <div>
                      <div className="font-black text-white">Global Neural Summary</div>
                      <div className="text-[9px] text-text-muted uppercase font-black tracking-widest">All enrolled nodes</div>
                    </div>
                    {selectedCourseExport === '' && <Check size={20} className="text-primary" />}
                 </button>

                 {myCourses.map(course => (
                    <button 
                      key={course.id}
                      onClick={() => setSelectedCourseExport(course.id)}
                      className={`p-4 rounded-2xl border text-left flex items-center justify-between transition-all ${selectedCourseExport === course.id ? 'bg-primary/20 border-primary shadow-xl shadow-primary/10' : 'bg-surface border-border hover:border-white/20'}`}
                    >
                       <div>
                         <div className="font-black text-white">{course.title}</div>
                         <div className="text-[9px] text-text-muted uppercase font-black tracking-widest">Single Course Report</div>
                       </div>
                       {selectedCourseExport === course.id && <Check size={20} className="text-primary" />}
                    </button>
                 ))}
               </div>
             </div>

             <button 
              onClick={handleExport}
              disabled={exporting}
              className="w-full btn-primary py-4 text-[12px] flex items-center justify-center gap-3 relative overflow-hidden"
             >
                {exporting ? 'Synching Data...' : 'Download Report'}
                {!exporting && <ArrowUpRight size={18} />}
             </button>
           </div>
         </div>
       )}
    </div>
  );
}
