'use client';

import React, { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { assignmentsAPI, lecturesAPI } from '@/lib/api';
import { 
  FileText, 
  Upload, 
  CheckCircle, 
  AlertCircle, 
  ArrowLeft,
  Loader2,
  BrainCircuit,
  Eye,
  Send,
  Save,
  Clock,
  ExternalLink
} from 'lucide-react';
import Sidebar from '@/components/Sidebar';

export default function AssignmentWorkspacePage() {
  const { id: assignmentId } = useParams();
  const router = useRouter();
  
  const [assignment, setAssignment] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [uploading, setUploading] = useState(false);
  
  // Submission State
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [answers, setAnswers] = useState<any[]>([]);
  const [generalComment, setGeneralComment] = useState('');
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    assignmentsAPI.get(assignmentId as string)
      .then(res => {
        setAssignment(res.data);
        // Initialize structured answers if questions exist
        if (res.data.questions && Array.isArray(res.data.questions)) {
          setAnswers(res.data.questions.map((q: any) => ({
            question: q.question,
            points: q.points,
            answer: ''
          })));
        }
      })
      .catch(err => console.error("Assignment Load Error:", err))
      .finally(() => setLoading(false));
  }, [assignmentId]);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    try {
      // Use lecturesAPI.uploadMaterial as a generic S3 uploader for now
      // assuming backend treats folder 'assignments' correctly
      const res = await lecturesAPI.uploadMaterial(
        assignment.course_id, 
        `Submission_${assignment.title}`, 
        'pdf', 
        file
      );
      setPdfUrl(res.data.file_url);
    } catch (err) {
      console.error("Upload failed:", err);
    } finally {
      setUploading(false);
    }
  };

  const handleSubmit = async () => {
    setSubmitting(true);
    try {
      await assignmentsAPI.submit({
        assignment_id: assignmentId,
        file_url: pdfUrl,
        text: generalComment,
        structured_answers: answers
      });
      setSuccess(true);
      setTimeout(() => router.push('/assignments'), 2000);
    } catch (err) {
      console.error("Submission failed:", err);
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return (
    <div className="flex items-center justify-center min-h-screen bg-background">
      <Loader2 className="animate-spin text-primary" size={48} />
    </div>
  );

  if (!assignment) return <div>Assignment not found.</div>;

  return (
    <div className="flex h-screen bg-background overflow-hidden">
      <Sidebar />
      
      <main className="flex-1 flex flex-col ml-64">
        {/* Workspace Nav */}
        <nav className="h-20 border-b border-border bg-surface/50 backdrop-blur-md flex items-center justify-between px-10 shrink-0">
          <div className="flex items-center gap-6">
            <button 
              onClick={() => router.back()}
              className="p-3 bg-white/5 rounded-xl hover:bg-white/10 transition-all text-text-muted"
            >
              <ArrowLeft size={18} />
            </button>
            <div>
              <div className="text-[8px] uppercase tracking-[0.3em] font-black text-primary">Academic Workspace</div>
              <h1 className="text-xl font-black text-white">{assignment.title}</h1>
            </div>
          </div>
          
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-3 px-4 py-2 bg-warning/10 rounded-full border border-warning/20">
              <Clock size={14} className="text-warning" />
              <span className="text-[10px] font-black text-warning uppercase tracking-widest">
                Due: {assignment.due_date ? new Date(assignment.due_date).toLocaleDateString() : 'No Limit'}
              </span>
            </div>
            <button 
              onClick={handleSubmit}
              disabled={submitting || success}
              className={`px-8 py-3 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all ${success ? 'bg-success text-white' : 'bg-primary text-white crimson-glow'}`}
            >
              {submitting ? <Loader2 className="animate-spin" size={16} /> : success ? 'Submitted!' : 'Submit Solution'}
            </button>
          </div>
        </nav>

        {/* HUD Content */}
        <div className="flex-1 flex overflow-hidden">
          
          {/* Left: Intelligence Pane (PDF/Instructions) */}
          <section className="w-1/2 border-r border-border bg-black/20 flex flex-col p-8 gap-8 overflow-y-auto custom-scrollbar">
             <div className="flex items-center justify-between mb-4">
               <h3 className="text-sm font-black text-white uppercase tracking-widest flex items-center gap-3">
                 <Eye size={16} className="text-primary" /> Reference Material
               </h3>
               {assignment.file_url && (
                  <a href={assignment.file_url} target="_blank" className="text-[10px] font-black text-primary uppercase tracking-widest hover:underline flex items-center gap-2">
                    <ExternalLink size={12} /> External View
                  </a>
               )}
             </div>

             {assignment.render_url ? (
               <div className="flex-1 w-full bg-surface-alt rounded-3xl border border-white/5 overflow-hidden shadow-2xl min-h-[600px]">
                 <iframe 
                   src={assignment.render_url} 
                   className="w-full h-full border-none"
                   title="PDF Viewer"
                 />
               </div>
             ) : (
               <div className="flex-1 flex flex-col items-center justify-center glass-card border-dashed border-white/10 p-12 text-center">
                 <FileText size={80} className="text-white/5 mb-6" />
                 <h4 className="text-xl font-bold text-text-muted">No visual reference provided.</h4>
                 <p className="text-xs text-text-muted mt-2 max-w-xs">{assignment.description || "Refer to the question bank below for instructions."}</p>
               </div>
             )}

             {assignment.description && !assignment.render_url && (
               <div className="glass-card p-10 space-y-4">
                  <h4 className="text-xs font-black text-primary uppercase tracking-widest">Description</h4>
                  <p className="text-sm text-text-muted leading-relaxed font-medium whitespace-pre-wrap">{assignment.description}</p>
               </div>
             )}
          </section>

          {/* Right: Submission Pane */}
          <section className="w-1/2 bg-background flex flex-col overflow-y-auto custom-scrollbar p-12 gap-12">
            
            {/* Phase 1: Artifact Upload */}
            <div className="space-y-6">
              <div className="flex items-center gap-4">
                <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center text-primary font-black text-xs">01</div>
                <h3 className="text-xs font-black text-white uppercase tracking-[0.2em]">Evidence Submission (PDF First)</h3>
              </div>
              
              <div className={`relative flex flex-col items-center justify-center p-12 border-2 border-dashed rounded-3xl transition-all ${pdfUrl ? 'border-success/40 bg-success/5' : 'border-white/10 hover:border-primary/40 bg-surface/50'}`}>
                {uploading ? (
                  <Loader2 className="animate-spin text-primary" size={40} />
                ) : pdfUrl ? (
                  <div className="text-center space-y-4">
                    <CheckCircle className="text-success mx-auto" size={48} />
                    <div>
                      <h4 className="text-lg font-black text-white">Solution Artifact Locked</h4>
                      <p className="text-[10px] text-success font-black uppercase tracking-widest">Successfully Uploaded to Forensic Hub</p>
                    </div>
                  </div>
                ) : (
                  <>
                    <Upload className="text-primary/40 mb-6" size={48} />
                    <div className="text-center space-y-2">
                       <h4 className="font-black text-white">Drop your PDF solution here</h4>
                       <p className="text-[10px] text-text-muted font-bold uppercase tracking-widest">Required for Semantic AI Grading</p>
                    </div>
                    <input 
                      type="file" 
                      onChange={handleFileUpload} 
                      className="absolute inset-0 opacity-0 cursor-pointer" 
                      accept=".pdf"
                    />
                  </>
                )}
              </div>
            </div>

            {/* Phase 2: Structural Inputs */}
            {answers.length > 0 && (
              <div className="space-y-10">
                <div className="flex items-center gap-4">
                  <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center text-primary font-black text-xs">02</div>
                  <h3 className="text-xs font-black text-white uppercase tracking-[0.2em]">Question Matrix</h3>
                </div>

                <div className="space-y-8">
                  {answers.map((q, idx) => (
                    <div key={idx} className="glass-card p-10 space-y-6 focus-within:border-primary/40 transition-all">
                      <div className="flex justify-between items-start">
                        <h4 className="text-sm font-black text-white leading-relaxed max-w-[80%]">{idx + 1}. {q.question}</h4>
                        <span className="text-[10px] font-black text-primary bg-primary/10 px-3 py-1.5 rounded-full uppercase tracking-widest">{q.points} Pts</span>
                      </div>
                      <textarea 
                        value={q.answer}
                        onChange={(e) => {
                          const newAnswers = [...answers];
                          newAnswers[idx].answer = e.target.value;
                          setAnswers(newAnswers);
                        }}
                        placeholder="Type your structured solution here..."
                        className="w-full bg-black/20 border border-white/5 rounded-2xl p-6 text-sm font-medium text-white focus:outline-none focus:border-primary/40 min-h-[150px] transition-all"
                      />
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Phase 3: Final Consolidation */}
            <div className="space-y-6 pb-20">
               <div className="flex items-center gap-4">
                <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center text-primary font-black text-xs">03</div>
                <h3 className="text-xs font-black text-white uppercase tracking-[0.2em]">Final Intelligence Narrative</h3>
              </div>
              <textarea 
                value={generalComment}
                onChange={(e) => setGeneralComment(e.target.value)}
                placeholder="Any additional insights or context for the evaluator?"
                className="w-full bg-surface border border-border rounded-3xl p-10 text-sm font-medium text-white focus:outline-none focus:border-primary/40 min-h-[200px] shadow-2xl"
              />
            </div>

          </section>
        </div>
      </main>
      
      {/* Aika Orbit Support */}
      <div className="fixed bottom-10 right-10 flex flex-col items-end gap-4 pointer-events-none">
         <div className="glass-card p-6 bg-primary crimson-glow text-white animate-bounce pointer-events-auto cursor-pointer">
            <BrainCircuit size={24} />
         </div>
      </div>
    </div>
  );
}
