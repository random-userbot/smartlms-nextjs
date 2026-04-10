'use client';

import React, { useState, useEffect, Suspense } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { 
  CheckCircle2, 
  X, 
  Search, 
  User, 
  FileText, 
  MessageSquare, 
  Award, 
  Sparkles,
  ChevronRight,
  ArrowLeft,
  Filter,
  Activity,
  Zap,
  Bot
} from 'lucide-react';
import Sidebar from '@/components/Sidebar';
import { assignmentsAPI, teacherAPI } from '@/lib/api';

function GradingContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const assignmentId = searchParams.get('assignment_id');

  const [submissions, setSubmissions] = useState<any[]>([]);
  const [selectedSubmission, setSelectedSubmission] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [grading, setGrading] = useState(false);
  const [score, setScore] = useState<number>(0);
  const [feedback, setFeedback] = useState<string>('');

  // AI Grading Assistance State
  const [aiReference, setAiReference] = useState<any>(null);
  const [aiRecap, setAiRecap] = useState<string>('');
  const [loadingReference, setLoadingReference] = useState(false);
  const [loadingRecap, setLoadingRecap] = useState(false);
  const [showReferencePanel, setShowReferencePanel] = useState(false);

  useEffect(() => {
    if (assignmentId) {
      loadSubmissions();
    }
  }, [assignmentId]);

  const loadSubmissions = async () => {
    setLoading(true);
    try {
      const res = await assignmentsAPI.getSubmissions(assignmentId!);
      setSubmissions(res.data || []);
    } catch (err) {
      console.error('Failed to load submissions', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectSubmission = async (sub: any) => {
    setSelectedSubmission(sub);
    setScore(sub.grade || 0); // Use grade instead of score to match backend
    setFeedback(sub.teacher_feedback || '');
    
    // Load AI Recap for this specific submission
    setLoadingRecap(true);
    setAiRecap('');
    try {
      const res = await assignmentsAPI.getRecap(sub.id);
      setAiRecap(res.data.recap);
    } catch (err) {
      console.error('Failed to load AI recap', err);
    } finally {
      setLoadingRecap(false);
    }
  };

  const loadAIReference = async () => {
    if (!assignmentId) return;
    setLoadingReference(true);
    try {
      const res = await assignmentsAPI.getReference(assignmentId);
      setAiReference(res.data);
      setShowReferencePanel(true);
    } catch (err) {
      console.error('Failed to load AI reference', err);
      alert('Could not synchronize AI reference key.');
    } finally {
      setLoadingReference(false);
    }
  };

  const handleGrade = async () => {
    if (!selectedSubmission) return;
    
    setGrading(true);
    try {
      await assignmentsAPI.grade({
        submission_id: selectedSubmission.id,
        grade: score,
        teacher_feedback: feedback
      });
      alert('Pedagogical score synchronized successfully.');
      loadSubmissions();
      setSelectedSubmission((prev: any) => ({ ...prev, score, feedback, status: 'Graded' }));
    } catch (err) {
      console.error('Grading failed', err);
      alert('Neural sync failure. Could not post score.');
    } finally {
      setGrading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="w-12 h-12 border-4 border-primary/20 border-t-primary rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="flex h-screen bg-background overflow-hidden font-sans">
      <Sidebar />
      <main className="flex-1 ml-64 flex flex-col relative z-10">
        
        {/* Header (Top Navigation) */}
        <header className="p-8 border-b border-border bg-surface/50 backdrop-blur-xl flex items-center justify-between">
           <div className="flex items-center gap-6">
              <button 
                onClick={() => router.back()} 
                className="w-10 h-10 flex items-center justify-center bg-surface-alt border border-border rounded-xl text-text-muted hover:text-primary transition-all"
              >
                <ArrowLeft size={20} />
              </button>
              <div>
                 <div className="text-[10px] font-black uppercase text-primary tracking-[0.2em]">Forensic Review Protocol</div>
                 <h1 className="text-3xl font-black tracking-tighter text-foreground">Grading Sequence.</h1>
              </div>
           </div>
            <div className="flex items-center gap-4">
               <button 
                 onClick={loadAIReference}
                 disabled={loadingReference}
                 className="px-6 py-2 bg-info/10 border border-info/20 rounded-full text-[10px] font-black uppercase tracking-widest text-info flex items-center gap-2 hover:bg-info hover:text-white transition-all shadow-lg"
               >
                  {loadingReference ? <Activity size={12} className="animate-spin" /> : <Sparkles size={12} />}
                  Pedagogical Reference Key
               </button>
               <div className="px-6 py-2 bg-primary/10 border border-primary/20 rounded-full text-[10px] font-black uppercase tracking-widest text-primary flex items-center gap-2">
                  <Zap size={12} /> {submissions.length} Submissions Synchronized
               </div>
            </div>
        </header>

        <div className="flex-1 flex overflow-hidden">
          
          {/* Submissions Sidebar (Left) */}
          <aside className="w-1/3 border-r border-border bg-surface-alt/30 overflow-y-auto custom-scrollbar">
             <div className="p-6 border-b border-border">
                <div className="relative">
                   <Search size={14} className="absolute left-4 top-1/2 -translate-y-1/2 text-text-muted" />
                   <input 
                      placeholder="Search neural ID..." 
                      className="w-full bg-background border border-border rounded-xl py-3 pl-10 pr-4 text-xs font-bold outline-none focus:border-primary/40 transition-all"
                   />
                </div>
             </div>
             <div className="divide-y divide-border/50">
               {submissions.map((sub, i) => (
                 <div 
                   key={i} 
                   onClick={() => handleSelectSubmission(sub)}
                   className={`p-6 cursor-pointer transition-all flex items-center justify-between group ${selectedSubmission?.id === sub.id ? 'bg-primary/5 border-l-4 border-l-primary shadow-inner' : 'hover:bg-white/5 border-l-4 border-l-transparent'}`}
                 >
                    <div className="flex items-center gap-4">
                       <div className="w-10 h-10 rounded-xl bg-surface border border-border flex items-center justify-center font-black text-primary group-hover:scale-110 transition-transform uppercase">
                          {sub.student_name?.charAt(0) || 'S'}
                       </div>
                       <div>
                          <div className={`text-sm font-black transition-colors ${selectedSubmission?.id === sub.id ? 'text-primary' : 'text-foreground group-hover:text-primary'}`}>
                             {sub.student_name}
                          </div>
                          <div className="text-[10px] font-bold text-text-muted mt-1 uppercase tracking-widest">
                             {new Date(sub.submitted_at).toLocaleDateString()} at {new Date(sub.submitted_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                          </div>
                       </div>
                    </div>
                    {sub.grade !== null ? (
                       <div className="text-right">
                          <div className="text-xs font-black text-success">{sub.grade} / {sub.max_score || 100}</div>
                          <div className="text-[8px] font-black uppercase text-text-muted tracking-widest">Synchronized</div>
                       </div>
                    ) : (
                       <div className="px-2 py-1 bg-primary/10 rounded-lg text-[8px] font-black uppercase text-primary animate-pulse tracking-widest">Pending</div>
                    )}
                 </div>
               ))}
               {submissions.length === 0 && (
                 <div className="p-12 text-center text-text-muted italic text-sm font-bold opacity-40">No submission nodes detected.</div>
               )}
             </div>
          </aside>

          {/* Grading Form (Right) */}
          <section className="flex-1 overflow-y-auto bg-background/50 p-12 relative">
             {selectedSubmission ? (
               <div className="max-w-3xl mx-auto space-y-12 animate-fade-in">
                  
                  {/* Submission Content */}
                  <div className="space-y-6">
                     <div className="flex items-center gap-4 text-primary">
                        <FileText size={20} />
                        <h2 className="text-xl font-black uppercase tracking-widest">Submission Payload</h2>
                     </div>

                     {/* AI Recap Display */}
                     {(loadingRecap || aiRecap) && (
                       <div className="p-8 bg-info/5 border-l-4 border-l-info rounded-r-[2rem] space-y-3 animate-fade-in">
                          <div className="flex items-center gap-2 text-[10px] font-black uppercase tracking-widest text-info">
                             <Bot size={14} className="shimmer" /> Student Intelligence Recap
                          </div>
                          {loadingRecap ? (
                            <div className="h-4 w-3/4 bg-info/10 animate-pulse rounded" />
                          ) : (
                            <p className="text-xs font-bold text-info/80 italic leading-relaxed">
                               "{aiRecap}"
                            </p>
                          )}
                       </div>
                     )}

                     <div className="glass-card p-10 bg-surface min-h-[200px] border-primary/20 shadow-2xl relative">
                        <p className="text-foreground/90 font-medium leading-relaxed whitespace-pre-wrap italic">
                           {selectedSubmission.text || "No textual payload provided. Verify external file resources (S3)."}
                        </p>
                        <div className="absolute top-4 right-4 text-[10px] font-black uppercase tracking-widest text-primary/40">Student Node Transcript</div>
                     </div>
                     {selectedSubmission.file_url && (
                        <a 
                          href={selectedSubmission.file_url} 
                          target="_blank" 
                          rel="noreferrer"
                          className="inline-flex items-center gap-3 px-6 py-3 bg-surface-alt border border-border rounded-xl text-xs font-black uppercase tracking-widest hover:border-primary/40 hover:text-primary transition-all"
                        >
                           <FileText size={16} /> Access Binary Resource
                        </a>
                     )}
                  </div>

                  {/* Grading Interface */}
                  <div className="space-y-6 pt-12 border-t border-border">
                     <div className="flex items-center gap-4 text-success">
                        <Award size={20} />
                        <h2 className="text-xl font-black uppercase tracking-widest">Node Calibration</h2>
                     </div>
                     
                     <div className="grid grid-cols-2 gap-8">
                        <div className="space-y-3">
                           <div className="flex justify-between items-center text-[10px] font-black uppercase tracking-widest text-text-muted px-1">
                              <span>Resonance Score</span>
                              <span>{score} / {selectedSubmission.max_score || 100}</span>
                           </div>
                           <input 
                             type="range" 
                             min="0" 
                             max={selectedSubmission.max_score || 100}
                             value={score}
                             onChange={(e) => setScore(parseInt(e.target.value))}
                             className="w-full h-2 bg-surface-alt rounded-lg appearance-none cursor-pointer accent-primary"
                           />
                           <div className="flex justify-between text-[8px] font-black text-text-muted uppercase tracking-widest mt-2">
                             <span>Lapse</span>
                             <span>Synchronized</span>
                           </div>
                        </div>
                        <div className="flex flex-col justify-center">
                           <div className="text-5xl font-black text-foreground shimmer">{score}</div>
                           <div className="text-[10px] font-black uppercase text-primary/60 tracking-[0.2em] mt-1">Calibrated Points</div>
                        </div>
                     </div>

                     <div className="space-y-3 pt-4">
                        <label className="text-[10px] font-black uppercase tracking-widest text-text-muted flex items-center gap-2">
                           <MessageSquare size={12} className="text-info" /> Feedback Synthesis
                        </label>
                        <textarea 
                           rows={5}
                           value={feedback}
                           onChange={(e) => setFeedback(e.target.value)}
                           placeholder="Synthesize pedagogical feedback for this submission node..."
                           className="w-full bg-surface border border-border rounded-2xl p-6 text-sm font-bold outline-none focus:border-primary/40 transition-all resize-none shadow-inner"
                        />
                     </div>

                     <button 
                       onClick={handleGrade}
                       disabled={grading}
                       className="w-full py-6 bg-primary text-white rounded-2xl font-black text-sm uppercase tracking-widest hover:scale-[1.02] active:scale-95 transition-all shadow-xl shadow-primary/20 crimson-glow disabled:opacity-50"
                     >
                        {grading ? 'Synchronizing Neural Scores...' : 'Post Calibration to Grid'}
                     </button>
                  </div>

               </div>
             ) : (
               <div className="h-full flex flex-col items-center justify-center text-center opacity-30 select-none">
                  <Activity size={100} className="text-primary mb-8 animate-pulse" />
                  <h3 className="text-3xl font-black tracking-tight">System Idle. Select a submission node.</h3>
                  <p className="text-xs font-bold uppercase tracking-widest mt-4">Forensic review protocol active</p>
               </div>
             )}
          </section>

           {/* AI Reference Sidebar (Far Right) */}
           {showReferencePanel && (
             <aside className="w-80 border-l border-border bg-surface-alt/50 overflow-y-auto animate-slide-in-right custom-scrollbar">
                <div className="p-8 border-b border-border flex items-center justify-between sticky top-0 bg-surface/80 backdrop-blur-md z-10">
                   <div className="flex items-center gap-3">
                      <Sparkles size={20} className="text-info" />
                      <h3 className="text-sm font-black uppercase tracking-widest">Aika Reference</h3>
                   </div>
                   <button onClick={() => setShowReferencePanel(false)} className="p-2 hover:bg-surface-alt rounded-lg"><X size={16} /></button>
                </div>
                
                <div className="p-8 space-y-10">
                   <div className="space-y-4">
                      <div className="text-[10px] font-black uppercase tracking-widest text-info flex items-center gap-2">
                         <Award size={12} /> Ideal Solution
                      </div>
                      <div className="text-[11px] font-bold text-foreground/80 leading-relaxed bg-background/50 border border-border p-5 rounded-2xl italic">
                         {aiReference?.perfect_answer || "Synthesizing ideal node..."}
                      </div>
                   </div>

                   <div className="space-y-6">
                      <div className="text-[10px] font-black uppercase tracking-widest text-info flex items-center gap-2">
                         <Activity size={12} /> Rubric Logic
                      </div>
                      <div className="space-y-4">
                         {aiReference?.rubric?.map((r: any, i: number) => (
                           <div key={i} className="p-4 bg-surface rounded-xl border border-border space-y-1">
                              <div className="flex justify-between items-center">
                                 <span className="text-[10px] font-black text-primary uppercase">{r.criterion}</span>
                                 <span className="text-[10px] font-black text-text-muted">{r.weight}</span>
                              </div>
                              <p className="text-[10px] font-medium text-text-muted leading-tight">{r.description}</p>
                           </div>
                         ))}
                      </div>
                   </div>
                </div>
             </aside>
           )}

        </div>


      </main>
    </div>
  );
}

export default function GradingPage() {
    return (
        <Suspense fallback={<div>Loading Neural Workspace...</div>}>
            <GradingContent />
        </Suspense>
    );
}
