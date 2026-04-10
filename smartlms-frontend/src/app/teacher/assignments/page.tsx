'use client';

import React, { useState, useEffect } from 'react';
import { 
  Plus, 
  FileText, 
  Clock, 
  Calendar, 
  ChevronRight, 
  Search, 
  Filter, 
  Trash2, 
  BookOpen,
  Award,
  Users,
  CheckCircle2,
  XCircle,
  Sparkles,
  Target
} from 'lucide-react';
import Sidebar from '@/components/Sidebar';
import { coursesAPI, assignmentsAPI, lecturesAPI } from '@/lib/api';
import Link from 'next/link';

export default function AssignmentsPage() {
  const [courses, setCourses] = useState<any[]>([]);
  const [selectedCourse, setSelectedCourse] = useState<string>('');
  const [assignments, setAssignments] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [dataLoading, setDataLoading] = useState(false);
  const [showCreateModal, setShowCreateModal] = useState(false);
  
  // New Assignment Form State
  const [newTitle, setNewTitle] = useState('');
  const [newDesc, setNewDesc] = useState('');
  const [newDueDate, setNewDueDate] = useState('');
  const [newMaxScore, setNewMaxScore] = useState(100);
  const [creating, setCreating] = useState(false);
  
  // AI Generation State
  const [lectures, setLectures] = useState<any[]>([]);
  const [selectedLecture, setSelectedLecture] = useState<string>('');
  const [subjectType, setSubjectType] = useState('technical');
  const [difficulty, setDifficulty] = useState('medium');
  const [generating, setGenerating] = useState(false);

  useEffect(() => {
    loadCourses();
  }, []);

  const loadCourses = async () => {
    try {
      const res = await coursesAPI.list();
      const data = Array.isArray(res.data) ? res.data : [];
      setCourses(data);
      if (data.length > 0) {
        setSelectedCourse(data[0].id);
        loadAssignments(data[0].id);
      } else {
        setLoading(false);
      }
    } catch (err) {
      console.error('Failed to load courses', err);
      setLoading(false);
    }
  };

  const loadAssignments = async (courseId: string) => {
    setDataLoading(true);
    try {
      const [assignRes, lectureRes] = await Promise.all([
        assignmentsAPI.getByCourse(courseId),
        lecturesAPI.getByCourse(courseId)
      ]);
      setAssignments(assignRes.data || []);
      setLectures(lectureRes.data || []);
      if (lectureRes.data?.length > 0) {
        setSelectedLecture(lectureRes.data[0].id);
      }
    } catch (err) {
      console.error('Failed to load assignments', err);
    } finally {
      setDataLoading(false);
      setLoading(false);
    }
  };

  const handleCreateAssignment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedCourse) return;
    
    setCreating(true);
    try {
      await assignmentsAPI.create({
        course_id: selectedCourse,
        title: newTitle,
        description: newDesc,
        due_date: newDueDate,
        max_score: newMaxScore
      });
      setShowCreateModal(false);
      setNewTitle('');
      setNewDesc('');
      setNewDueDate('');
      loadAssignments(selectedCourse);
    } catch (err) {
      console.error('Failed to create assignment', err);
      alert('Neural sync failure. Could not publish assignment node.');
    } finally {
      setCreating(false);
    }
  };

  const handleGenerateAI = async () => {
    if (!selectedLecture) {
      alert("Please select a lecture context first.");
      return;
    }
    setGenerating(true);
    try {
      const res = await assignmentsAPI.generateAI({
        lecture_id: selectedLecture,
        subject_type: subjectType,
        difficulty: difficulty
      });
      
      const data = res.data;
      setNewTitle(data.title);
      
      // Combine questions into instructions
      let fullDesc = data.description + "\n\n### ASSIGNMENT TASKS\n";
      data.questions.forEach((q: any, i: number) => {
        fullDesc += `\n${i+1}. [${q.points}pts] ${q.question}\n`;
      });
      setNewDesc(fullDesc);
      setNewMaxScore(data.max_score || 100);
      
    } catch (err: any) {
      console.error('AI Generation failed', err);
      alert(err.response?.data?.detail || "AI synthesis failed. The transcript neural link might be offline.");
    } finally {
      setGenerating(false);
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
      <main className="flex-1 ml-64 p-12 overflow-y-auto space-y-12 animate-fade-in relative z-10">
        
        {/* Background Ornament */}
        <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-primary/5 rounded-full blur-[120px] -z-10 pointer-events-none" />

        <header className="flex flex-col md:flex-row md:items-end justify-between gap-8">
           <div>
              <div className="text-[10px] uppercase tracking-[0.4em] font-black text-primary mb-2 flex items-center gap-2">
                 <Sparkles size={12} /> Curricular Node Deployment
              </div>
              <h1 className="text-7xl font-black tracking-tighter text-foreground leading-[0.9]">
                 Assignments.
              </h1>
           </div>
           <div className="flex items-center gap-4">
              <div className="flex flex-col gap-2">
                 <label className="text-[10px] font-black uppercase tracking-widest text-text-muted ml-1">Contextual Domain</label>
                 <select 
                   value={selectedCourse}
                   onChange={(e) => {
                     setSelectedCourse(e.target.value);
                     loadAssignments(e.target.value);
                   }}
                   className="bg-surface border border-border rounded-2xl py-3 px-6 text-sm font-bold outline-none focus:border-primary/40 transition-all cursor-pointer shadow-lg crimson-glow"
                 >
                   {courses.map(c => <option key={c.id} value={c.id}>{c.title}</option>)}
                 </select>
              </div>
              <button 
                onClick={() => setShowCreateModal(true)}
                className="mt-6 flex items-center gap-2 px-8 py-4 bg-primary text-white rounded-2xl font-black text-sm uppercase tracking-widest hover:scale-[1.02] active:scale-95 transition-all shadow-xl shadow-primary/20"
              >
                <Plus size={20} /> Deploy New Node
              </button>
           </div>
        </header>

        {dataLoading ? (
            <div className="flex-1 flex items-center justify-center h-[50vh]">
               <div className="text-center space-y-4">
                  <div className="w-12 h-12 border-4 border-primary/20 border-t-primary rounded-full animate-spin mx-auto" />
                  <p className="text-[10px] font-black uppercase tracking-[0.2em] text-primary">Fetching Assignment Grid...</p>
               </div>
            </div>
        ) : (
          <div className="grid grid-cols-12 gap-8">
            
            {/* Assignment List */}
            <div className="col-span-12 lg:col-span-8 space-y-6">
               <div className="flex items-center justify-between">
                  <h2 className="text-3xl font-black text-foreground flex items-center gap-3">
                     <FileText className="text-primary" /> Active Nodes
                  </h2>
                  <div className="text-[10px] font-black text-text-muted uppercase tracking-widest">{assignments.length} Assignments Synchronized</div>
               </div>
               
               <div className="space-y-4">
                 {assignments.length > 0 ? assignments.map((a, i) => (
                   <div key={i} className="glass-card p-8 flex flex-col md:flex-row md:items-center justify-between gap-6 group hover:border-primary/40 transition-all transition-transform hover:-translate-y-1">
                      <div className="flex items-center gap-6">
                         <div className="w-16 h-16 rounded-2xl bg-surface-alt flex items-center justify-center text-primary group-hover:bg-primary/10 transition-colors">
                            <BookOpen size={30} />
                         </div>
                         <div>
                            <h3 className="text-xl font-black text-foreground group-hover:text-primary transition-colors">{a.title}</h3>
                            <div className="flex items-center gap-4 mt-2">
                               <div className="flex items-center gap-1.5 text-xs font-bold text-text-muted">
                                  <Calendar size={14} className="text-primary" /> Due {new Date(a.due_date).toLocaleDateString()}
                               </div>
                               <div className="flex items-center gap-1.5 text-xs font-bold text-text-muted">
                                  <Award size={14} className="text-success" /> {a.max_score} pts
                               </div>
                            </div>
                         </div>
                      </div>
                      <div className="flex items-center gap-4">
                         <Link 
                           href={`/teacher/grading?assignment_id=${a.id}`}
                           className="px-6 py-3 bg-surface-alt border border-border rounded-xl text-[10px] font-black uppercase tracking-widest hover:border-primary/40 hover:text-primary transition-all flex items-center gap-2"
                         >
                            <Users size={14} /> Grade Sync
                         </Link>
                         <button className="p-3 text-text-muted hover:text-red-500 transition-colors"><Trash2 size={18} /></button>
                      </div>
                   </div>
                 )) : (
                   <div className="p-20 text-center border-2 border-dashed border-border rounded-[3rem] opacity-40">
                      <FileText size={80} className="mx-auto mb-6" />
                      <h3 className="text-2xl font-black italic">No assignments deployed to this neural cluster.</h3>
                   </div>
                 )}
               </div>
            </div>

            {/* Quick Stats Bento */}
            <div className="col-span-12 lg:col-span-4 space-y-8">
               <div className="glass-card p-8 space-y-8">
                  <div className="flex items-center justify-between">
                     <h3 className="text-xl font-black">Cluster Health</h3>
                     <Target className="text-primary" />
                  </div>
                  
                  <div className="space-y-6">
                     <div className="flex justify-between items-end">
                        <div className="space-y-1">
                           <div className="text-[10px] font-black text-text-muted uppercase tracking-widest">Average Completion</div>
                           <div className="text-3xl font-black text-foreground">68.4%</div>
                        </div>
                        <div className="w-24 h-1.5 bg-background rounded-full overflow-hidden">
                           <div className="h-full bg-primary rounded-full" style={{ width: '68%' }}></div>
                        </div>
                     </div>
                     
                     <div className="flex justify-between items-end">
                        <div className="space-y-1">
                           <div className="text-[10px] font-black text-text-muted uppercase tracking-widest">Grading Turnaround</div>
                           <div className="text-3xl font-black text-success">1.2d</div>
                        </div>
                        <div className="w-24 h-1.5 bg-background rounded-full overflow-hidden">
                           <div className="h-full bg-success rounded-full" style={{ width: '90%' }}></div>
                        </div>
                     </div>
                  </div>

                  <div className="p-6 bg-primary/5 rounded-2xl border border-primary/20 space-y-4">
                     <div className="text-[10px] font-black text-primary uppercase tracking-widest flex items-center gap-2">
                        <Sparkles size={12} /> Aika Sync Logic
                     </div>
                     <p className="text-xs font-bold text-text-muted leading-relaxed italic">
                        Deployment of "Higher-Order Calculus" node resulted in a 4.2% spike in global engagement density. Maintain current pacing.
                     </p>
                  </div>
               </div>
            </div>

          </div>
        )}

        {/* Create Assignment Modal */}
        {showCreateModal && (
          <div className="fixed inset-0 bg-background/90 backdrop-blur-3xl z-[500] flex items-center justify-center p-6">
            <div className="bg-surface border border-border w-full max-w-xl rounded-[3rem] overflow-hidden shadow-2xl animate-slide-up">
               <div className="p-10 border-b border-border bg-surface-alt/50 flex items-center justify-between">
                  <div className="flex items-center gap-4">
                     <div className="w-12 h-12 rounded-2xl bg-primary/10 flex items-center justify-center text-primary">
                        <Plus size={24} />
                     </div>
                     <h2 className="text-3xl font-black tracking-tighter">Deploy New Node</h2>
                  </div>
                  <button onClick={() => setShowCreateModal(false)} className="p-3 hover:bg-surface-alt border border-border rounded-xl transition-all"><XCircle size={24} /></button>
               </div>
               
               <div className="p-10 bg-primary/5 border-b border-border space-y-4">
                  <div className="flex items-center gap-2 text-[10px] font-black uppercase tracking-[0.3em] text-primary">
                     <Sparkles size={14} /> AI Magic Wand (Subject Aware)
                  </div>
                  <div className="grid grid-cols-12 gap-4">
                     <div className="col-span-6 space-y-2">
                        <label className="text-[10px] font-black uppercase tracking-widest text-text-muted ml-1">Lecture Context</label>
                        <select 
                          value={selectedLecture}
                          onChange={(e) => setSelectedLecture(e.target.value)}
                          className="w-full bg-surface border border-border rounded-xl p-3 text-xs font-bold outline-none"
                        >
                          {lectures.map(l => <option key={l.id} value={l.id}>{l.title}</option>)}
                        </select>
                     </div>
                     <div className="col-span-3 space-y-2">
                        <label className="text-[10px] font-black uppercase tracking-widest text-text-muted ml-1">Logic Pattern</label>
                        <select 
                          value={subjectType}
                          onChange={(e) => setSubjectType(e.target.value)}
                          className="w-full bg-surface border border-border rounded-xl p-3 text-xs font-bold outline-none"
                        >
                          <option value="technical">Technical</option>
                          <option value="descriptive">Descriptive</option>
                        </select>
                     </div>
                     <div className="col-span-3 flex items-end">
                        <button 
                          type="button"
                          onClick={handleGenerateAI}
                          disabled={generating}
                          className="w-full py-3 bg-foreground text-background rounded-xl font-black text-[10px] uppercase tracking-widest hover:scale-105 active:scale-95 transition-all disabled:opacity-50"
                        >
                          {generating ? 'SYNTHESIZING...' : 'GENERATE AI'}
                        </button>
                     </div>
                  </div>
               </div>

               <form onSubmit={handleCreateAssignment} className="p-10 space-y-6">
                  <div className="space-y-2">
                    <label className="text-[10px] font-black uppercase tracking-widest text-text-muted ml-1">Assignment Title</label>
                    <input 
                      required
                      value={newTitle}
                      onChange={(e) => setNewTitle(e.target.value)}
                      placeholder="e.g. Advanced Cognitive Synthesis"
                      className="w-full bg-background border border-border rounded-2xl p-4 text-sm font-bold outline-none focus:border-primary/40 transition-all"
                    />
                  </div>
                  
                  <div className="space-y-2">
                    <label className="text-[10px] font-black uppercase tracking-widest text-text-muted ml-1">Pedagogical Instructions</label>
                    <textarea 
                      required
                      value={newDesc}
                      onChange={(e) => setNewDesc(e.target.value)}
                      placeholder="Provide deep-level instructions for this curricular node..."
                      rows={4}
                      className="w-full bg-background border border-border rounded-2xl p-4 text-sm font-bold outline-none focus:border-primary/40 transition-all resize-none"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <label className="text-[10px] font-black uppercase tracking-widest text-text-muted ml-1">Synchronization Deadline</label>
                      <input 
                        required
                        type="date"
                        value={newDueDate}
                        onChange={(e) => setNewDueDate(e.target.value)}
                        className="w-full bg-background border border-border rounded-2xl p-4 text-sm font-bold filter invert dark:invert-0"
                      />
                    </div>
                    <div className="space-y-2">
                      <label className="text-[10px] font-black uppercase tracking-widest text-text-muted ml-1">Max Resonance Score</label>
                      <input 
                        required
                        type="number"
                        value={newMaxScore}
                        onChange={(e) => setNewMaxScore(parseInt(e.target.value))}
                        className="w-full bg-background border border-border rounded-2xl p-4 text-sm font-bold"
                      />
                    </div>
                  </div>

                  <button 
                    disabled={creating}
                    className="w-full py-6 bg-primary text-white rounded-2xl font-black text-xs uppercase tracking-widest hover:scale-[1.02] transition-all crimson-glow shadow-xl disabled:opacity-50"
                  >
                    {creating ? 'Synchronizing Neural Link...' : 'Publish to Course Grid'}
                  </button>
               </form>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
