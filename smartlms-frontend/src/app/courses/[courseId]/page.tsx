'use client';

import React, { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { coursesAPI, lecturesAPI, api } from '@/lib/api';
import { 
  Play, 
  BookOpen, 
  Users, 
  Clock, 
  FileText, 
  ChevronRight, 
  CheckCircle2,
  Lock,
  Sparkles,
  Activity,
  Bot
} from 'lucide-react';
import Sidebar from '@/components/Sidebar';
import NavigationHeader from '@/components/NavigationHeader';

export default function CoursePortal() {
  const params = useParams();
  const router = useRouter();
  const courseId = params.courseId as string;

  const [course, setCourse] = useState<any>(null);
  const [lectures, setLectures] = useState<any[]>([]);
  const [completedIds, setCompletedIds] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState<any>({ total_learning_time_sec: 0, avg_engagement: 0 });

  useEffect(() => {
    if (courseId) {
      Promise.all([
        coursesAPI.get(courseId),
        lecturesAPI.getByCourse(courseId),
        coursesAPI.getProgress(courseId).then((res: any) => res.data).catch(() => ({}))
      ]).then(([courseRes, lecturesRes, progressData]) => {
        setCourse(courseRes.data);
        setLectures(lecturesRes.data || []);
        setCompletedIds(progressData.completed_lecture_ids || []);
        setStats({
          total_learning_time_sec: progressData.total_learning_time_sec || 0,
          avg_engagement: progressData.avg_engagement || 0
        });
      }).finally(() => setLoading(false));
    }
  }, [courseId]);

  const activeLectureIndex = lectures.findIndex(l => !completedIds.includes(l.id));
  const activeLecture = activeLectureIndex !== -1 ? lectures[activeLectureIndex] : null;

  if (loading) return null;

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <Sidebar />
      <div className="flex-1 ml-64 flex flex-col min-w-0">
        <NavigationHeader title={course?.title || 'Course Roadmap'} showBack={true} />
        
        <main className="flex-1 p-12 space-y-12 animate-fade-in overflow-y-auto no-scrollbar">
          
          {/* Course Hero Banner */}
          <section className="relative h-[400px] rounded-[3rem] overflow-hidden border border-border crimson-glow group">
            <div className="absolute inset-0 bg-gradient-to-br from-primary to-surface-alt opacity-90"></div>
            <div className="absolute inset-0 bg-[url('/noise.png')] opacity-10"></div>
            
            <div className="relative h-full flex flex-col justify-center p-16 gap-6 z-10">
              <div className="flex items-center gap-3 text-[10px] font-black text-white uppercase tracking-[0.4em]">
                <BookOpen size={14} /> Cognitive Roadmap
              </div>
              <h1 className="text-7xl font-black text-white tracking-tighter max-w-3xl leading-[0.9]">
                {course?.title}
              </h1>
              <p className="text-xl font-bold text-white/80 max-w-2xl leading-relaxed">
                {course?.description || 'Synchronizing cross-functional learning nodes for professional domain mastery.'}
              </p>
              
              <div className="flex gap-6 mt-4">
                 <div className="flex items-center gap-2 text-xs font-black text-white border border-white/20 px-6 py-3 rounded-2xl bg-white/5 backdrop-blur-md">
                   <Users size={16} /> {course?.student_count || 0} Students
                 </div>
                 <div className="flex items-center gap-2 text-xs font-black text-white border border-white/20 px-6 py-3 rounded-2xl bg-white/5 backdrop-blur-md">
                   <Play size={16} /> {lectures?.length} Modules
                 </div>
              </div>
            </div>

            <Sparkles className="absolute -right-20 -bottom-20 text-white/5 group-hover:scale-110 transition-transform duration-1000" size={500} />
          </section>

          {/* Content Grid */}
          <div className="grid grid-cols-12 gap-12">
            
            {/* Roadmap */}
            <div className="col-span-12 lg:col-span-8 space-y-8">
              <h2 className="text-3xl font-black text-foreground flex items-center gap-4">
                Curriculum Nodes <div className="flex-1 h-px bg-border"></div>
              </h2>

              <div className="space-y-4">
                {lectures.map((lecture, i) => {
                  const isCompleted = completedIds.includes(lecture.id);
                  const isActive = activeLecture?.id === lecture.id;
                  return (
                    <button
                      key={lecture.id}
                      onClick={() => router.push(`/lectures/${lecture.id}`)}
                      className={`w-full group relative flex items-center gap-6 p-8 rounded-[2rem] border transition-all duration-500 hover:scale-[1.02] ${
                        isActive 
                        ? 'bg-primary/5 border-primary shadow-2xl shadow-primary/10' 
                        : isCompleted 
                        ? 'bg-success/5 border-success/20' 
                        : 'bg-surface border-border hover:border-primary/50'
                      }`}
                    >
                      <div className={`w-14 h-14 rounded-2xl flex items-center justify-center flex-shrink-0 transition-transform group-hover:rotate-12 ${
                        isCompleted ? 'bg-success text-white' : isActive ? 'bg-primary text-white crimson-glow' : 'bg-white/5 text-text-muted'
                      }`}>
                        {isCompleted ? <CheckCircle2 size={24} /> : <Play size={24} />}
                      </div>
                      
                      <div className="flex-1 text-left">
                        <div className="flex items-center gap-3 mb-1">
                           <span className="text-[10px] font-black text-text-muted uppercase tracking-widest">Module {i + 1}</span>
                           {isActive && <span className="bg-primary/20 text-primary text-[8px] font-black px-2 py-0.5 rounded-full uppercase">Active Now</span>}
                        </div>
                        <h3 className="text-xl font-bold text-white group-hover:text-primary transition-colors">
                          {lecture.title}
                        </h3>
                      </div>

                      <ChevronRight className={`transition-transform group-hover:translate-x-2 ${isActive ? 'text-primary' : 'text-text-muted/20'}`} />
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Sidebar Stats */}
            <div className="col-span-12 lg:col-span-4 space-y-8">
               <div className="glass-card p-10 space-y-8">
                  <div className="space-y-2">
                    <h3 className="text-sm font-black text-text-muted uppercase tracking-widest">Neural Progress</h3>
                    <div className="text-5xl font-black text-white">
                      {Math.round((completedIds.length / (lectures.length || 1)) * 100)}%
                    </div>
                  </div>
                  
                  <div className="h-2 w-full bg-white/5 rounded-full overflow-hidden">
                    <div 
                      className="h-full bg-primary crimson-glow transition-all duration-1000" 
                      style={{ width: `${(completedIds.length / (lectures.length || 1)) * 100}%` }}
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div className="p-4 rounded-2xl bg-white/5 border border-white/5">
                       <Clock className="text-primary mb-2" size={16} />
                       <div className="text-lg font-black text-white">
                         {Math.floor(stats.total_learning_time_sec / 3600)}h {Math.floor((stats.total_learning_time_sec % 3600) / 60)}m
                       </div>
                       <div className="text-[9px] font-black text-text-muted uppercase">Total Learning</div>
                    </div>
                    <div className="p-4 rounded-2xl bg-white/5 border border-white/5">
                       <Activity className="text-success mb-2" size={16} />
                       <div className="text-lg font-black text-white">
                         {stats.avg_engagement > 70 ? 'High' : stats.avg_engagement > 40 ? 'Med' : 'Low'}
                       </div>
                       <div className="text-[9px] font-black text-text-muted uppercase">Avg Engagement</div>
                    </div>
                  </div>

                  <button className="w-full btn-primary py-4 rounded-2xl flex items-center justify-center gap-3 group">
                    <div className="w-8 h-8 rounded-lg bg-white/20 flex items-center justify-center">
                      <Sparkles size={16} />
                    </div>
                    <span className="font-black uppercase tracking-widest text-xs">AI Study Companion</span>
                  </button>
               </div>

               <div className="glass-card p-10 bg-gradient-to-br from-surface to-primary/10">
                  <Bot className="text-primary mb-6" size={40} />
                  <h4 className="text-xl font-bold text-white mb-4">Neural Insights</h4>
                  <p className="text-sm text-text-muted font-medium leading-relaxed mb-6">
                    Aika perceives that you excel in theoretical concepts but might need more practical application. 
                    Target Module 4 for maximum cognitive resonance.
                  </p>
                  <button className="text-primary font-black uppercase tracking-widest text-[10px] flex items-center gap-2 hover:gap-4 transition-all">
                    Generate Learning Plan <ChevronRight size={14} />
                  </button>
               </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
