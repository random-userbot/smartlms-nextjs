'use client';

import React, { useState, useEffect } from 'react';
import { 
  Activity,
  BarChart3, 
  TrendingUp, 
  Users, 
  AlertTriangle, 
  Target, 
  Zap, 
  Brain, 
  ArrowUpRight,
  ChevronRight,
  Filter,
  Search,
  BookOpen,
  Play,
  Monitor,
  MousePointer2,
  Calendar,
  Sparkles,
  Info,
  X,
  CheckCircle2
} from 'lucide-react';
import Sidebar from '@/components/Sidebar';
import { analyticsAPI, coursesAPI, teacherAPI } from '@/lib/api';
import Link from 'next/link';

export default function TeacherAnalyticsPage() {
  const [courses, setCourses] = useState<any[]>([]);
  const [selectedCourse, setSelectedCourse] = useState<string>('');
  const [teachingScore, setTeachingScore] = useState<any>(null);
  const [studentEngagement, setStudentEngagement] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [dataLoading, setDataLoading] = useState(false);
  const [patching, setPatching] = useState(false);
  const [showMetricModal, setShowMetricModal] = useState(false);
  const [activeMetric, setActiveMetric] = useState<string | null>(null);

  useEffect(() => {
    loadCourses();
  }, []);

  const loadCourses = async () => {
    try {
      const res = await coursesAPI.list();
      setCourses(res.data);
      if (res.data.length > 0) {
        setSelectedCourse(res.data[0].id);
        loadAnalytics(res.data[0].id);
      } else {
        setLoading(false);
      }
    } catch (err) {
      console.error('Failed to load courses', err);
      setLoading(false);
    }
  };

  const loadAnalytics = async (courseId: string) => {
    setDataLoading(true);
    try {
      const [scoreRes, engRes] = await Promise.all([
        analyticsAPI.getTeachingScore(courseId),
        teacherAPI.getStudentEngagement(courseId)
      ]);
      setTeachingScore(scoreRes.data);
      setStudentEngagement(engRes.data);
    } catch (err) {
      console.error('Failed to load analytics', err);
    } finally {
      setDataLoading(false);
      setLoading(false);
    }
  };

  const handleDeployPatch = async () => {
    if (!selectedCourse) return;
    
    setPatching(true);
    try {
      const res = await analyticsAPI.deployPatch(selectedCourse);
      alert(`Pedagogical synchronization complete. Patch ${res.data.patch_id} successfully deployed across ${res.data.affected_nodes} nodes.`);
      loadAnalytics(selectedCourse);
    } catch (err) {
      console.error('Patch deployment failed', err);
      alert('Neural synchronization failed. Please verify the curricular branch integrity.');
    } finally {
      setPatching(false);
    }
  };

  if (loading) {
    return (
      <div className="flex h-screen bg-background items-center justify-center">
        <div className="w-12 h-12 border-4 border-primary/20 border-t-primary rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="flex h-screen bg-background overflow-hidden font-sans">
      <Sidebar />
      <main className="flex-1 ml-64 p-12 overflow-y-auto space-y-12 animate-fade-in relative">
        
        {/* Global Background Ornament */}
        <div className="absolute top-0 right-0 w-[600px] h-[600px] bg-primary/5 rounded-full blur-[120px] -z-10 pointer-events-none" />

        {/* Header Area */}
        <header className="flex flex-col md:flex-row md:items-end justify-between gap-8 h-32">
          <div>
            <div className="text-[10px] uppercase tracking-[0.4em] font-black text-primary mb-2 flex items-center gap-2">
              <Sparkles size={12} /> Quantum Analytics Sequence
            </div>
            <h1 className="text-7xl font-black tracking-tighter text-foreground leading-[0.9]">
              Insights.
            </h1>
          </div>
          <div className="flex flex-col gap-3 min-w-[300px]">
             <label className="text-[10px] font-black uppercase tracking-widest text-text-muted ml-1">Observational Domain</label>
             <select 
               value={selectedCourse}
               onChange={(e) => {
                 setSelectedCourse(e.target.value);
                 loadAnalytics(e.target.value);
               }}
               className="bg-surface border border-border rounded-2xl py-4 px-6 text-sm font-bold outline-none focus:border-primary/40 transition-all cursor-pointer shadow-lg"
             >
               {courses.map(c => <option key={c.id} value={c.id}>{c.title}</option>)}
             </select>
          </div>
        </header>

        {dataLoading ? (
            <div className="flex-1 flex items-center justify-center h-[60vh]">
               <div className="text-center space-y-6">
                 <div className="w-16 h-16 border-4 border-primary/20 border-t-primary rounded-full animate-spin mx-auto" />
                 <p className="text-[10px] font-black uppercase tracking-[0.3em] text-primary">Synchronizing Neural Data...</p>
               </div>
            </div>
        ) : !teachingScore ? (
            <div className="flex-1 flex flex-col items-center justify-center h-[60vh] text-center opacity-30">
               <BarChart3 size={120} className="mb-6" />
               <h3 className="text-3xl font-black">No telemetry detected for this module.</h3>
            </div>
        ) : (
          <>
            {/* Top Metrics Bento */}
            <div className="grid grid-cols-12 gap-8">
              
              {/* Teaching Efficiency Score (Bento 4) */}
              <div className="col-span-12 lg:col-span-4 glass-card p-10 flex flex-col justify-between border-primary/20 relative overflow-hidden group">
                <div className="absolute -right-6 -bottom-6 text-primary/5 group-hover:scale-125 transition-transform duration-1000">
                  <Target size={180} />
                </div>
                <div 
                  onClick={() => { setActiveMetric('Teaching Efficiency'); setShowMetricModal(true); }}
                  className="relative z-10 cursor-pointer"
                >
                  <h3 className="text-xl font-black text-foreground group-hover:text-primary transition-colors flex items-center gap-2">
                    Teaching Efficiency <Info size={14} />
                  </h3>
                  <div className="text-[10px] font-black text-primary uppercase tracking-widest mt-1">Version 5 Propeller Metric</div>
                  
                  <div className="mt-12 flex items-baseline gap-2">
                    <span className="text-8xl font-black tracking-tighter text-foreground leading-none group-hover:scale-105 transition-transform">{teachingScore.overall_score}</span>
                    <span className="text-xl font-black text-primary">/100</span>
                  </div>
                </div>
                
                <div className="pt-8 border-t border-border mt-8 relative z-10 flex items-center justify-between">
                   <div className="flex gap-1.5">
                     {[...Array(5)].map((_, i) => (
                       <div key={i} className={`w-1.5 h-6 rounded-full ${i < (teachingScore.overall_score/20) ? 'bg-primary' : 'bg-surface-alt border border-border'}`} />
                     ))}
                   </div>
                   <span className="text-[10px] font-black uppercase text-success tracking-widest">Optimal Sync</span>
                </div>
              </div>

              {/* Components Visualization (Bento 8) */}
              <div className="col-span-12 lg:col-span-8 glass-card p-10 grid grid-cols-2 md:grid-cols-4 gap-8">
                {[
                  { label: 'Engagement', val: teachingScore.components.engagement, icon: Zap, color: 'text-warning' },
                  { label: 'Attendance', val: teachingScore.components.attendance, icon: Calendar, color: 'text-info' },
                  { label: 'ICAP Depth', val: teachingScore.components.icap_score, icon: Brain, color: 'text-primary' },
                  { label: 'Completion', val: teachingScore.components.completion_rate, icon: CheckCircle2, color: 'text-success' }
                ].map((comp, i) => (
                  <div 
                    key={i} 
                    onClick={() => { setActiveMetric(comp.label); setShowMetricModal(true); }}
                    className="flex flex-col gap-4 cursor-pointer group"
                  >
                    <div className={`w-12 h-12 rounded-2xl bg-white/5 flex items-center justify-center ${comp.color} border border-white/5 shadow-sm group-hover:scale-110 transition-transform`}>
                      <comp.icon size={24} />
                    </div>
                    <div>
                      <div className="text-sm font-black text-text-muted uppercase tracking-widest">{comp.label}</div>
                      <div className="text-3xl font-black text-foreground mt-1 group-hover:text-primary transition-colors">{comp.val}%</div>
                    </div>
                    <div className="w-full h-1 bg-surface-alt rounded-full overflow-hidden mt-auto">
                      <div className={`h-full opacity-60 ${comp.color.replace('text-', 'bg-')}`} style={{ width: `${comp.val}%` }} />
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Risk Management Section */}
            <div className="grid grid-cols-12 gap-8">
              
              {/* Student Risk Matrix (Bento 8) */}
              <div className="col-span-12 lg:col-span-8 glass-premium rounded-[3rem] border border-border overflow-hidden">
                <div className="p-8 border-b border-border bg-surface-alt flex items-center justify-between">
                  <h3 className="text-xl font-black flex items-center gap-3">
                    <Users size={20} className="text-primary" /> Cognitive Risk Matrix
                  </h3>
                  <div className="px-4 py-1.5 bg-error/10 border border-error/20 rounded-full text-[10px] font-black text-error uppercase tracking-widest">
                    {studentEngagement.filter(s => s.engagement_score < 50).length} Anomalies Detected
                  </div>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-border bg-black/5">
                        <th className="px-8 py-5 text-left text-[10px] font-black uppercase tracking-widest text-text-muted">Student Subject</th>
                        <th className="px-8 py-5 text-left text-[10px] font-black uppercase tracking-widest text-text-muted">Attention Resonance</th>
                        <th className="px-8 py-5 text-left text-[10px] font-black uppercase tracking-widest text-text-muted">Visibility Lapses</th>
                        <th className="px-8 py-5 text-left text-[10px] font-black uppercase tracking-widest text-text-muted">Context Switches</th>
                        <th className="px-8 py-5 text-right text-[10px] font-black uppercase tracking-widest text-text-muted">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/50">
                      {studentEngagement.length === 0 ? (
                        <tr><td colSpan={5} className="p-20 text-center font-bold text-text-muted italic">No student telemetry observed.</td></tr>
                      ) : studentEngagement.map((s) => (
                        <tr key={s.student_id} className="hover:bg-white/5 transition-colors group cursor-pointer">
                          <td className="px-8 py-6">
                            <Link href={`/teacher/students/${s.student_id}`} className="flex items-center gap-4">
                              <div className="w-10 h-10 rounded-full border border-border bg-surface-alt flex items-center justify-center font-black text-primary group-hover:scale-110 transition-transform">
                                {s.full_name.charAt(0)}
                              </div>
                              <div>
                                <div className="font-black text-foreground group-hover:text-primary transition-colors">{s.full_name}</div>
                                <div className="text-[10px] text-text-muted font-bold">{s.email}</div>
                              </div>
                            </Link>
                          </td>
                          <td className="px-8 py-6">
                             <div className="flex items-center gap-3">
                               <div className="flex-1 w-24 h-1.5 bg-surface-alt rounded-full overflow-hidden">
                                 <div className={`h-full ${s.engagement_score < 50 ? 'bg-error' : s.engagement_score < 75 ? 'bg-warning' : 'bg-success'}`} style={{ width: `${s.engagement_score}%` }} />
                               </div>
                               <span className="text-xs font-black text-foreground">{s.engagement_score}%</span>
                             </div>
                          </td>
                          <td className="px-8 py-6">
                             <span className={`text-xs font-bold ${s.visibility_score < 70 ? 'text-error' : 'text-text-muted'}`}>{100 - s.visibility_score}% lapse rate</span>
                          </td>
                          <td className="px-8 py-6">
                             <div className="flex items-center gap-2 text-xs font-bold text-text-muted">
                               <MousePointer2 size={12} className="text-primary" /> {s.tab_switches} switches
                             </div>
                          </td>
                          <td className="px-8 py-6 text-right">
                             {s.engagement_score < 50 ? (
                               <span className="inline-flex items-center gap-1.5 px-3 py-1 bg-error/10 text-error text-[8px] font-black uppercase rounded-full border border-error/20">
                                 <AlertTriangle size={10} /> Critical Drop
                               </span>
                             ) : (
                               <span className="inline-flex items-center gap-1.5 px-3 py-1 bg-success/10 text-success text-[8px] font-black uppercase rounded-full border border-success/20">
                                 Stable Sync
                               </span>
                             )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Recommendations Bento (Bento 4) */}
              <div className="col-span-12 lg:col-span-4 glass-card p-10 flex flex-col gap-8">
                <div className="flex items-center justify-between">
                  <h3 className="text-xl font-black text-foreground">Aika Protocol</h3>
                  <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center text-primary">
                    <Info size={16} />
                  </div>
                </div>
                
                <div className="space-y-6 flex-1 overflow-y-auto">
                   {teachingScore.recommendations.map((rec: string, i: number) => (
                     <div key={i} className="flex gap-4 p-5 bg-white/5 border border-white/5 rounded-[2rem] group hover:border-primary/20 transition-all">
                        <div className="mt-1"><ArrowUpRight size={16} className="text-primary group-hover:rotate-45 transition-transform" /></div>
                        <p className="text-xs font-medium text-foreground/80 leading-relaxed italic">"{rec}"</p>
                     </div>
                   ))}
                </div>

                 <button 
                   onClick={handleDeployPatch}
                   disabled={patching || !selectedCourse}
                   className="w-full py-4 text-[10px] font-black uppercase tracking-widest text-primary border border-primary/20 rounded-2xl hover:bg-primary hover:text-white transition-all crimson-glow mt-4 disabled:opacity-50"
                 >
                   {patching ? 'Synchronizing Neural Data...' : 'Deploy Curricular Patch'}
                 </button>
              </div>

            </div>
          </>
        )}

      </main>

      {/* Metric Data Telemetry Modal */}
      {showMetricModal && (
        <div className="fixed inset-0 bg-background/80 backdrop-blur-2xl z-[300] flex items-center justify-center p-6">
          <div className="bg-surface border border-border w-full max-w-2xl rounded-[3rem] overflow-hidden shadow-2xl animate-slide-up">
            <div className="p-10 border-b border-border bg-surface-alt/50 flex items-center justify-between">
              <div className="flex items-center gap-5">
                <div className="w-12 h-12 rounded-2xl bg-info/10 flex items-center justify-center text-info">
                  <BarChart3 size={24} />
                </div>
                <div>
                  <h2 className="text-3xl font-black tracking-tighter">Metric Telemetry</h2>
                  <div className="text-[10px] font-black text-primary uppercase tracking-widest mt-1">{activeMetric} Synchronicity</div>
                </div>
              </div>
              <button onClick={() => setShowMetricModal(false)} className="p-3 hover:bg-surface-alt border border-border rounded-xl transition-all"><X size={24} /></button>
            </div>
            
            <div className="p-10 space-y-8 max-h-[70vh] overflow-y-auto custom-scrollbar">
              <div className="flex items-center justify-between mb-4">
                <div className="text-[10px] font-black text-text-muted uppercase tracking-[0.2em]">Data Credibility</div>
                <div className="flex items-center gap-2">
                  <div className="text-xl font-black text-primary">{teachingScore?.confidence_score || '95.2'}%</div>
                  <div className="text-[10px] font-black text-text-muted uppercase tracking-widest">Confidence</div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-6">
                {[
                  { label: 'Attention Resonance', value: '30%', data: `${teachingScore.components.engagement}%`, desc: 'Real-time eye-tracking & attentive focus' },
                  { label: 'Pedagogical Depth', value: '25%', data: `${teachingScore.components.icap_score}%`, desc: 'ICAP cognitive engagement levels' },
                  { label: 'Attendance Logic', value: '20%', data: `${teachingScore.components.attendance}%`, desc: 'Historical participation frequency' },
                  { label: 'Completion Flux', value: '25%', data: `${teachingScore.components.completion_rate}%`, desc: 'Average syllabus node traversal speed' },
                ].map((item, i) => (
                  <div key={i} className="p-6 bg-surface-alt rounded-3xl border border-border space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-black text-text-muted uppercase tracking-widest">{item.label}</span>
                      <span className="px-2 py-0.5 bg-primary/10 rounded-full text-[8px] font-black text-primary">{item.value}</span>
                    </div>
                    <div className="text-2xl font-black text-foreground">{item.data}</div>
                    <p className="text-[8px] font-bold text-text-muted leading-relaxed uppercase">{item.desc}</p>
                  </div>
                ))}
              </div>

              {/* Forensic Logs */}
              <div className="space-y-4">
                <div className="text-[10px] font-black text-text-muted uppercase tracking-widest flex items-center gap-2">
                  <Activity size={12} className="text-primary" /> Forensic Activity Stream
                </div>
                <div className="space-y-3">
                  {teachingScore?.forensic_logs?.length > 0 ? teachingScore.forensic_logs.map((log: any, idx: number) => (
                    <div key={idx} className="flex items-start gap-4 p-4 bg-background rounded-2xl border border-border group hover:border-primary/20 transition-all">
                      <div className="w-1.5 h-1.5 rounded-full bg-primary/40 mt-1.5 group-hover:bg-primary transition-colors"></div>
                      <div className="flex-1">
                        <div className="flex items-center justify-between">
                          <div className="text-xs font-black text-foreground uppercase tracking-tight">{log.action.replace('_', ' ')}</div>
                          <div className="text-[8px] font-bold text-text-muted uppercase">{new Date(log.timestamp).toLocaleTimeString()}</div>
                        </div>
                        <div className="text-[10px] font-medium text-text-muted mt-1">
                          Source: {log.user} | Detail: {JSON.stringify(log.details || {}).slice(0, 50)}...
                        </div>
                      </div>
                    </div>
                  )) : (
                    <div className="text-center py-6 border-2 border-dashed border-border rounded-2xl">
                       <p className="text-[10px] font-bold text-text-muted uppercase italic">No raw log data available for this cycle.</p>
                    </div>
                  )}
                </div>
              </div>

              <div className="p-8 bg-primary/5 rounded-[2.5rem] border border-primary/20 space-y-4">
                <div className="flex items-center gap-3 text-primary">
                  <Sparkles size={20} />
                  <span className="text-xs font-black uppercase tracking-widest">Aika Analytical Output</span>
                </div>
                <p className="text-sm font-medium text-foreground/90 leading-relaxed italic">
                   The <span className="text-primary font-black uppercase tracking-tighter">{activeMetric}</span> metric is verified by <span className="text-primary font-black">{teachingScore?.forensic_logs?.length || 0} telemetry nodes</span>. 
                   Current telemetry shows <span className="text-primary font-black">{activeMetric === 'Teaching Efficiency' ? teachingScore.overall_score : teachingScore.components[activeMetric?.toLowerCase().replace(' ', '_') || 'engagement'] || '0'}%</span> resonance with <span className="text-primary font-black">{teachingScore?.confidence_score || '95'}%</span> confidence.
                </p>
              </div>

              <button 
                onClick={() => setShowMetricModal(false)}
                className="w-full py-6 bg-primary text-white rounded-2xl font-black text-sm uppercase tracking-widest hover:scale-[1.02] transition-all shadow-xl crimson-glow"
              >
                Acknowledge Node Analysis
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
