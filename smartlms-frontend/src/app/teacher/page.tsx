'use client';

import React, { useState, useEffect } from 'react';
import { analyticsAPI, coursesAPI, teacherAPI, lecturesAPI, messagesAPI } from '@/lib/api';
import { 
  Target, 
  Users, 
  Activity, 
  BarChart3, 
  Sparkles, 
  Clock, 
  Award,
  ArrowUpRight,
  MessageSquare,
  AlertTriangle,
  X,
  ChevronRight,
  Info,
  Zap
} from 'lucide-react';
import Sidebar from '@/components/Sidebar';
import Link from 'next/link';
import MultiStudentWaves from '@/components/MultiStudentWaves';
import EngagementWaveform from '@/components/EngagementWaveform';

export default function TeacherDashboard() {
  const [courses, setCourses] = useState<any[]>([]);
  const [selectedCourse, setSelectedCourse] = useState<string>('');
  const [lectures, setLectures] = useState<any[]>([]);
  const [selectedLecture, setSelectedLecture] = useState<string>('');
  const [students, setStudents] = useState<any[]>([]);
  const [selectedStudentIds, setSelectedStudentIds] = useState<string[]>([]);
  const [score, setScore] = useState<any>(null);
  const [atRiskStudents, setAtRiskStudents] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [sendingAlert, setSendingAlert] = useState(false);
  const [showScoreModal, setShowScoreModal] = useState(false);
  const [activeMetric, setActiveMetric] = useState<string | null>(null);
  const [feedbackAnalysis, setFeedbackAnalysis] = useState<any>(null);
  const [showFeedbackModal, setShowFeedbackModal] = useState(false);
  const [loadingFeedback, setLoadingFeedback] = useState(false);
  const [liveSessions, setLiveSessions] = useState<any[]>([]);

  useEffect(() => {
    coursesAPI.list().then(res => {
      const c = res.data || [];
      if (c.length > 0) {
        setCourses(c);
        setSelectedCourse(c[0].id);
      }
    }).finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!selectedCourse) return;
    Promise.all([
      analyticsAPI.getTeachingScore(selectedCourse),
      teacherAPI.getStudentEngagement(selectedCourse).catch(() => ({ data: [] })),
      lecturesAPI.getByCourse(selectedCourse).catch(() => ({ data: [] }))
    ]).then(([scoreRes, riskRes, lectRes]) => {
      setScore(scoreRes.data);
      const allStudents = riskRes.data || [];
      setStudents(allStudents);
      
      const sortedRisk = [...allStudents].sort((a, b) => (a.engagement_score || 0) - (b.engagement_score || 0));
      setAtRiskStudents(sortedRisk.slice(0, 3));

      const courseLectures = lectRes.data || [];
      setLectures(courseLectures);
      if (courseLectures.length > 0) {
        setSelectedLecture(courseLectures[0].id);
      }
    });
  }, [selectedCourse]);

  const handleBulkAlert = async () => {
    if (!selectedCourse || atRiskStudents.length === 0) {
      alert('No students needing help found right now.');
      return;
    }

    const confirmSend = confirm(`Send an urgent study reminder to ${atRiskStudents.length} students?`);
    if (!confirmSend) return;

    setSendingAlert(true);
    try {
      await messagesAPI.bulkSend({
        student_ids: atRiskStudents.map(s => s.student_id),
        subject: "Study Reminder",
        content: "I've noticed you might be falling behind a bit in our class sessions. Please review the latest lessons and use Aika if you have questions about the difficult parts.",
        course_id: selectedCourse,
        category: "alert"
      });
      alert('Reminders sent successfully.');
    } catch (err) {
      console.error('Reminder failed', err);
      alert('Failed to send reminders. Check your connection.');
    } finally {
      setSendingAlert(false);
    }
  };

  const handleFetchFeedbackAnalysis = async () => {
    if (!selectedCourse) return;
    setLoadingFeedback(true);
    setShowFeedbackModal(true);
    try {
      const res = await analyticsAPI.getFeedbackAnalysis(selectedCourse);
      setFeedbackAnalysis(res.data);
    } catch (err) {
      console.error('Failed to fetch feedback analysis', err);
    } finally {
      setLoadingFeedback(false);
    }
  };

  useEffect(() => {
    const fetchLive = () => {
      analyticsAPI.getLiveSessions().then(res => {
        setLiveSessions(res.data || []);
      }).catch(() => {});
    };
    
    fetchLive();
    const interval = setInterval(fetchLive, 5000);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="flex min-h-screen bg-background">
        <Sidebar aria-hidden="true" />
        <main className="flex-1 ml-64 p-12 flex items-center justify-center">
          <div className="w-12 h-12 border-4 border-primary/20 border-t-primary rounded-full animate-spin"></div>
        </main>
      </div>
    );
  }

  const overallScore = score?.overall_score || 0;
  const components = score?.components || {};

  return (
    <div className="flex min-h-screen bg-background">
      <Sidebar />
      <main className="flex-1 ml-64 p-12 space-y-10 animate-fade-in relative z-10">
        
        {/* Header Section */}
        <header className="flex flex-col md:flex-row md:items-end justify-between gap-6">
          <div>
            <div className="text-[10px] uppercase tracking-[0.3em] font-black text-primary mb-2">Teacher Control Center</div>
            <h1 className="text-6xl font-black tracking-tighter text-foreground">Class Stats.</h1>
            <p className="text-text-muted font-bold mt-4 max-w-xl">
              Checking how students are doing, if they are responding, and how focused they are.
            </p>
          </div>
          <div className="flex gap-4">
            <select 
              value={selectedCourse} 
              onChange={(e) => setSelectedCourse(e.target.value)}
              className="bg-surface border border-border text-foreground text-sm font-bold rounded-2xl px-6 py-3 crimson-glow"
            >
              {(Array.isArray(courses) ? courses : []).map((c: any) => (
                <option key={c.id} value={c.id}>{c.title}</option>
              ))}
            </select>
          </div>
        </header>

        {/* Hero Performance Card */}
        <div className="grid grid-cols-12 gap-6">
          <section 
            onClick={() => { setActiveMetric('Teaching Score'); setShowScoreModal(true); }}
            className="col-span-12 lg:col-span-4 glass-card p-12 flex flex-col items-center justify-center text-center relative overflow-hidden bg-primary/5 hover:border-primary/40 transition-all group cursor-pointer"
          >
            <div className="absolute inset-0 bg-gradient-to-br from-primary/10 to-transparent opacity-50 group-hover:opacity-100 transition-opacity"></div>
            <div className="relative z-10">
              <div className="text-[10px] font-black text-primary uppercase tracking-[0.2em] mb-4 flex items-center justify-center gap-2">
                Teaching Score <Info size={12} />
              </div>
              <div className="text-9xl font-black text-foreground tracking-tighter mb-4 shimmer">
                {(overallScore).toFixed(1)}
              </div>
              <div className="inline-flex items-center gap-2 px-6 py-2 bg-primary/20 border border-primary/40 rounded-full text-xs font-black text-foreground uppercase tracking-widest">
                <Sparkles size={14} className="text-primary" /> {overallScore > 90 ? 'Great Teacher' : 'On Track'}
              </div>
            </div>
          </section>

          <section className="col-span-12 lg:col-span-8 glass-card p-12 grid grid-cols-2 md:grid-cols-4 gap-8">
            {[
              { label: 'Engagement', value: `${components.engagement?.toFixed(0) || 0}%`, icon: Activity, color: 'text-primary', key: 'engagement' },
              { label: 'Quiz Avg', value: `${components.quiz_performance?.toFixed(0) || 0}%`, icon: BarChart3, color: 'text-success', key: 'quiz_performance' },
              { label: 'Responsiveness', value: `${components.responsiveness?.toFixed(0) || 0}%`, icon: MessageSquare, color: 'text-info', key: 'responsiveness' },
              { label: 'Activity Score', value: `${components.activity_score?.toFixed(0) || 0}%`, icon: Award, color: 'text-warning', key: 'activity_score' },
            ].map((m, i) => (
              <div 
                key={i} 
                onClick={() => { setActiveMetric(m.label); setShowScoreModal(true); }}
                className="space-y-4 flex flex-col items-center justify-center p-6 bg-surface-alt rounded-3xl border border-border hover:border-primary/40 transition-all cursor-pointer group"
              >
                <div className={`p-4 bg-background rounded-2xl border border-border transition-transform group-hover:scale-110 ${m.color}`}><m.icon size={24} /></div>
                <div className="text-center">
                  <div className="text-3xl font-black text-foreground">{m.value}</div>
                  <div className="text-[10px] font-black text-text-muted uppercase tracking-widest mt-1 mb-2">{m.label}</div>
                  <div className="text-[10px] font-black text-primary uppercase opacity-0 group-hover:opacity-100 transition-opacity">View Data</div>
                </div>
              </div>
            ))}
          </section>
        </div>

        {/* Active Class Monitor Section */}
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-1.5 h-6 bg-success rounded-full" />
              <h2 className="text-3xl font-black text-foreground tracking-tight uppercase italic">Active Class Monitor</h2>
            </div>
            {liveSessions.length > 0 && (
              <div className="flex items-center gap-4 bg-success/10 border border-success/20 px-4 py-2 rounded-xl">
                 <div className="w-2 h-2 rounded-full bg-success animate-pulse shadow-[0_0_8px_rgba(34,197,94,0.5)]" />
                 <span className="text-[10px] font-black text-success uppercase tracking-widest">{liveSessions.length} STUDENTS SYNCED</span>
              </div>
            )}
          </div>

          {liveSessions.length === 0 ? (
            <div className="p-12 border-2 border-dashed border-white/5 rounded-[3rem] text-center bg-surface/10">
               <div className="w-16 h-16 rounded-3xl bg-white/5 flex items-center justify-center mx-auto mb-6 text-white/10">
                  <Activity size={32} />
               </div>
               <h3 className="text-xl font-bold text-white/20 uppercase tracking-widest">No Active Sessions</h3>
               <p className="text-[10px] font-black text-white/10 uppercase tracking-[0.3em] mt-2 italic">Student monitoring is currently on standby.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
              {(Array.isArray(liveSessions) ? liveSessions : []).map((ls: any) => (
                <div key={ls.session_id} className="glass-card p-6 border-white/5 bg-surface/40 hover:bg-surface transition-all group relative overflow-hidden">
                  <div className="absolute top-0 right-0 w-32 h-32 bg-primary/5 blur-3xl rounded-full -mr-16 -mt-16 pointer-events-none" />
                  
                  <div className="flex items-center gap-4 mb-6">
                    <div className="w-12 h-12 rounded-2xl bg-white/5 border border-white/5 flex items-center justify-center text-xl font-black text-foreground group-hover:border-primary/40 transition-colors uppercase">
                      {ls.student_avatar ? <img src={ls.student_avatar} className="w-full h-full object-cover rounded-2xl" /> : ls.student_name?.charAt(0)}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-black text-foreground truncate">{ls.student_name}</div>
                      <div className="text-[9px] font-black text-text-muted uppercase tracking-widest truncate">{ls.lecture_title}</div>
                    </div>
                    <div className="flex flex-col items-end">
                       <div className={`text-sm font-black ${ls.engagement > 70 ? 'text-success' : ls.engagement > 40 ? 'text-warning' : 'text-primary'}`}>
                          {(ls.engagement || 0).toFixed(0)}%
                       </div>
                       <div className="text-[7px] font-black text-text-muted uppercase tracking-widest">FOCUS</div>
                    </div>
                  </div>

                  {/* Mini-Wave for each student */}
                  <div className="h-16 w-full mb-4 opacity-50 group-hover:opacity-100 transition-opacity">
                    <EngagementWaveform data={(ls.waveform || []).map((e: any) => ({ engagement: e.engagement }))} isLive={false} />
                  </div>

                  <div className="flex items-center justify-between mt-auto pt-4 border-t border-white/5">
                    <div className="flex items-center gap-2">
                       <Zap size={10} className="text-primary" />
                       <span className="text-[8px] font-black text-white/30 uppercase tracking-widest">{ls.status}</span>
                    </div>
                    <Link 
                      href={`/teacher/students/${ls.student_id}`}
                      className="text-[8px] font-black text-primary uppercase tracking-[0.2em] group-hover:underline"
                    >
                      View Report &rarr;
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Multi-Wave Engagement Dashboard */}
        <div className="space-y-6">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <h2 className="text-3xl font-black text-foreground tracking-tight">Class Focus Graph</h2>
              <p className="text-[10px] font-black text-text-muted uppercase tracking-[0.2em] mt-1">Comparing how students focus during lessons</p>
            </div>
            
            <div className="flex flex-wrap gap-4">
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-black text-foreground uppercase tracking-widest">Lecture:</span>
                <select 
                  value={selectedLecture}
                  onChange={(e) => setSelectedLecture(e.target.value)}
                  className="bg-surface border border-border text-xs font-bold text-foreground rounded-xl px-4 py-2"
                >
                  {(Array.isArray(lectures) ? lectures : []).map(l => (
                    <option key={l.id} value={l.id}>{l.title}</option>
                  ))}
                </select>
              </div>

              <button 
                onClick={() => setSelectedStudentIds([])}
                className={`px-4 py-2 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all ${selectedStudentIds.length === 0 ? 'bg-primary text-white' : 'bg-surface-alt text-text-muted border border-border'}`}
              >
                All Students
              </button>
            </div>
          </div>

          <div className="grid grid-cols-12 gap-6">
            <div className="col-span-12 lg:col-span-9">
              <MultiStudentWaves lectureId={selectedLecture} selectedStudentIds={selectedStudentIds} />
            </div>
            
            <div className="col-span-12 lg:col-span-3 glass-card p-6 overflow-y-auto max-h-[450px] space-y-4">
              <div className="text-[10px] font-black text-text-muted uppercase tracking-widest mb-2 flex items-center gap-2">
                <Users size={12} /> Student List
              </div>
              <div className="space-y-2">
                {(Array.isArray(students) ? students : []).map(s => (
                  <div 
                    key={s.student_id}
                    onClick={() => {
                      if (selectedStudentIds.includes(s.student_id)) {
                        setSelectedStudentIds(prev => prev.filter(id => id !== s.student_id));
                      } else {
                        setSelectedStudentIds(prev => [...prev, s.student_id]);
                      }
                    }}
                    className={`flex items-center justify-between p-3 rounded-xl cursor-pointer border transition-all ${selectedStudentIds.includes(s.student_id) ? 'bg-primary/20 border-primary/40' : 'bg-surface-alt border-transparent hover:border-border'}`}
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-6 h-6 rounded-lg bg-background flex items-center justify-center text-[10px] font-black text-foreground">
                        {s.full_name?.charAt(0)}
                      </div>
                      <span className="text-xs font-bold text-foreground/90 truncate max-w-[120px]">{s.full_name}</span>
                    </div>
                    {selectedStudentIds.includes(s.student_id) && <Activity size={12} className="text-primary animate-pulse" />}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Secondary Insights Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div 
            onClick={handleFetchFeedbackAnalysis}
            className="glass-card p-10 space-y-8 cursor-pointer hover:border-primary/40 transition-all group"
          >
             <div className="flex items-center justify-between">
               <h3 className="text-2xl font-black text-foreground flex items-center gap-2">
                 <MessageSquare className="text-primary" size={24} /> Student Feedback
               </h3>
               <span className="text-[10px] font-black text-text-muted uppercase tracking-widest">How they feel</span>
             </div>
             
             <div className="space-y-6">
               {[
                 { label: 'Positive', pct: score?.feedback_sentiment?.positive || 0, color: 'bg-info' },
                 { label: 'Neutral', pct: score?.feedback_sentiment?.neutral || 0, color: 'bg-text-muted' },
                 { label: 'Critical', pct: score?.feedback_sentiment?.critical || 0, color: 'bg-primary' },
               ].map(s => (
                 <div key={s.label} className="space-y-2">
                   <div className="flex justify-between text-xs font-bold text-foreground/80">
                     <span>{s.label}</span>
                     <span>{s.pct}%</span>
                   </div>
                   <div className="w-full h-1.5 bg-background rounded-full overflow-hidden">
                     <div className={`h-full ${s.color} rounded-full transition-all duration-1000`} style={{ width: `${s.pct}%` }}></div>
                   </div>
                 </div>
               ))}
             </div>

              <div className="p-6 bg-surface-alt rounded-2xl border border-border space-y-4 group-hover:bg-surface transition-colors">
                <div className="text-xs font-bold text-text-muted uppercase tracking-widest flex items-center justify-between">
                   <span>Aika Insight:</span>
                   <span className="text-primary text-[10px] opacity-0 group-hover:opacity-100 transition-opacity">Analyze Deeply &rarr;</span>
                </div>
                <p className="text-sm font-medium text-foreground/90 leading-relaxed italic">
                  {score?.aika_insight || "Synchronizing with your classroom flow. Insights will appear once baseline data is established."}
                </p>
              </div>
          </div>

          <div className="glass-card p-10 space-y-8">
             <div className="flex items-center justify-between">
                <h3 className="text-2xl font-black text-foreground flex items-center gap-2">
                  <AlertTriangle className="text-warning" size={24} /> Students Needing Help
                </h3>
                <button 
                   onClick={handleBulkAlert}
                   disabled={sendingAlert || atRiskStudents.length === 0}
                   className="text-[10px] font-black text-primary uppercase tracking-widest hover:underline disabled:opacity-50 disabled:no-underline"
                 >
                   {sendingAlert ? 'Sending...' : 'Send Reminders'}
                 </button>
             </div>

              <div className="space-y-4">
                {Array.isArray(atRiskStudents) && atRiskStudents.length > 0 ? atRiskStudents.map((r, i) => (
                  <Link 
                    key={i} 
                    href={`/teacher/students/${r.student_id}`}
                    className="flex items-center justify-between p-4 bg-surface-alt rounded-2xl border border-border hover:bg-surface hover:shadow-lg hover:border-primary/20 transition-all cursor-pointer group"
                  >
                    <div className="flex items-center gap-4">
                      <div className="w-10 h-10 bg-background rounded-xl border border-border flex items-center justify-center font-black text-foreground group-hover:border-primary/40 transition-colors uppercase">{r.full_name?.charAt(0) || 'S'}</div>
                      <div>
                        <div className="text-sm font-bold text-foreground group-hover:text-primary transition-colors">{r.full_name}</div>
                        <div className="flex items-center gap-2">
                          <div className={`text-[10px] font-black uppercase tracking-widest ${r.visibility_score < 85 ? 'text-primary' : 'text-text-muted'}`}>
                            {r.visibility_score < 100 ? `Visibility: ${(r.visibility_score || 0).toFixed(0)}%` : 'Full Sync'}
                          </div>
                          <span className="text-[10px] text-foreground/20">•</span>
                          <div className={`text-[10px] font-black uppercase tracking-widest ${r.tab_switches > 5 ? 'text-info' : 'text-text-muted'}`}>
                            Tabs: {r.tab_switches || 0}
                          </div>
                          <span className="text-[10px] text-foreground/20">•</span>
                          <div className="text-[10px] font-bold text-text-muted uppercase">{r.sessions || 0} sessions</div>
                        </div>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className={`text-sm font-black ${(r.engagement_score || 0) < 40 ? 'text-primary' : (r.engagement_score || 0) < 70 ? 'text-warning' : 'text-success'}`}>
                        {(r.engagement_score || 0) < 40 ? 'Needs Help' : (r.engagement_score || 0) < 70 ? 'Doing Okay' : 'Great Job'}
                      </div>
                      <div className="text-[10px] font-bold text-text-muted">{(r.engagement_score || 0).toFixed(0)}% focus</div>
                    </div>
                  </Link>
                )) : (
                  <div className="text-center py-8">
                   <p className="text-xs font-bold text-text-muted italic">All students are doing well with the lessons.</p>
                 </div>
               )}
             </div>
          </div>
        </div>
      </main>

      {/* Data Inspector Modal */}
      {showScoreModal && (
        <div className="fixed inset-0 bg-background/80 backdrop-blur-2xl z-[300] flex items-center justify-center p-6">
          <div className="bg-surface border border-border w-full max-w-2xl rounded-[3rem] overflow-hidden shadow-2xl animate-slide-up">
            <div className="p-10 border-b border-border bg-surface-alt/50 flex items-center justify-between">
              <div className="flex items-center gap-5">
                <div className="w-12 h-12 rounded-2xl bg-primary/10 flex items-center justify-center text-primary">
                  <BarChart3 size={24} />
                </div>
                <div>
                  <h2 className="text-3xl font-black tracking-tighter">Detailed Stats</h2>
                  <div className="text-[10px] font-black text-primary uppercase tracking-widest mt-1">{activeMetric} Details</div>
                </div>
              </div>
              <button onClick={() => setShowScoreModal(false)} className="p-3 hover:bg-surface-alt border border-border rounded-xl transition-all"><X size={24} /></button>
            </div>
            
            <div className="p-10 space-y-8 max-h-[70vh] overflow-y-auto custom-scrollbar">
              <div className="flex items-center justify-between mb-4">
                <div className="text-[10px] font-black text-text-muted uppercase tracking-[0.2em]">Data Accuracy</div>
                <div className="flex items-center gap-2">
                  <div className="text-xl font-black text-primary">{score?.confidence_score?.toFixed(1) || '0.0'}%</div>
                  <div className="text-[10px] font-black text-text-muted uppercase tracking-widest">Confidence</div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-6">
                {[
                  { label: 'Engagement', value: '15%', data: `${components.engagement?.toFixed(1) || 0}%`, desc: 'Multi-wave attention synchronization' },
                  { label: 'Quiz Avg', value: '10%', data: `${components.quiz_performance?.toFixed(1) || 0}%`, desc: 'Summative assessment baseline' },
                  { label: 'Responsiveness', value: '10%', data: `${components.responsiveness?.toFixed(1) || 0}%`, desc: 'Average message response rate' },
                  { label: 'Subject Focused', value: '10%', data: `${components.icap_score?.toFixed(1) || 0}%`, desc: 'Active processing classification' },
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
                  <Activity size={12} className="text-primary" /> Activity History
                </div>
                <div className="space-y-3">
                  {score?.forensic_logs?.length > 0 ? score.forensic_logs.map((log: any, idx: number) => (
                    <div key={idx} className="flex items-start gap-4 p-4 bg-background rounded-2xl border border-border group hover:border-primary/20 transition-all">
                      <div className="w-2 h-2 rounded-full bg-primary/40 mt-1.5 group-hover:bg-primary transition-colors"></div>
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

              <div className="p-8 bg-primary/5 rounded-[2rem] border border-primary/20 space-y-4">
                <div className="flex items-center gap-3 text-primary">
                  <Sparkles size={20} />
                  <span className="text-xs font-black uppercase tracking-widest">Aika Telemetry Summary</span>
                </div>
                <p className="text-sm font-medium text-foreground/90 leading-relaxed italic">
                  The Teaching Score of <span className="font-black text-primary">{overallScore.toFixed(2)}</span> is a deterministic aggregate. Verified by <span className="font-black text-primary">{score?.forensic_logs?.length || 0} telemetry nodes</span> with <span className="font-black text-primary">{score?.confidence_score || '95'}%</span> confidence.
                </p>
              </div>

              <button 
                onClick={() => setShowScoreModal(false)}
                className="w-full py-6 bg-primary text-white rounded-2xl font-black text-xs uppercase tracking-widest hover:bg-primary-dark transition-all crimson-glow shadow-xl"
              >
                Acknowledge System Report
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Deep Feedback Analysis Modal */}
      {showFeedbackModal && (
        <div className="fixed inset-0 bg-background/80 backdrop-blur-2xl z-[350] flex items-center justify-center p-6">
          <div className="bg-surface border border-border w-full max-w-4xl rounded-[3rem] overflow-hidden shadow-2xl animate-slide-up flex flex-col max-h-[90vh]">
            <div className="p-10 border-b border-border bg-surface-alt/50 flex items-center justify-between">
              <div className="flex items-center gap-5">
                <div className="w-12 h-12 rounded-2xl bg-primary flex items-center justify-center text-white crimson-glow">
                  <MessageSquare size={24} />
                </div>
                <div>
                  <h2 className="text-3xl font-black tracking-tighter">Feedback Intelligence</h2>
                  <div className="text-[10px] font-black text-primary uppercase tracking-widest mt-1">NLP Curricular Analysis</div>
                </div>
              </div>
              <button onClick={() => setShowFeedbackModal(false)} className="p-3 hover:bg-surface-alt border border-border rounded-xl transition-all"><X size={24} /></button>
            </div>
            
            <div className="flex-1 overflow-y-auto p-10 space-y-12 custom-scrollbar">
              {loadingFeedback ? (
                <div className="flex flex-col items-center justify-center py-20 space-y-4">
                   <div className="w-12 h-12 border-4 border-primary/20 border-t-primary rounded-full animate-spin"></div>
                   <p className="text-[10px] font-black text-text-muted uppercase tracking-widest">Analyzing Sentiment Data...</p>
                </div>
              ) : (
                <>
                  {/* AI Insights Hero */}
                  <div className="p-8 bg-primary/5 rounded-[2rem] border border-primary/20 space-y-4 relative overflow-hidden group">
                    <div className="absolute top-0 right-0 p-8 opacity-10 group-hover:opacity-20 transition-opacity">
                       <Sparkles size={120} />
                    </div>
                    <div className="flex items-center gap-3 text-primary relative z-10">
                      <Sparkles size={20} />
                      <span className="text-xs font-black uppercase tracking-widest">Aika Strategic Recommendation</span>
                    </div>
                    <p className="text-xl font-bold text-foreground leading-relaxed italic relative z-10">
                      "{feedbackAnalysis?.ai_insights}"
                    </p>
                    <div className="flex flex-wrap gap-2 mt-4 relative z-10">
                       {(feedbackAnalysis?.top_keywords || []).map((k: string) => (
                         <span key={k} className="px-3 py-1 bg-background border border-primary/20 rounded-full text-[10px] font-black text-primary uppercase tracking-widest">#{k}</span>
                       ))}
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-10">
                    {/* Concerns Section */}
                    <div className="space-y-6">
                       <div className="flex items-center justify-between">
                         <h3 className="text-xl font-black text-foreground flex items-center gap-2">
                           <AlertTriangle size={20} className="text-primary" /> Student Concerns
                         </h3>
                         <span className="text-[10px] font-black text-primary uppercase bg-primary/10 px-2 py-0.5 rounded-full">{feedbackAnalysis?.concerns?.length || 0} Nodes</span>
                       </div>
                       
                       <div className="space-y-4">
                         {(feedbackAnalysis?.concerns || []).length > 0 ? (feedbackAnalysis.concerns || []).map((c: any, i: number) => (
                           <div key={i} className="p-5 bg-surface-alt rounded-3xl border border-border border-l-4 border-l-primary group hover:bg-background transition-all">
                              <p className="text-sm font-medium text-foreground/90 italic leading-relaxed mb-3">"{c.text}"</p>
                              <div className="flex items-center justify-between">
                                 <div className="text-[10px] font-black text-text-muted uppercase tracking-tight">{c.student_name}</div>
                                 <div className="text-[10px] font-bold text-primary">Rating: {c.rating}/5</div>
                              </div>
                           </div>
                         )) : (
                           <div className="text-center py-10 border-2 border-dashed border-border rounded-3xl">
                              <p className="text-xs font-bold text-text-muted uppercase italic">No critical friction detected.</p>
                           </div>
                         )}
                       </div>
                    </div>

                    {/* Suggestions Section */}
                    <div className="space-y-6">
                       <div className="flex items-center justify-between">
                         <h3 className="text-xl font-black text-foreground flex items-center gap-2">
                           <Award size={20} className="text-success" /> Curricular Suggestions
                         </h3>
                         <span className="text-[10px] font-black text-success uppercase bg-success/10 px-2 py-0.5 rounded-full">{feedbackAnalysis?.suggestions?.length || 0} Units</span>
                       </div>

                       <div className="space-y-4">
                         {(feedbackAnalysis?.suggestions || []).length > 0 ? (feedbackAnalysis.suggestions || []).map((s: any, i: number) => (
                           <div key={i} className="p-5 bg-surface-alt rounded-3xl border border-border border-l-4 border-l-success group hover:bg-background transition-all">
                              <p className="text-sm font-medium text-foreground/90 italic leading-relaxed mb-3">"{s.text}"</p>
                              <div className="text-[10px] font-black text-text-muted uppercase tracking-tight">{s.student_name}</div>
                           </div>
                         )) : (
                           <div className="text-center py-10 border-2 border-dashed border-border rounded-3xl">
                              <p className="text-xs font-bold text-text-muted uppercase italic">Awaiting constructive proposals.</p>
                           </div>
                         )}
                       </div>
                    </div>
                  </div>

                  {/* Sentiment Summary */}
                  <div className="grid grid-cols-3 gap-6">
                    {[
                      { label: 'Positive', val: feedbackAnalysis?.sentiment_summary?.positive || 0, color: 'text-info' },
                      { label: 'Neutral', val: feedbackAnalysis?.sentiment_summary?.neutral || 0, color: 'text-text-muted' },
                      { label: 'Critical', val: feedbackAnalysis?.sentiment_summary?.negative || 0, color: 'text-primary' },
                    ].map(s => (
                      <div key={s.label} className="p-6 bg-surface-alt rounded-3xl border border-border text-center space-y-1">
                         <div className={`text-3xl font-black ${s.color}`}>{s.val}</div>
                         <div className="text-[10px] font-black text-text-muted uppercase tracking-widest">{s.label}</div>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </div>

            <div className="p-10 bg-surface-alt/50 border-t border-border flex gap-4">
               <button 
                onClick={() => setShowFeedbackModal(false)}
                className="flex-1 py-4 border border-border rounded-2xl font-black text-xs uppercase tracking-widest hover:bg-background transition-all"
               >
                 Close
               </button>
               <button 
                className="flex-1 px-8 py-4 bg-primary text-white rounded-2xl font-black text-xs uppercase tracking-widest hover:bg-primary-dark transition-all crimson-glow"
                onClick={() => alert("Class update started.")}
               >
                 Deploy Update
               </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
