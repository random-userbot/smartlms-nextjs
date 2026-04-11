'use client';

import React, { useState, useEffect } from 'react';
import { 
  Activity,
  Sparkles, 
  Plus, 
  Search, 
  Filter, 
  Trash2, 
  Edit3, 
  Eye, 
  Brain, 
  FileText, 
  ChevronRight,
  Zap,
  Wand2,
  RefreshCw,
  Layout,
  X,
  ArrowUpRight,
  CheckCircle2,
  BookOpen,
  Play
} from 'lucide-react';
import Sidebar from '@/components/Sidebar';
import { quizzesAPI, coursesAPI, lecturesAPI } from '@/lib/api';
import { useAuth } from '@/context/AuthContext';
import { useParams, useSearchParams } from 'next/navigation';

import { Suspense } from 'react';

function TeacherQuizzesContent() {
  const { user } = useAuth();
  const searchParams = useSearchParams();
  // ... rest of the existing state and functions ...
  const [quizzes, setQuizzes] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [courses, setCourses] = useState<any[]>([]);
  const [lectures, setLectures] = useState<any[]>([]);
  const [isGenerating, setIsGenerating] = useState(false);
  const [showGenModal, setShowGenModal] = useState(false);
  const [genParams, setGenParams] = useState({
    lecture_id: '',
    course_id: '',
    num_questions: 10,
    difficulty: 'medium',
    include_icap: true,
    anti_cheat_enabled: true,
    webcam_required: false,
    time_limit: 10
  });
  const [generatedQuestions, setGeneratedQuestions] = useState<any[]>([]);
  const [refining, setRefining] = useState(false);
  const [refineFeedback, setRefineFeedback] = useState('');

  useEffect(() => {
    loadData();
    
    // Check for deep-linked generation
    const lid = searchParams.get('lecture_id');
    const cid = searchParams.get('course_id');
    
    if (lid && cid) {
      setGenParams(prev => ({ ...prev, lecture_id: lid, course_id: cid }));
      loadLectures(cid);
      setShowGenModal(true);
    }
  }, [searchParams]);

  const loadData = async () => {
    try {
      const [quizRes, courseRes] = await Promise.all([
        quizzesAPI.listMine(),
        coursesAPI.list()
      ]);
      setQuizzes(Array.isArray(quizRes.data) ? quizRes.data : []);
      setCourses(Array.isArray(courseRes.data) ? courseRes.data : []);
    } catch (err) {
      console.error('Failed to load quizzes', err);
    } finally {
      setLoading(false);
    }
  };

  const loadLectures = async (courseId: string) => {
    try {
      const res = await lecturesAPI.getByCourse(courseId);
      setLectures(Array.isArray(res.data) ? res.data : []);
    } catch (err) {
      console.error('Failed to load lectures', err);
    }
  };

  const handleGenerate = async () => {
    if (!genParams.lecture_id) return;
    setIsGenerating(true);
    setGeneratedQuestions([]);
    try {
      const res = await quizzesAPI.generateAI(genParams);
      setGeneratedQuestions(res.data.questions);
    } catch (err) {
      console.error('AI Generation failed', err);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleRefine = async () => {
    if (!refineFeedback || generatedQuestions.length === 0) return;
    setRefining(true);
    try {
      const res = await quizzesAPI.refineAI({
        lecture_id: genParams.lecture_id,
        current_questions: generatedQuestions,
        feedback: refineFeedback
      });
      setGeneratedQuestions(res.data.questions);
      setRefineFeedback('');
    } catch (err) {
      console.error('Refinement failed', err);
    } finally {
      setRefining(false);
    }
  };

  const handleSaveQuiz = async () => {
    if (generatedQuestions.length === 0) return;
    try {
      const lecture = lectures.find(l => l.id === genParams.lecture_id);
      await quizzesAPI.create({
        lecture_id: genParams.lecture_id,
        title: `Assessment: ${lecture?.title || 'Lecture Module'}`,
        questions: generatedQuestions,
        is_published: true,
        anti_cheat_enabled: genParams.anti_cheat_enabled,
        webcam_required: genParams.webcam_required,
        time_limit: genParams.time_limit * 60
      });
      setShowGenModal(false);
      setGeneratedQuestions([]);
      loadData();
    } catch (err) {
      console.error('Failed to save quiz', err);
    }
  };

  const handleDeleteQuiz = async (id: string) => {
    if (!confirm('Purge this assessment module? All student traces will be lost.')) return;
    try {
      await quizzesAPI.delete(id);
      loadData();
    } catch (err) {
      console.error('Purge failed', err);
    }
  };

  return (
    <div className="flex h-screen bg-background overflow-hidden font-sans">
      <Sidebar />
      <main className="flex-1 ml-64 p-12 overflow-y-auto space-y-12 animate-fade-in">
        
        {/* Header */}
        <header className="flex flex-col md:flex-row md:items-end justify-between gap-8">
          <div>
            <div className="text-[10px] uppercase tracking-[0.4em] font-black text-primary mb-2 flex items-center gap-2">
              <Brain size={12} /> Cognitive Engineering
            </div>
            <h1 className="text-7xl font-black tracking-tighter text-foreground leading-[0.9]">
              Quizzes.
            </h1>
            <p className="text-text-muted font-bold mt-6 max-w-xl leading-relaxed">
              Engineer high-fidelity assessments using Aika's generative engine. Deploy modules across your learning sequences.
            </p>
          </div>
          <button 
            onClick={() => setShowGenModal(true)}
            className="btn-primary py-5 px-10 text-xs font-black uppercase tracking-widest flex items-center gap-3 crimson-glow"
          >
            <Wand2 size={18} /> Initiate AI Synthesis
          </button>
        </header>

        {/* Bento Grid Stats */}
        <div className="grid grid-cols-12 gap-8">
          <div className="col-span-12 lg:col-span-4 glass-card p-8 flex flex-col gap-6">
            <div className="w-12 h-12 rounded-2xl bg-primary/10 flex items-center justify-center text-primary border border-primary/20">
              <Zap size={24} />
            </div>
            <div>
              <div className="text-4xl font-black text-foreground">{quizzes.length}</div>
              <div className="text-[10px] font-black text-text-muted uppercase tracking-widest mt-1">Active Modules</div>
            </div>
          </div>
          <div className="col-span-12 lg:col-span-4 glass-card p-8 flex flex-col gap-6">
            <div className="w-12 h-12 rounded-2xl bg-success/10 flex items-center justify-center text-success border border-success/20">
              <Activity size={24} />
            </div>
            <div>
              <div className="text-4xl font-black text-foreground">
                {quizzes.length > 0 ? (quizzes.reduce((acc, q) => acc + (q.best_percentage || 0), 0) / quizzes.length).toFixed(0) : 0}%
              </div>
              <div className="text-[10px] font-black text-text-muted uppercase tracking-widest mt-1">Average Evaluation</div>
            </div>
          </div>
          <div className="col-span-12 lg:col-span-4 glass-card p-8 flex flex-col gap-6">
            <div className="w-12 h-12 rounded-2xl bg-info/10 flex items-center justify-center text-info border border-info/20">
              <Sparkles size={24} />
            </div>
            <div>
              <div className="text-4xl font-black text-foreground">Aika Pro</div>
              <div className="text-[10px] font-black text-text-muted uppercase tracking-widest mt-1">Synthesis Engine</div>
            </div>
          </div>
        </div>

        {/* Quiz List */}
        <div className="glass-premium rounded-[3rem] border border-border overflow-hidden">
          <div className="p-8 border-b border-border bg-surface-alt flex items-center justify-between">
            <h3 className="text-xl font-black flex items-center gap-3">
              <Layout size={20} className="text-primary" /> Assessment Repositories
            </h3>
            <div className="flex gap-4">
               <div className="relative">
                  <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-text-muted" size={16} />
                  <input className="bg-background border border-border rounded-xl py-2 pl-12 pr-6 text-sm font-bold outline-none focus:border-primary/40 transition-all w-64" placeholder="Probe modules..." />
                </div>
            </div>
          </div>
          
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border bg-surface-alt/50">
                  <th className="px-8 py-5 text-left text-[10px] font-black uppercase tracking-widest text-text-muted">Module Identity</th>
                  <th className="px-8 py-5 text-left text-[10px] font-black uppercase tracking-widest text-text-muted">Parent Sequence</th>
                  <th className="px-8 py-5 text-left text-[10px] font-black uppercase tracking-widest text-text-muted">Resonance</th>
                  <th className="px-8 py-5 text-left text-[10px] font-black uppercase tracking-widest text-text-muted">Status</th>
                  <th className="px-8 py-5 text-center text-[10px] font-black uppercase tracking-widest text-text-muted">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {loading ? (
                  <tr><td colSpan={5} className="p-20 text-center"><div className="w-10 h-10 border-4 border-primary/20 border-t-primary rounded-full animate-spin mx-auto"></div></td></tr>
                ) : quizzes.length === 0 ? (
                  <tr><td colSpan={5} className="p-20 text-center font-bold text-text-muted italic">No assessment sequences detected.</td></tr>
                ) : quizzes.map((q) => (
                  <tr key={q.id} className="hover:bg-surface-alt transition-colors group">
                    <td className="px-8 py-6">
                      <div className="font-black text-foreground">{q.title}</div>
                      <div className="text-[10px] text-text-muted font-bold mt-1">ID: {q.id?.slice(0,8)}...</div>
                    </td>
                    <td className="px-8 py-6">
                      <div className="text-sm font-bold text-foreground/80">{q.course_title}</div>
                      <div className="text-[10px] text-primary/60 font-black uppercase italic mt-1">{q.lecture_title}</div>
                    </td>
                    <td className="px-8 py-6">
                       <span className="text-xs font-black text-success">+{q.best_percentage || 0}%</span>
                    </td>
                    <td className="px-8 py-6">
                      <span className={`px-3 py-1 rounded-full text-[8px] font-black uppercase tracking-widest border ${q.is_published ? 'bg-success/5 text-success border-success/20' : 'bg-warning/5 text-warning border-warning/20'}`}>
                        {q.is_published ? 'Active' : 'Draft'}
                      </span>
                    </td>
                    <td className="px-8 py-6">
                      <div className="flex justify-center gap-2">
                        <button className="p-2 hover:bg-primary/10 rounded-lg text-primary transition-all"><Edit3 size={16} /></button>
                        <button 
                          onClick={() => handleDeleteQuiz(q.id)}
                          className="p-2 hover:bg-error/10 rounded-lg text-error transition-all"
                        >
                          <Trash2 size={16} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

      </main>

      {/* AI Synthesis Modal */}
      {showGenModal && (
        <div className="fixed inset-0 bg-background/90 backdrop-blur-2xl z-[100] p-8 flex items-center justify-center">
          <div className="bg-surface border border-border w-full max-w-6xl h-[85vh] rounded-[4rem] overflow-hidden flex flex-col shadow-2xl relative">
            
            {/* Modal Header */}
            <div className="p-10 border-b border-border bg-surface-alt/50 flex items-center justify-between">
              <div className="flex items-center gap-6">
                <div className="w-16 h-16 rounded-[1.5rem] bg-primary flex items-center justify-center text-white crimson-glow">
                  <Sparkles size={32} />
                </div>
                <div>
                  <h2 className="text-4xl font-black tracking-tighter text-foreground uppercase">AI Synthesis</h2>
                  <p className="text-[10px] font-black text-primary uppercase tracking-[0.3em] mt-1">Autonomous question engineering active</p>
                </div>
              </div>
              <button 
                onClick={() => { setShowGenModal(false); setGeneratedQuestions([]); }}
                className="p-4 hover:bg-surface-alt rounded-3xl border border-border text-text-muted hover:text-foreground transition-all"
              >
                <X size={28} />
              </button>
            </div>

              <div className="flex-1 overflow-hidden flex">
                {/* Generation Form Sidebar */}
                <div className="w-[400px] border-r border-border p-10 space-y-10 overflow-y-auto bg-surface-alt/20">
                  <div className="space-y-4">
                    <label className="text-[10px] font-black text-text-muted uppercase tracking-widest ml-1">Target Curriculum Branch</label>
                    <select 
                      value={genParams.course_id}
                      onChange={(e) => { 
                        setGenParams({...genParams, course_id: e.target.value, lecture_id: ''});
                        loadLectures(e.target.value);
                      }}
                      className="w-full px-8 py-5 bg-surface border border-border rounded-2xl font-bold outline-none focus:border-primary transition-all appearance-none"
                    >
                      <option value="">Select Module</option>
                      {courses.map(c => <option key={c.id} value={c.id}>{c.title}</option>)}
                    </select>
                  </div>

                  <div className="space-y-4">
                    <label className="text-[10px] font-black text-text-muted uppercase tracking-widest ml-1">Specific Neural Node</label>
                    <select 
                      value={genParams.lecture_id}
                      onChange={(e) => setGenParams({...genParams, lecture_id: e.target.value})}
                      className="w-full px-8 py-5 bg-surface border border-border rounded-2xl font-bold outline-none focus:border-primary transition-all appearance-none"
                    >
                      <option value="">Select Node</option>
                      {lectures.map(l => <option key={l.id} value={l.id}>{l.title}</option>)}
                    </select>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                       <label className="text-[10px] font-black text-text-muted uppercase tracking-widest">Questions</label>
                       <input type="number" value={genParams.num_questions} onChange={e => setGenParams({...genParams, num_questions: parseInt(e.target.value)})} className="w-full px-6 py-4 bg-surface border border-border rounded-xl font-bold outline-none focus:border-primary" />
                    </div>
                    <div className="space-y-2">
                       <label className="text-[10px] font-black text-text-muted uppercase tracking-widest">Time (min)</label>
                       <input type="number" value={genParams.time_limit} onChange={e => setGenParams({...genParams, time_limit: parseInt(e.target.value)})} className="w-full px-6 py-4 bg-surface border border-border rounded-xl font-bold outline-none focus:border-primary" />
                    </div>
                  </div>

                  <div className="space-y-6 pt-4">
                     <label className="flex items-center gap-4 cursor-pointer group">
                        <div className="relative">
                          <input type="checkbox" checked={genParams.anti_cheat_enabled} onChange={e => setGenParams({...genParams, anti_cheat_enabled: e.target.checked})} className="sr-only" />
                          <div className={`w-14 h-8 rounded-full transition-all ${genParams.anti_cheat_enabled ? 'bg-primary' : 'bg-border'}`} />
                          <div className={`absolute top-1 left-1 w-6 h-6 bg-white rounded-full transition-all shadow-lg ${genParams.anti_cheat_enabled ? 'translate-x-6' : ''}`} />
                        </div>
                        <span className="text-[10px] font-black uppercase tracking-widest group-hover:text-primary transition-colors">Anti-Cheat Core</span>
                     </label>

                     <label className="flex items-center gap-4 cursor-pointer group">
                        <div className="relative">
                          <input type="checkbox" checked={genParams.webcam_required} onChange={e => setGenParams({...genParams, webcam_required: e.target.checked})} className="sr-only" />
                          <div className={`w-14 h-8 rounded-full transition-all ${genParams.webcam_required ? 'bg-primary' : 'bg-border'}`} />
                          <div className={`absolute top-1 left-1 w-6 h-6 bg-white rounded-full transition-all shadow-lg ${genParams.webcam_required ? 'translate-x-6' : ''}`} />
                        </div>
                        <span className="text-[10px] font-black uppercase tracking-widest group-hover:text-primary transition-colors">Webcam Verification</span>
                     </label>
                  </div>

                  <button 
                    onClick={handleGenerate}
                    disabled={isGenerating || !genParams.lecture_id}
                    className="w-full py-6 bg-primary text-white rounded-[2rem] font-black text-sm uppercase tracking-[0.3em] crimson-glow hover:scale-[1.02] active:scale-95 transition-all shadow-2xl flex items-center justify-center gap-4"
                  >
                     {isGenerating ? <RefreshCw className="animate-spin" /> : <Sparkles size={20} />}
                     {isGenerating ? 'Synthesizing...' : 'Generate Blueprint'}
                  </button>
                </div>

              <div className="flex-1 p-10 flex flex-col overflow-hidden">
                {!isGenerating && generatedQuestions.length === 0 ? (
                  <div className="flex-1 flex flex-col items-center justify-center text-center p-20 opacity-40">
                     <Brain size={120} className="mb-8 text-primary/20" />
                     <h4 className="text-3xl font-black mb-4">Awaiting Curricular Stream</h4>
                  </div>
                ) : (
                  <div className="flex-1 flex flex-col overflow-hidden space-y-6">
                    <div className="flex items-center justify-between">
                       <h4 className="text-xl font-black text-foreground flex items-center gap-3">
                         <CheckCircle2 className="text-success" /> Generated Blueprint ({generatedQuestions.length})
                       </h4>
                       <button onClick={handleSaveQuiz} className="px-8 py-3 bg-success text-white font-black rounded-xl hover:bg-success-dark transition-all crimson-glow">Finalize & Deploy</button>
                    </div>

                    <div className="flex-1 overflow-y-auto space-y-4 pr-4 custom-scrollbar">
                      {generatedQuestions.map((q, i) => (
                        <div key={i} className="glass-card p-6 border-white/5 space-y-4 group">
                          <div className="flex gap-4">
                            <span className="w-8 h-8 rounded-lg bg-surface-alt flex items-center justify-center font-black text-sm text-primary">{i+1}</span>
                            <div>
                                <div className="font-black text-lg text-foreground">{q.question}</div>
                                <div className="flex items-center gap-4 mt-2">
                                  <div className="text-[8px] font-black text-primary uppercase tracking-[0.2em]">{q.type}</div>
                                  <div className="text-[8px] font-black text-success uppercase tracking-[0.2em] px-2 py-0.5 bg-success/10 rounded">Points: {q.points || 1}</div>
                                  <div className="text-[8px] font-black text-info uppercase tracking-[0.2em] px-2 py-0.5 bg-info/10 rounded">ICAP: {q.icap_level || 'active'}</div>
                                </div>
                                
                                {q.options && (
                                  <div className="grid grid-cols-2 gap-3 mt-4">
                                    {q.options.map((opt: string, oi: number) => (
                                      <div key={oi} className={`p-4 rounded-xl border text-xs font-bold transition-all ${opt === q.correct_answer ? 'border-success bg-success/5 text-success' : 'border-border bg-black/5'}`}>
                                        {opt}
                                      </div>
                                    ))}
                                  </div>
                                )}
                                
                                {!q.options && (
                                  <div className="mt-4 p-4 rounded-xl border border-success/20 bg-success/5 text-xs font-bold text-success">
                                    Correct Answer: {q.correct_answer}
                                  </div>
                                )}
                                
                                {q.explanation && (
                                  <div className="mt-4 p-4 rounded-2xl bg-primary/5 border border-primary/10 text-[10px] text-text-muted italic">
                                    <span className="font-black uppercase tracking-widest text-primary mr-2">Rationale:</span> {q.explanation}
                                  </div>
                                )}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>

                    <div className="p-8 bg-surface-alt border border-border rounded-[2.5rem] flex items-center gap-6">
                       <input 
                         value={refineFeedback}
                         onChange={(e) => setRefineFeedback(e.target.value)}
                         className="flex-1 bg-surface border border-border rounded-2xl p-4 text-sm font-bold outline-none focus:border-primary/40 text-foreground"
                         placeholder="Refine Blueprint..."
                       />
                       <button onClick={handleRefine} disabled={refining} className="btn-primary py-4 px-8 text-xs font-black uppercase tracking-widest">
                         {refining ? <RefreshCw className="animate-spin" /> : 'Refine'}
                       </button>
                    </div>
                  </div>
                )}
              </div>

            </div>

          </div>
        </div>
      )}

    </div>
  );
}

export default function TeacherQuizzesPage() {
  return (
    <Suspense fallback={<div className="flex h-screen bg-background items-center justify-center"><div className="w-12 h-12 border-4 border-primary/20 border-t-primary rounded-full animate-spin" /></div>}>
      <TeacherQuizzesContent />
    </Suspense>
  );
}
