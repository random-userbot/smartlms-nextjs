'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { coursesAPI } from '@/lib/api';
import { 
  BookOpen, 
  Search, 
  Play, 
  Users, 
  CheckCircle2, 
  TrendingUp, 
  Clock,
  Sparkles,
  Loader2
} from 'lucide-react';
import Sidebar from '@/components/Sidebar';

export default function MyCoursesPage() {
  const router = useRouter();
  const [enrolled, setEnrolled] = useState<any[]>([]);
  const [available, setAvailable] = useState<any[]>([]);
  const [tab, setTab] = useState<'enrolled' | 'browse'>('enrolled');
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [enrollingId, setEnrollingId] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      coursesAPI.getMyCourses().catch(() => ({ data: [] })),
      coursesAPI.list().catch(() => ({ data: [] })),
    ]).then(([enrolledRes, availableRes]) => {
      setEnrolled(enrolledRes.data || []);
      setAvailable(availableRes.data || []);
    }).finally(() => setLoading(false));
  }, []);

  const handleEnroll = async (id: string) => {
    setEnrollingId(id);
    try {
      await coursesAPI.enroll(id);
      const res = await coursesAPI.getMyCourses();
      setEnrolled(res.data || []);
      setTab('enrolled');
    } catch (err) {
      console.error(err);
    } finally {
      setEnrollingId(null);
    }
  };

  const enrolledIds = new Set(enrolled.map(c => c.course_id));
  const filteredAvailable = available.filter(c => 
    !enrolledIds.has(c.id) && c.title.toLowerCase().includes(search.toLowerCase())
  );

  if (loading) return null;

  return (
    <div className="flex min-h-screen bg-background">
      <Sidebar />
      <main className="flex-1 ml-64 p-12 space-y-10 animate-fade-in">
        
        {/* Hub Header */}
        <header className="flex flex-col md:flex-row md:items-end justify-between gap-6 border-b border-border pb-10">
          <div>
            <div className="text-[10px] uppercase tracking-[0.3em] font-black text-primary mb-2">Academic Repository</div>
            <h1 className="text-6xl font-black tracking-tighter text-white">Learning Hub.</h1>
            <p className="text-text-muted font-bold mt-4 max-w-xl">
              Access your enrolled modules or browse the global intelligence catalog for new specializations.
            </p>
          </div>
          <div className="flex p-1.5 bg-surface rounded-2xl border border-border">
            <button 
              onClick={() => setTab('enrolled')}
              className={`px-8 py-3 rounded-xl text-xs font-black uppercase tracking-widest transition-all ${tab === 'enrolled' ? 'bg-primary text-white crimson-glow' : 'text-text-muted hover:text-white'}`}
            >
              Enrolled
            </button>
            <button 
              onClick={() => setTab('browse')}
              className={`px-8 py-3 rounded-xl text-xs font-black uppercase tracking-widest transition-all ${tab === 'browse' ? 'bg-primary text-white crimson-glow' : 'text-text-muted hover:text-white'}`}
            >
              Catalog
            </button>
          </div>
        </header>

        {tab === 'enrolled' ? (
          <div className="space-y-12">
            {enrolled.length > 0 ? (
              <>
                {/* Spotlight Course */}
                <section 
                  onClick={() => router.push(`/courses/${enrolled[0].course_id}`)}
                  className="glass-card p-12 flex flex-col md:flex-row gap-12 items-center cursor-pointer hover:border-primary/40 transition-all group overflow-hidden relative"
                >
                  <Sparkles className="absolute -right-10 -top-10 text-primary/5 group-hover:scale-110 transition-transform duration-700" size={300} />
                  <div className="w-full md:w-1/3 aspect-video bg-surface-alt rounded-[2rem] border border-white/5 overflow-hidden relative">
                    <div className="absolute inset-0 bg-gradient-to-br from-primary/20 to-transparent"></div>
                    <BookOpen className="absolute inset-0 m-auto text-primary/20" size={80} />
                  </div>
                  <div className="flex-1 space-y-6">
                    <div>
                      <div className="text-[10px] font-black text-primary uppercase tracking-widest mb-2">Resume Module</div>
                      <h2 className="text-4xl font-black text-white">{enrolled[0].title}</h2>
                      <p className="text-sm font-bold text-text-muted mt-1 uppercase tracking-widest">{enrolled[0].teacher_name}</p>
                    </div>
                    <div className="space-y-2">
                       <div className="flex justify-between items-end">
                         <span className="text-[10px] font-black text-text-muted uppercase tracking-widest">Progress</span>
                         <span className="text-2xl font-black text-primary">{Math.round(enrolled[0].progress || 0)}%</span>
                       </div>
                       <div className="w-full h-3 bg-white/5 rounded-full overflow-hidden border border-white/5">
                         <div className="h-full bg-primary crimson-glow rounded-full" style={{ width: `${enrolled[0].progress}%` }}></div>
                       </div>
                    </div>
                    <div className="flex gap-4">
                      <div className="flex items-center gap-2 text-[10px] font-black text-success uppercase tracking-widest">
                         <CheckCircle2 size={12} /> {enrolled[0].completed_lectures} / {enrolled[0].total_lectures || 0} Complete
                      </div>
                      <div className="flex items-center gap-2 text-[10px] font-black text-warning uppercase tracking-widest">
                         <TrendingUp size={12} /> {enrolled[0].avg_engagement}% Avg Focus
                      </div>
                    </div>
                  </div>
                </section>

                {/* Other Enrolled Courses */}
                {enrolled.length > 1 && (
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    {enrolled.slice(1).map(c => (
                      <div 
                        key={c.course_id}
                        onClick={() => router.push(`/courses/${c.course_id}`)}
                        className="glass-card p-8 space-y-6 cursor-pointer hover:border-primary/30 transition-all flex flex-col justify-between"
                      >
                         <h4 className="text-xl font-black text-white line-clamp-2">{c.title}</h4>
                         <div className="space-y-2">
                            <div className="flex justify-between text-[8px] font-black text-text-muted uppercase tracking-widest">
                              <span>Progress</span>
                              <span>{Math.round(c.progress)}%</span>
                            </div>
                            <div className="w-full h-1.5 bg-white/5 rounded-full overflow-hidden">
                              <div className="h-full bg-primary rounded-full" style={{ width: `${c.progress}%` }}></div>
                            </div>
                         </div>
                      </div>
                    ))}
                  </div>
                )}
              </>
            ) : (
              <div className="text-center py-32 glass-card bg-primary/5 border-dashed border-primary/20">
                <BookOpen className="mx-auto text-primary/20 mb-6" size={80} />
                <h3 className="text-3xl font-black text-white mb-2">No Active Modules</h3>
                <p className="text-text-muted font-bold mb-8">Your intelligence grid is currently empty. Explore the catalog to begin.</p>
                <button 
                  onClick={() => setTab('browse')}
                  className="btn-primary"
                >
                  Explore Catalog
                </button>
              </div>
            )}
          </div>
        ) : (
          <div className="space-y-10">
            {/* Catalog Search */}
            <div className="max-w-xl relative group">
              <div className="absolute inset-y-0 left-6 flex items-center pointer-events-none">
                <Search size={18} className="text-text-muted group-focus-within:text-primary transition-colors" />
              </div>
              <input 
                type="text" 
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search the global catalog..."
                className="w-full bg-surface border border-border rounded-2xl pl-16 pr-6 py-4 text-sm font-medium text-white focus:outline-none focus:border-primary/40 transition-all shadow-xl"
              />
            </div>

            {/* Catalog Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
              {filteredAvailable.map(c => (
                <div key={c.id} className="glass-card flex flex-col group hover:border-primary/40 transition-all overflow-hidden">
                  <div className="aspect-video bg-surface-alt relative overflow-hidden">
                    <div className="absolute inset-0 bg-gradient-to-br from-primary/10 to-transparent"></div>
                    <BookOpen className="absolute inset-0 m-auto text-primary/10 group-hover:scale-110 transition-transform duration-700" size={60} />
                  </div>
                  <div className="p-8 flex flex-col gap-6 flex-1">
                    <div className="flex justify-between items-start">
                      <h4 className="text-xl font-black text-white group-hover:text-primary transition-colors line-clamp-2">{c.title}</h4>
                    </div>
                    <p className="text-xs font-medium text-text-muted line-clamp-3 leading-relaxed">{c.description}</p>
                    
                    <div className="flex items-center gap-4 py-4 border-y border-white/5 mt-auto">
                       <div className="flex items-center gap-2 text-[10px] font-black text-text-muted uppercase tracking-widest">
                         <Play size={10} className="text-primary" /> {c.lecture_count || 0} Modules
                       </div>
                       <div className="flex items-center gap-2 text-[10px] font-black text-text-muted uppercase tracking-widest">
                         <Users size={10} className="text-primary" /> {c.student_count || 0} Enrolled
                       </div>
                    </div>

                    <button 
                      onClick={() => handleEnroll(c.id)}
                      disabled={enrollingId === c.id}
                      className="w-full btn-secondary flex items-center justify-center gap-2 py-4"
                    >
                      {enrollingId === c.id ? <Loader2 className="animate-spin" size={16} /> : 'Enroll Module'}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

      </main>
    </div>
  );
}
