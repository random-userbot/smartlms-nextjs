'use client';

import React, { useState, useEffect } from 'react';
import { 
  FileText, 
  Calendar, 
  CheckCircle2, 
  Clock, 
  Upload, 
  AlertCircle,
  ExternalLink,
  ChevronRight,
  Plus,
  X
} from 'lucide-react';
import { assignmentsAPI, coursesAPI } from '@/lib/api';
import { useAuth } from '@/context/AuthContext';
import Sidebar from '@/components/Sidebar';
import { uploadFile } from '@/lib/cloudinary';

export default function AssignmentsPage() {
  const { user } = useAuth();
  const [courses, setCourses] = useState<any[]>([]);
  const [assignments, setAssignments] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedAssignment, setSelectedAssignment] = useState<any>(null);
  const [submissionText, setSubmissionText] = useState('');
  const [submissionFile, setSubmissionFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const coursesRes = await coursesAPI.getMyCourses();
      const myCourses = coursesRes.data;
      setCourses(myCourses);

      const allAssignments: any[] = [];
      for (const course of myCourses) {
        const assignRes = await assignmentsAPI.getByCourse(course.course_id);
        const courseAssigns = assignRes.data.map((a: any) => ({ ...a, course_title: course.title }));
        allAssignments.push(...courseAssigns);
      }
      setAssignments(allAssignments.sort((a, b) => new Date(a.due_date || 0).getTime() - new Date(b.due_date || 0).getTime()));
    } catch (err) {
      console.error('Failed to load assignments', err);
    } finally {
      setLoading(false);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setSubmissionFile(e.target.files[0]);
    }
  };

  const handleSubmit = async () => {
    if (!selectedAssignment || submitting) return;
    setSubmitting(true);
    try {
      let fileUrl = '';
      if (submissionFile) {
        fileUrl = await uploadFile(submissionFile);
      }

      await assignmentsAPI.submit({
        assignment_id: selectedAssignment.id,
        text: submissionText,
        file_url: fileUrl,
      });

      setSelectedAssignment(null);
      setSubmissionText('');
      setSubmissionFile(null);
      alert('Assignment submitted successfully!');
    } catch (err) {
      console.error('Submission failed', err);
      alert('Submission failed. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-screen bg-background">
        <Sidebar />
        <main className="flex-1 ml-64 p-8 flex items-center justify-center">
          <div className="w-12 h-12 border-4 border-primary/20 border-t-primary rounded-full animate-spin" />
        </main>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-background text-white selection:bg-primary/30">
      <Sidebar />
      
      <main className="flex-1 ml-64 p-8 md:p-12">
        <div className="max-w-6xl mx-auto">
          <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 mb-12">
            <div>
              <h1 className="text-4xl font-black tracking-tight mb-3">Assignments</h1>
              <p className="text-text-muted font-medium text-lg">Manage your coursework and track submission deadlines.</p>
            </div>
            <div className="flex items-center gap-3">
              <span className="px-4 py-2 bg-white/5 rounded-xl border border-white/5 text-xs font-bold text-text-muted uppercase tracking-widest">
                Total: {assignments.length}
              </span>
            </div>
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
            {assignments.length === 0 ? (
              <div className="col-span-full p-20 text-center glass-premium rounded-[2.5rem] border border-white/5">
                <FileText size={64} className="mx-auto mb-6 opacity-20" />
                <h3 className="text-2xl font-black">No assignments found</h3>
                <p className="text-text-muted mt-2 font-medium">You don't have any pending assignments at the moment.</p>
              </div>
            ) : (
              assignments.map((assignment) => {
                const isOverdue = assignment.due_date && new Date(assignment.due_date) < new Date();
                
                return (
                  <div 
                    key={assignment.id}
                    onClick={() => setSelectedAssignment(assignment)}
                    className="group glass-premium border border-white/5 p-8 rounded-[2rem] hover:border-primary/30 hover:shadow-lg transition-all cursor-pointer flex flex-col h-full bg-surface/40"
                  >
                    <div className="flex items-start justify-between gap-4 mb-6">
                      <div className="w-14 h-14 rounded-2xl bg-white/5 flex items-center justify-center text-primary group-hover:scale-110 transition-transform border border-white/5 shrink-0">
                        <FileText size={24} />
                      </div>
                      <div className={`px-4 py-1.5 rounded-full text-[10px] font-black uppercase tracking-widest border ${isOverdue ? 'bg-red-500/10 text-red-500 border-red-500/20' : 'bg-primary/10 text-primary border-primary/20'}`}>
                        {isOverdue ? 'Overdue' : 'Due Soon'}
                      </div>
                    </div>
                    
                    <h3 className="text-xl font-black mb-2 line-clamp-1">{assignment.title}</h3>
                    <p className="text-[10px] font-bold text-primary uppercase tracking-widest mb-4 flex items-center gap-1.5">
                      <Calendar size={12} /> {assignment.course_title}
                    </p>
                    <p className="text-sm text-text-muted line-clamp-3 leading-relaxed mb-8 flex-1">
                      {assignment.description || 'No description provided.'}
                    </p>
                    
                    <div className="pt-6 border-t border-white/5 flex items-center justify-between mt-auto">
                      <div className="flex flex-col">
                        <span className="text-[10px] font-black uppercase tracking-widest text-text-muted mb-1">Due Date</span>
                        <span className="text-sm font-bold text-white">
                          {assignment.due_date ? new Date(assignment.due_date).toLocaleDateString() : 'No deadline'}
                        </span>
                      </div>
                      <div className="w-10 h-10 rounded-full bg-white/5 flex items-center justify-center group-hover:bg-primary group-hover:text-white transition-all">
                        <ChevronRight size={20} />
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      </main>

      {/* Submission Modal */}
      {selectedAssignment && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[100] flex items-center justify-center p-4">
          <div className="bg-surface border border-white/10 w-full max-w-2xl rounded-[2.5rem] overflow-hidden shadow-2xl animate-in fade-in zoom-in duration-300 flex flex-col max-h-[90vh]">
            <div className="p-8 border-b border-white/5 flex items-center justify-between shrink-0">
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 rounded-2xl bg-primary/10 flex items-center justify-center text-primary">
                  <Upload size={24} />
                </div>
                <div>
                  <h2 className="text-2xl font-black">Submit assignment</h2>
                  <p className="text-[10px] font-black text-primary uppercase tracking-widest mt-1">{selectedAssignment.course_title}</p>
                </div>
              </div>
              <button 
                onClick={() => setSelectedAssignment(null)}
                className="p-3 hover:bg-white/5 rounded-xl border border-white/5 text-text-muted hover:text-white transition-all"
              >
                <X size={24} />
              </button>
            </div>
            
            <div className="p-8 overflow-y-auto space-y-8">
              <div>
                <h3 className="text-xl font-bold mb-3">{selectedAssignment.title}</h3>
                <p className="text-sm text-text-muted leading-relaxed font-medium">
                  {selectedAssignment.description}
                </p>
                {selectedAssignment.file_url && (
                  <a 
                    href={selectedAssignment.file_url} 
                    target="_blank" 
                    rel="noreferrer"
                    className="inline-flex items-center gap-2 mt-4 text-xs font-black uppercase tracking-widest text-primary hover:underline"
                  >
                    <ExternalLink size={14} /> Download Instructions
                  </a>
                )}
              </div>

              <div className="space-y-4">
                <label className="text-[10px] font-black uppercase tracking-widest text-text-muted">Submission details</label>
                <textarea
                  value={submissionText}
                  onChange={(e) => setSubmissionText(e.target.value)}
                  placeholder="Paste your submission or add notes..."
                  className="w-full px-6 py-4 bg-white/5 border border-white/10 rounded-2xl focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none transition-all h-32 resize-none placeholder:text-text-muted"
                />
              </div>

              <div className="space-y-4">
                <label className="text-[10px] font-black uppercase tracking-widest text-text-muted">Attach file</label>
                <div className="relative">
                  <input
                    type="file"
                    onChange={handleFileChange}
                    className="hidden"
                    id="assign-file"
                  />
                  <label 
                    htmlFor="assign-file"
                    className="flex flex-col items-center justify-center w-full p-8 bg-white/5 border-2 border-dashed border-white/10 rounded-2xl cursor-pointer hover:bg-white/10 hover:border-primary/30 transition-all group"
                  >
                    <div className="w-12 h-12 bg-white/10 rounded-xl flex items-center justify-center mb-3 group-hover:scale-110 transition-transform">
                      <Plus size={24} />
                    </div>
                    <span className="text-sm font-bold">{submissionFile ? submissionFile.name : 'Click to select or drag and drop'}</span>
                    <span className="text-[10px] text-text-muted font-black uppercase tracking-widest mt-1">PDF, DOCX, Or Source Files (Max 10MB)</span>
                  </label>
                </div>
              </div>
            </div>

            <div className="p-8 border-t border-white/5 shrink-0">
              <button 
                onClick={handleSubmit}
                disabled={(!submissionText && !submissionFile) || submitting}
                className="w-full py-5 bg-primary text-white font-black rounded-2xl transition-all crimson-glow disabled:opacity-40 disabled:scale-100 hover:scale-[1.02] active:scale-95 shadow-lg"
              >
                {submitting ? 'Initiating Secure Upload...' : 'Submit Assignment'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
