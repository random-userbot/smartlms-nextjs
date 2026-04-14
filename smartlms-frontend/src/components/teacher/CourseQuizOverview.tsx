'use client';

import React, { useState, useEffect } from 'react';
import { quizzesAPI } from '@/lib/api';
import { 
  BarChart3, 
  Target, 
  AlertTriangle, 
  HelpCircle, 
  CheckCircle2, 
  Users,
  TrendingDown,
  ArrowRight
} from 'lucide-react';
import { motion } from 'framer-motion';

interface QuizStat {
  id: string;
  title: string;
  lecture: string;
  avg_score: number;
  attempt_count: number;
}

interface DifficultQuestion {
  question: string;
  success_rate: number;
  total_attempts: number;
}

interface QuizAnalytics {
  quizzes: QuizStat[];
  difficult_questions: DifficultQuestion[];
  avg_course_score: number;
}

export default function CourseQuizOverview({ courseId }: { courseId: string }) {
  const [data, setData] = useState<QuizAnalytics | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!courseId) return;
    setLoading(true);
    // Note: We need to add this to quizzesAPI in api.ts
    (quizzesAPI as any).getCourseAnalytics(courseId)
      .then((res: any) => setData(res.data))
      .catch((err: any) => console.error("Quiz analytics failed", err))
      .finally(() => setLoading(false));
  }, [courseId]);

  if (loading) {
    return (
      <div className="w-full h-80 flex flex-col items-center justify-center space-y-4 bg-surface/20 rounded-[2.5rem] border border-white/5 animate-pulse">
        <div className="w-10 h-10 border-4 border-primary/20 border-t-primary rounded-full animate-spin" />
        <div className="text-[10px] font-black text-text-muted uppercase tracking-[0.4em]">Aggregating Class Results...</div>
      </div>
    );
  }

  if (!data || !data.quizzes || data.quizzes.length === 0) {
    return (
      <div className="w-full p-12 text-center bg-surface/20 rounded-[2.5rem] border border-white/5 space-y-4">
        <div className="w-16 h-16 bg-white/5 rounded-3xl flex items-center justify-center mx-auto">
          <HelpCircle size={32} className="text-white/20" />
        </div>
        <div className="space-y-1">
          <h3 className="text-lg font-black text-foreground uppercase tracking-widest">No Quiz Data Recorded</h3>
          <p className="text-xs text-text-muted max-w-xs mx-auto italic">Pedagogical challenges have been assigned, but no students have finalized their attempts yet.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-10 animate-fade-in">
      {/* Overview Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
         <div className="glass-card p-8 border-primary/20 bg-primary/5">
            <div className="flex items-center gap-4 mb-4">
               <div className="p-3 bg-primary/20 rounded-2xl"><Users className="text-primary" size={24} /></div>
               <div>
                  <div className="text-[9px] font-black text-text-muted uppercase tracking-widest">Class Average</div>
                  <div className="text-3xl font-black text-foreground">{data.avg_course_score}%</div>
               </div>
            </div>
            <div className="h-1 w-full bg-white/5 rounded-full overflow-hidden">
               <div className="h-full bg-primary crimson-glow" style={{ width: `${data.avg_course_score}%` }} />
            </div>
         </div>

         <div className="col-span-2 glass-card p-8 border-white/5 bg-surface/40 flex items-center justify-between">
            <div className="space-y-4">
               <div>
                  <div className="text-[9px] font-black text-text-muted uppercase tracking-widest">Pedagogical Health</div>
                  <p className="text-xs text-text-muted mt-1 max-w-md italic">
                     {data.avg_course_score > 80 ? "Class demonstrates mastery. Consider increasing cognitive complexity." : 
                      data.avg_course_score > 60 ? "Stable progress. Some friction detected in abstract topics." : 
                      "Significant pedagogical resistance. Reviewing prerequisites recommended."}
                  </p>
               </div>
            </div>
            <div className="flex flex-col items-end">
               <div className="text-3xl font-black text-foreground">{data.quizzes.reduce((acc, q) => acc + q.attempt_count, 0)}</div>
               <div className="text-[9px] font-black text-text-muted uppercase tracking-widest">Total Submissions</div>
            </div>
         </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
         {/* Most Difficult Questions */}
         <div className="space-y-6">
            <div className="flex items-center gap-3">
               <AlertTriangle className="text-red-400" size={20} />
               <h3 className="text-[10px] font-black text-red-400 uppercase tracking-[0.3em]">Critical Friction Points</h3>
            </div>
            
            <div className="space-y-4">
               {data.difficult_questions?.length > 0 ? data.difficult_questions.map((q, i) => (
                  <div key={i} className="glass-card p-6 border-red-500/10 hover:border-red-500/30 transition-all flex items-start gap-4">
                     <div className="shrink-0 w-10 h-10 rounded-xl bg-red-500/10 border border-red-500/20 flex items-center justify-center text-red-400 text-xs font-black">
                        {q.success_rate}%
                     </div>
                     <div className="flex-1 space-y-2">
                        <p className="text-sm font-bold text-white/90 leading-relaxed">{q.question}</p>
                        <div className="flex items-center gap-3 text-[9px] font-black text-text-muted uppercase tracking-widest">
                           <TrendingDown size={12} className="text-red-400" /> High failure rate in {q.total_attempts} attempts
                        </div>
                     </div>
                  </div>
               )) : (
                  <div className="p-8 text-center bg-surface/40 rounded-3xl border border-white/5">
                     <CheckCircle2 className="mx-auto text-success mb-3" size={24} />
                     <p className="text-[10px] font-black text-text-muted uppercase tracking-widest">No major friction zones detected</p>
                  </div>
               )}
            </div>
         </div>

         {/* Quiz performance table */}
         <div className="space-y-6">
            <div className="flex items-center gap-3">
               <BarChart3 className="text-primary" size={20} />
               <h3 className="text-[10px] font-black text-primary uppercase tracking-[0.3em]">Module-wise Proficiency</h3>
            </div>

            <div className="glass-card overflow-hidden">
               <div className="overflow-x-auto">
                  <table className="w-full text-left">
                     <thead className="border-b border-white/5 bg-white/5">
                        <tr>
                           <th className="p-6 text-[9px] font-black text-text-muted uppercase tracking-widest">Assessed Module</th>
                           <th className="p-6 text-[9px] font-black text-text-muted uppercase tracking-widest">Avg Proficiency</th>
                           <th className="p-6 text-[9px] font-black text-text-muted uppercase tracking-widest">Sample Size</th>
                           <th className="p-6"></th>
                        </tr>
                     </thead>
                     <tbody className="divide-y divide-white/5">
                        {data.quizzes.map((quiz) => (
                           <tr key={quiz.id} className="hover:bg-white/5 transition-colors">
                              <td className="p-6">
                                 <div className="text-sm font-bold text-white mb-1">{quiz.title}</div>
                                 <div className="text-[9px] font-black text-text-muted uppercase tracking-tight">{quiz.lecture}</div>
                              </td>
                              <td className="p-6">
                                 <div className="flex items-center gap-3">
                                    <div className="w-16 h-1 bg-white/5 rounded-full overflow-hidden">
                                       <div 
                                          className={`h-full ${quiz.avg_score > 75 ? 'bg-success' : quiz.avg_score > 50 ? 'bg-yellow-400' : 'bg-red-500'}`} 
                                          style={{ width: `${quiz.avg_score}%` }} 
                                       />
                                    </div>
                                    <span className="text-xs font-black text-foreground">{quiz.avg_score}%</span>
                                 </div>
                              </td>
                              <td className="p-6">
                                 <div className="text-xs font-bold text-white/70">{quiz.attempt_count} students</div>
                              </td>
                              <td className="p-6 text-right">
                                 <button className="text-white/20 hover:text-primary transition-colors">
                                    <ArrowRight size={18} />
                                 </button>
                              </td>
                           </tr>
                        ))}
                     </tbody>
                  </table>
               </div>
            </div>
         </div>
      </div>
    </div>
  );
}
