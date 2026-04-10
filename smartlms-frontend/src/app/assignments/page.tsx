'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { 
  FileText, 
  Calendar, 
  ChevronRight,
  Loader2,
  Sparkles,
  Search,
  BookOpen
} from 'lucide-react';
import { assignmentsAPI, coursesAPI } from '@/lib/api';
import Sidebar from '@/components/Sidebar';

export default function AssignmentsPage() {
  const router = useRouter();
  const [courses, setCourses] = useState<any[]>([]);
  const [assignments, setAssignments] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

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
        try {
          const assignRes = await assignmentsAPI.getByCourse(course.course_id);
          const courseAssigns = assignRes.data.map((a: any) => ({ 
            ...a, 
            course_title: course.title,
            course_thumbnail: course.thumbnail_url 
          }));
          allAssignments.push(...courseAssigns);
        } catch (e) {
          console.warn(`Could not load assignments for course ${course.course_id}`);
        }
      }
      setAssignments(allAssignments.sort((a, b) => new Date(a.due_date || 0).getTime() - new Date(b.due_date || 0).getTime()));
    } catch (err) {
      console.error('Failed to load assignments', err);
    } finally {
      setLoading(false);
    }
  };

  const filteredAssignments = assignments.filter(a => 
    a.title.toLowerCase().includes(search.toLowerCase()) || 
    a.course_title.toLowerCase().includes(search.toLowerCase())
  );

  if (loading) {
    return (
      <div className="flex min-h-screen bg-background">
        <Sidebar />
        <main className="flex-1 ml-64 p-8 flex items-center justify-center">
          <Loader2 className="animate-spin text-primary" size={48} />
        </main>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-background text-white selection:bg-primary/30">
      <Sidebar />
      
      <main className="flex-1 ml-64 p-12 space-y-12">
        <div className="max-w-7xl mx-auto space-y-12">
          
          {/* Header Section */}
          <header className="flex flex-col md:flex-row md:items-end justify-between gap-8 border-b border-border pb-12">
            <div>
              <div className="text-[10px] uppercase tracking-[0.4em] font-black text-primary mb-2">Academic Assessment Center</div>
              <h1 className="text-6xl font-black tracking-tighter text-white">Work Assignments.</h1>
              <p className="text-text-muted font-bold mt-4 max-w-xl text-lg opacity-80">
                Track your active intelligence requests and submit your findings to the Forensic S3 Repository.
              </p>
            </div>
            
            <div className="flex items-center gap-6">
               <div className="relative group min-w-[300px]">
                  <Search size={16} className="absolute left-6 top-1/2 -translate-y-1/2 text-text-muted group-focus-within:text-primary transition-all" />
                  <input 
                    type="text"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    placeholder="Search tasks..."
                    className="w-full bg-surface border border-border rounded-2xl pl-16 pr-6 py-4 text-xs font-black uppercase tracking-widest text-white focus:outline-none focus:border-primary/40 transition-all shadow-xl"
                  />
               </div>
               <div className="glass-card px-8 py-4 flex flex-col items-center">
                  <span className="text-[10px] font-black uppercase tracking-widest text-text-muted">Active</span>
                  <span className="text-2xl font-black text-primary">{assignments.length}</span>
               </div>
            </div>
          </header>

          {/* Grid View */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            {filteredAssignments.length === 0 ? (
              <div className="col-span-full py-40 text-center glass-card bg-primary/5 border-dashed border-primary/20">
                <FileText size={80} className="mx-auto mb-8 text-primary/10" />
                <h3 className="text-3xl font-black text-white uppercase tracking-tighter">No Active Requests</h3>
                <p className="text-text-muted font-bold">Your assessment queue is currently verified and clear.</p>
              </div>
            ) : (
              filteredAssignments.map((assignment) => {
                const isOverdue = assignment.due_date && new Date(assignment.due_date) < new Date();
                
                return (
                  <div 
                    key={assignment.id}
                    onClick={() => router.push(`/assignments/${assignment.id}`)}
                    className="group glass-card p-10 cursor-pointer hover:border-primary/40 hover:shadow-2xl transition-all relative overflow-hidden"
                  >
                    <Sparkles className="absolute -right-10 -bottom-10 text-primary/5 group-hover:scale-110 transition-transform duration-700" size={200} />
                    
                    <div className="flex items-start justify-between mb-8">
                       <div className="w-16 h-16 rounded-2xl bg-surface-alt border border-white/5 flex items-center justify-center text-primary group-hover:crimson-glow transition-all">
                          <FileText size={28} />
                       </div>
                       <div className={`px-4 py-2 rounded-full text-[9px] font-black uppercase tracking-[0.2em] border ${isOverdue ? 'bg-red-500/10 text-red-500 border-red-500/20' : 'bg-primary/10 text-primary border-primary/20 animate-pulse'}`}>
                          {isOverdue ? 'Deadline Passed' : 'Assessment Active'}
                       </div>
                    </div>
                    
                    <div className="space-y-4 mb-10">
                       <h3 className="text-2xl font-black text-white group-hover:text-primary transition-colors leading-tight">{assignment.title}</h3>
                       <div className="flex items-center gap-3">
                          <div className="w-6 h-6 rounded-full bg-white/5 overflow-hidden border border-white/10 flex items-center justify-center">
                             {assignment.course_thumbnail ? <img src={assignment.course_thumbnail} alt="" className="w-full h-full object-cover" /> : <BookOpen size={10} />}
                          </div>
                          <span className="text-[10px] font-black text-text-muted uppercase tracking-[0.2em]">{assignment.course_title}</span>
                       </div>
                    </div>
                    
                    <p className="text-sm text-text-muted font-medium line-clamp-3 leading-relaxed mb-10 opacity-70">
                       {assignment.description || "Comprehensive technical assessment requiring architectural analysis and structured implementation narratives."}
                    </p>
                    
                    <div className="pt-8 border-t border-white/5 flex items-center justify-between">
                       <div className="space-y-1">
                          <div className="text-[8px] font-black text-text-muted uppercase tracking-widest">Submission Window</div>
                          <div className="text-sm font-black text-white">
                             {assignment.due_date ? new Date(assignment.due_date).toLocaleDateString() : 'Continuous'}
                          </div>
                       </div>
                       <div className="flex items-center gap-4 text-xs font-black uppercase tracking-widest text-primary opacity-0 group-hover:opacity-100 transition-all group-hover:translate-x-0 translate-x-4">
                          Enter Workspace <ChevronRight size={16} />
                       </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
