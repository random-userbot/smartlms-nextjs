'use client';

import React, { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { 
  teacherAPI, 
  analyticsAPI, 
  quizzesAPI,
  coursesAPI,
  messagesAPI
} from '@/lib/api';
import Sidebar from '@/components/Sidebar';
import { 
  User, 
  Activity, 
  BarChart3, 
  Award, 
  Clock, 
  ArrowLeft,
  Search,
  Filter,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Mail,
  Zap
} from 'lucide-react';
import CommunicationFab from '@/components/CommunicationFab';
import NeuralInsights from '@/components/teacher/NeuralInsights';
import { Calendar, ChevronRight, Play } from 'lucide-react';

export default function StudentDetailPage() {
  const { id } = useParams();
  const router = useRouter();
  const [student, setStudent] = useState<any>(null);
  const [activities, setActivities] = useState<any[]>([]);
  const [quizzes, setQuizzes] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedSession, setSelectedSession] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;

    setLoading(true);
    Promise.all([
      teacherAPI.getStudentDetail(id as string),
      quizzesAPI.getStudentAttempts(id as string, 'all'), // 'all' for general lookup, or specific course if context allows
      // Add more specific analytics if needed
    ]).then(([studentRes, quizRes]) => {
      setStudent(studentRes.data);
      setQuizzes(quizRes.data || []);
      
      // Auto-select latest session if available
      if (studentRes.data.sessions && studentRes.data.sessions.length > 0) {
        setSelectedSession(studentRes.data.sessions[0].id);
      }
      
      setLoading(false);
    }).catch(err => {
      console.error('Failed to load student detail:', err);
      setError('Failed to load student data. They may not be enrolled in any of your courses.');
      setLoading(false);
    });
  }, [id]);

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

  if (error || !student) {
    return (
      <div className="flex min-h-screen bg-background text-red-500 items-center justify-center">
         <div className="text-center space-y-4">
            <h1 className="text-3xl font-black">{error || 'Student Not Found'}</h1>
            <button onClick={() => router.back()} className="px-6 py-3 bg-primary text-white rounded-2xl font-bold uppercase tracking-widest text-xs">Go Back</button>
         </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-background">
      <Sidebar />
      <main className="flex-1 ml-64 p-12 space-y-10 animate-fade-in relative z-10">
        
        {/* Header */}
        <header className="flex flex-col md:flex-row md:items-end justify-between gap-6">
          <div className="flex items-center gap-6">
             <button 
                onClick={() => router.back()} 
                className="w-14 h-14 flex items-center justify-center bg-surface border-2 border-border rounded-full text-text-muted hover:text-primary hover:border-primary/40 transition-all shadow-lg crimson-glow group"
             >
                <ArrowLeft size={24} className="group-hover:-translate-x-1 transition-transform" />
             </button>
             <div>
                <div className="text-[10px] uppercase tracking-[0.3em] font-black text-primary mb-2">Student Intelligence Profile</div>
                <h1 className="text-6xl font-black tracking-tighter text-foreground">{student.full_name}</h1>
                <div className="flex items-center gap-4 mt-4">
                   <div className="flex items-center gap-2 px-4 py-1.5 bg-primary/10 border border-primary/20 rounded-full text-[10px] font-black text-primary uppercase tracking-widest">
                      <Zap size={12} /> {student.role || 'Scholar'}
                   </div>
                   <div className="text-sm font-bold text-text-muted">{student.email}</div>
                </div>
             </div>
          </div>
          <div className="flex gap-4">
             <div className="glass-card px-8 py-4 text-center border-primary/20">
                <div className="text-4xl font-black text-foreground shimmer">{(student.engagement_score || 0).toFixed(0)}%</div>
                <div className="text-[10px] font-black text-text-muted uppercase tracking-widest mt-1">Global Engagement</div>
             </div>
          </div>
        </header>

        {/* Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
           {[
              { label: 'Visbility', value: `${(student.visibility_score || 0).toFixed(0)}%`, icon: User, color: 'text-primary' },
              { label: 'Quiz Avg', value: `${(student.quiz_avg || 0).toFixed(0)}%`, icon: Award, color: 'text-success' },
              { label: 'Focus Index', value: `${(student.focus_index || 0).toFixed(1)}`, icon: Activity, color: 'text-warning' },
              { label: 'Sessions', value: student.session_count || 0, icon: Clock, color: 'text-info' },
           ].map((s, i) => (
              <div key={i} className="glass-card p-8 flex items-center justify-between group hover:border-primary/40 transition-all transition-transform hover:-translate-y-1">
                 <div className="space-y-1">
                    <div className="text-sm font-black text-text-muted uppercase tracking-widest">{s.label}</div>
                    <div className="text-3xl font-black text-foreground">{s.value}</div>
                 </div>
                 <div className={`p-4 bg-surface rounded-2xl border border-border ${s.color}`}><s.icon size={24} /></div>
              </div>
           ))}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-12 gap-8">
           {/* Quiz Performance */}
           <section className="col-span-12 lg:col-span-8 space-y-6">
              <div className="flex items-center justify-between">
                 <h2 className="text-3xl font-black text-foreground tracking-tight flex items-center gap-3">
                   <BarChart3 className="text-primary" /> Assessment Analytics
                 </h2>
              </div>
              
              <div className="glass-card overflow-hidden">
                 <table className="w-full text-left border-collapse">
                    <thead className="bg-surface-alt border-b border-border">
                       <tr>
                          <th className="p-6 text-[10px] font-black uppercase tracking-widest text-text-muted">Assessment</th>
                          <th className="p-6 text-[10px] font-black uppercase tracking-widest text-text-muted text-center">Score</th>
                          <th className="p-6 text-[10px] font-black uppercase tracking-widest text-text-muted text-center">Status</th>
                          <th className="p-6 text-[10px] font-black uppercase tracking-widest text-text-muted text-right">Completed</th>
                       </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                       {quizzes.length > 0 ? quizzes.map((q, i) => (
                           <tr key={i} className="hover:bg-primary/5 transition-colors group">
                              <td className="p-6">
                                 <div className="text-sm font-bold text-foreground">{q.quiz_title}</div>
                                 <div className="text-[10px] font-bold text-text-muted uppercase tracking-widest mt-1">Course: {q.course_title || q.lecture_title}</div>
                              </td>
                              <td className="p-6 text-center">
                                 <div className={`text-lg font-black ${q.percentage >= 80 ? 'text-success' : q.percentage >= 50 ? 'text-warning' : 'text-primary'}`}>
                                    {q.percentage}%
                                 </div>
                              </td>
                              <td className="p-6 flex justify-center">
                                 {q.percentage >= 50 ? (
                                    <div className="px-4 py-1 bg-success/20 text-success border border-success/40 rounded-full text-[10px] font-black uppercase tracking-widest flex items-center gap-2">
                                       <CheckCircle2 size={12} /> Passed
                                    </div>
                                 ) : (
                                    <div className="px-4 py-1 bg-primary/20 text-primary border border-primary/40 rounded-full text-[10px] font-black uppercase tracking-widest flex items-center gap-2">
                                       <XCircle size={12} /> Underperformed
                                    </div>
                                 )}
                              </td>
                             <td className="p-6 text-right">
                                <div className="text-xs font-bold text-text-muted">{new Date(q.completed_at).toLocaleDateString()}</div>
                             </td>
                          </tr>
                       )) : (
                          <tr>
                             <td colSpan={4} className="p-12 text-center text-text-muted font-bold italic">No assessment data available for this student.</td>
                          </tr>
                       )}
                    </tbody>
                 </table>
              </div>
           </section>

           {/* Activity & Risks */}
           <section className="col-span-12 lg:col-span-4 space-y-6">
              <h2 className="text-3xl font-black text-foreground tracking-tight flex items-center gap-3">
                 <AlertTriangle className="text-warning" /> Behavioral Synthesis
              </h2>
              
              <div className="glass-card p-8 space-y-8">
                 <div className="space-y-6">
                    <div className="flex justify-between items-end">
                       <div className="space-y-1">
                          <div className="text-[10px] font-black text-text-muted uppercase tracking-widest">Visibility Consistency</div>
                          <div className="text-xl font-black text-foreground">{(student.visibility_score || 0).toFixed(1)}%</div>
                       </div>
                       <div className="w-32 h-1.5 bg-background rounded-full overflow-hidden">
                          <div className="h-full bg-primary rounded-full" style={{ width: `${student.visibility_score}%` }}></div>
                       </div>
                    </div>
                    
                    <div className="flex justify-between items-end">
                       <div className="space-y-1">
                          <div className="text-[10px] font-black text-text-muted uppercase tracking-widest">Lecture Attendance</div>
                          <div className="text-xl font-black text-foreground">{student.attendance_rate || 0}%</div>
                       </div>
                       <div className="w-32 h-1.5 bg-background rounded-full overflow-hidden">
                          <div className="h-full bg-success rounded-full" style={{ width: `${student.attendance_rate}%` }}></div>
                       </div>
                    </div>
                 </div>

                 <div className="p-6 bg-surface-alt rounded-2xl border border-border space-y-4">
                    <div className="text-xs font-bold text-text-muted uppercase tracking-widest flex items-center gap-2">
                       <Mail size={12} /> System Recommendation:
                    </div>
                    <p className="text-sm font-medium text-foreground/90 leading-relaxed italic">
                       {student.engagement_score < 60 
                          ? "Student engagement is falling below standard. Strategic intervention via direct messaging is recommended."
                          : "Student is performing within optimal parameters. Maintain current pedagogical synchronization."}
                    </p>
                 </div>
              </div>
           </section>
        </div>

         {/* Neural Forensic Hub */}
         <section className="space-y-10 pt-10 border-t border-white/5">
            <div className="flex flex-col md:flex-row md:items-end justify-between gap-6">
               <div className="space-y-1">
                  <div className="text-[10px] font-black text-primary uppercase tracking-[0.4em]">Intelligence Pulse</div>
                  <h2 className="text-4xl font-black text-foreground tracking-tighter italic">Neural Forensic Hub</h2>
                  <p className="text-sm font-medium text-text-muted">Analyze high-fidelity behavioral diagnostics for specific learning sessions.</p>
               </div>
               
               {/* Session Selector (Slide-able Cards) */}
               <div className="flex gap-4 overflow-x-auto pb-4 max-w-full md:max-w-[500px] no-scrollbar">
                  {student.sessions?.map((session: any) => (
                     <button 
                        key={session.id}
                        onClick={() => setSelectedSession(session.id)}
                        className={`shrink-0 px-6 py-4 rounded-3xl border-2 transition-all flex flex-col gap-2 min-w-[200px] text-left
                           ${selectedSession === session.id 
                              ? 'bg-primary/20 border-primary text-primary crimson-glow' 
                              : 'bg-surface border-border text-text-muted hover:border-primary/40'}`}
                     >
                        <div className="flex items-center justify-between font-black text-[8px] uppercase tracking-widest">
                           <span className="flex items-center gap-1"><Calendar size={10} /> {new Date(session.date).toLocaleDateString()}</span>
                           <span className="text-foreground">{session.avg_score}% Index</span>
                        </div>
                        <div className="text-xs font-black truncate">{session.lecture_title}</div>
                        <div className="flex items-center gap-2 text-[8px] font-bold uppercase opacity-60">
                           <Play size={8} /> {Math.round(session.duration / 60)}m Sync
                        </div>
                     </button>
                  ))}
               </div>
            </div>

            {selectedSession ? (
               <NeuralInsights studentId={id as string} sessionId={selectedSession} />
            ) : (
               <div className="h-96 glass-card flex flex-col items-center justify-center space-y-4 border-dashed border-white/10 opacity-30">
                  <Activity size={48} className="animate-pulse" />
                  <div className="text-xs font-black uppercase tracking-widest text-center">
                     Synchronize with a past session period<br/>to begin forensic reconstruction
                  </div>
               </div>
            )}
         </section>

        {/* Floating Communication UI */}
        <CommunicationFab recipientId={student.id} recipientName={student.full_name} />
      </main>
    </div>
  );
}
