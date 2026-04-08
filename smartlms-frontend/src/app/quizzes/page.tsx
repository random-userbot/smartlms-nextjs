'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { 
  Zap, 
  Search, 
  Filter, 
  ChevronRight, 
  Clock, 
  Trophy, 
  Play, 
  CheckCircle2, 
  AlertCircle,
  Brain,
  Video
} from 'lucide-react';
import { quizzesAPI } from '@/lib/api';
import NavigationHeader from '@/components/NavigationHeader';
import Sidebar from '@/components/Sidebar';

export default function StudentQuizzesPage() {
  const [quizzes, setQuizzes] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [filter, setFilter] = useState<'all' | 'completed' | 'pending'>('all');

  useEffect(() => {
    fetchQuizzes();
  }, []);

  const fetchQuizzes = async () => {
    try {
      const res = await quizzesAPI.listMine();
      setQuizzes(res.data || []);
    } catch (err) {
      console.error("Failed to fetch quizzes:", err);
    } finally {
      setLoading(false);
    }
  };

  const filteredQuizzes = quizzes.filter(q => {
    const matchesSearch = q.title.toLowerCase().includes(searchQuery.toLowerCase()) || 
                         q.course_title?.toLowerCase().includes(searchQuery.toLowerCase());
    
    if (filter === 'completed') return matchesSearch && (q.attempt_count > 0);
    if (filter === 'pending') return matchesSearch && (q.attempt_count === 0);
    return matchesSearch;
  });

  return (
    <div className="flex h-screen bg-background overflow-hidden relative">
      <Sidebar />
      
      <main className="flex-1 ml-64 flex flex-col min-w-0 relative">
        <NavigationHeader title="Neural Assessment Hub" />
        
        <div className="flex-1 overflow-y-auto p-8 lg:p-12 space-y-12 no-scrollbar">
          
          <header className="flex flex-col md:flex-row md:items-end justify-between gap-8">
            <div className="flex flex-col">
              <div className="text-[10px] font-black uppercase tracking-[0.3em] mb-2 text-primary flex items-center gap-2">
                <Zap size={12} className="crimson-glow" /> Cognitive Checkpoints
              </div>
              <h1 className="text-4xl font-black text-foreground tracking-tighter">Your Quiz Catalog</h1>
              <p className="text-text-muted font-bold mt-2 max-w-xl">
                Retake quizzes from past lectures or dive into new assessments to reinforce your neural connections.
              </p>
            </div>

            <div className="flex items-center gap-4">
               <div className="flex bg-surface-alt p-1 rounded-2xl border border-border shadow-sm">
                 {(['all', 'pending', 'completed'] as const).map(f => (
                   <button 
                     key={f}
                     onClick={() => setFilter(f)}
                     className={`px-6 py-2.5 rounded-xl text-xs font-black uppercase tracking-widest transition-all ${filter === f ? 'bg-primary text-white crimson-glow' : 'text-text-muted hover:bg-surface'}`}
                   >
                     {f}
                   </button>
                 ))}
               </div>
            </div>
          </header>

          {/* Search Bar */}
          <div className="relative group max-w-2xl">
            <div className="absolute inset-y-0 left-6 flex items-center pointer-events-none text-text-muted group-focus-within:text-primary transition-colors">
              <Search size={20} />
            </div>
            <input 
              type="text"
              placeholder="Filter by lecture title or course..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              className="w-full bg-surface border-border border rounded-[2rem] pl-16 pr-8 py-5 text-sm font-bold placeholder:text-text-muted focus:ring-4 focus:ring-primary/10 transition-all outline-none"
            />
          </div>

          {loading ? (
             <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-8 animate-pulse">
               {[1,2,3,4,5,6].map(i => (
                 <div key={i} className="h-64 bg-surface rounded-[2.5rem] border border-border" />
               ))}
             </div>
          ) : filteredQuizzes.length === 0 ? (
             <div className="flex flex-col items-center justify-center p-20 glass-card border-dashed">
                <AlertCircle size={48} className="text-text-muted mb-4" />
                <h3 className="text-xl font-bold text-foreground">No quizzes synchronized</h3>
                <p className="text-text-muted mt-2">Try adjusting your filters or search query.</p>
             </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-8 pb-12">
              {filteredQuizzes.map((quiz) => (
                <div key={quiz.id} className="group glass-card border-white/5 hover:border-primary/20 transition-all duration-500 overflow-hidden flex flex-col h-full bg-surface hover:bg-surface-alt rounded-[2.5rem] shadow-xl">
                  {/* Top Progress / Score Header */}
                  <div className="p-8 pb-0 flex items-center justify-between">
                     <div className="px-4 py-1.5 bg-primary/10 rounded-full text-[10px] font-black text-primary uppercase tracking-widest border border-primary/20">
                        {quiz.course_title || 'General'}
                     </div>
                     {quiz.attempt_count > 0 && (
                        <div className="flex items-center gap-1.5 text-success font-black text-sm">
                           <Trophy size={14} />
                           {quiz.best_percentage}%
                        </div>
                     )}
                  </div>

                  <div className="p-8 flex-1 flex flex-col">
                    <h3 className="text-2xl font-black text-foreground tracking-tighter line-clamp-2 leading-tight mb-4 group-hover:text-primary transition-colors">
                      {quiz.title}
                    </h3>

                    <div className="space-y-4 mb-8">
                       <div className="flex items-center gap-3 text-text-muted">
                          <Video size={16} className="text-primary/60" />
                          <span className="text-xs font-bold truncate">{quiz.lecture_title}</span>
                       </div>
                       <div className="flex items-center gap-3 text-text-muted">
                          <Clock size={16} className="text-primary/60" />
                          <span className="text-xs font-bold">{Math.round(quiz.time_limit / 60)} Minutes Neural Window</span>
                       </div>
                    </div>

                    <div className="mt-auto space-y-4">
                       <div className="bg-background/50 rounded-2xl border border-border p-4 flex items-center justify-between">
                          <div className="flex flex-col">
                             <span className="text-[10px] font-black text-text-muted uppercase tracking-widest">History</span>
                             <span className="text-sm font-bold text-foreground">{quiz.attempt_count} Attempts</span>
                          </div>
                          {quiz.lecture_watched ? (
                             <div className="w-10 h-10 rounded-xl bg-success/10 text-success flex items-center justify-center border border-success/20">
                                <CheckCircle2 size={20} />
                             </div>
                          ) : (
                             <div className="w-10 h-10 rounded-xl bg-orange-400/10 text-orange-400 flex items-center justify-center border border-orange-400/20" title="Lecture engagement recommended">
                                <Brain size={20} />
                             </div>
                          )}
                       </div>

                       <Link href={`/quizzes/${quiz.id}`} className="flex items-center justify-between px-8 py-5 bg-foreground text-background rounded-2xl group/btn hover:bg-primary hover:text-white transition-all crimson-glow-hover active:scale-95">
                          <span className="font-black uppercase tracking-widest text-xs">
                             {quiz.attempt_count > 0 ? 'Retake Alignment' : 'Initiate Sync'}
                          </span>
                          <Play size={16} fill="currentColor" className="transition-transform group-hover/btn:translate-x-1" />
                       </Link>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
