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
  Loader2,
  ArrowRight
} from 'lucide-react';
import Sidebar from '@/components/Sidebar';

export default function MyCoursesPage() {
  const router = useRouter();
  const [enrolled, setEnrolled] = useState<any[]>([]);
  const [catalog, setCatalog] = useState<any[]>([]);
  const [tab, setTab] = useState<'enrolled' | 'browse'>('enrolled');
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [enrollingId, setEnrollingId] = useState<string | null>(null);

  const fetchDashboard = async () => {
    try {
      const [enrolledRes, catalogRes] = await Promise.all([
        coursesAPI.getMyCourses(),
        coursesAPI.list({ view: 'catalog', search: search || undefined })
      ]);
      setEnrolled(enrolledRes.data || []);
      setCatalog(catalogRes.data || []);
    } catch (err) {
      console.error("Failed to fetch courses:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboard();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search]); // Re-fetch on search change

  const handleEnroll = async (id: string) => {
    setEnrollingId(id);
    try {
      await coursesAPI.enroll(id);
      await fetchDashboard();
      setTab('enrolled');
    } catch (err) {
      console.error(err);
    } finally {
      setEnrollingId(null);
    }
  };

  if (loading && enrolled.length === 0 && catalog.length === 0) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-background">
        <Loader2 className="animate-spin text-primary" size={48} />
      </div>
    );
  }

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
              Access your enrolled modules or discover new specializations from the global intelligence catalog.
            </p>
          </div>
          <div className="flex p-1.5 bg-surface rounded-2xl border border-border">
            <button 
              onClick={() => setTab('enrolled')}
              className={`px-8 py-3 rounded-xl text-xs font-black uppercase tracking-widest transition-all ${tab === 'enrolled' ? 'bg-primary text-white crimson-glow shadow-lg shadow-primary/20' : 'text-text-muted hover:text-white'}`}
            >
              My Courses
            </button>
            <button 
              onClick={() => setTab('browse')}
              className={`px-8 py-3 rounded-xl text-xs font-black uppercase tracking-widest transition-all ${tab === 'browse' ? 'bg-primary text-white crimson-glow shadow-lg shadow-primary/20' : 'text-text-muted hover:text-white'}`}
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
                  <div className="w-full md:w-1/3 aspect-video bg-surface-alt rounded-[2rem] border border-white/5 overflow-hidden relative shadow-2xl">
                    {enrolled[0].thumbnail_url ? (
                        <img src={enrolled[0].thumbnail_url} alt={enrolled[0].title} className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-700" />
                    ) : (
                        <div className="absolute inset-0 flex items-center justify-center">
                             <BookOpen className="text-primary/20" size={80} />
                        </div>
                    )}
                    <div className="absolute inset-0 bg-gradient-to-br from-primary/20 to-transparent"></div>
                  </div>
                  <div className="flex-1 space-y-6">
                    <div>
                      <div className="text-[10px] font-black text-primary uppercase tracking-widest mb-2 flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full bg-primary animate-pulse"></span>
                        Resume Module
                      </div>
                      <h2 className="text-4xl font-black text-white">{enrolled[0].title}</h2>
                      <p className="text-sm font-bold text-text-muted mt-1 uppercase tracking-widest">{enrolled[0].teacher_name}</p>
                    </div>
                    <div className="space-y-3">
                       <div className="flex justify-between items-end">
                         <span className="text-[10px] font-black text-text-muted uppercase tracking-widest">Mastery Level</span>
                         <span className="text-2xl font-black text-primary">{Math.round(enrolled[0].progress || 0)}%</span>
                       </div>
                       <div className="w-full h-3 bg-white/5 rounded-full overflow-hidden border border-white/5">
                         <div className="h-full bg-primary crimson-glow rounded-full transition-all duration-1000" style={{ width: `${enrolled[0].progress}%` }}></div>
                       </div>
                    </div>
                    <div className="flex gap-4 pt-2">
                      <div className="flex items-center gap-2 text-[10px] font-black text-success uppercase tracking-widest">
                         <CheckCircle2 size={12} /> Live Support Active
                      </div>
                      <div className="flex items-center gap-2 text-[10px] font-black text-warning uppercase tracking-widest">
                         <TrendingUp size={12} /> High Cognitive Focus
                      </div>
                    </div>
                  </div>
                </section>

                {/* Sub-grid of Enrolled */}
                {enrolled.length > 1 && (
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    {enrolled.slice(1).map(c => (
                      <div 
                        key={c.course_id}
                        onClick={() => router.push(`/courses/${c.course_id}`)}
                        className="glass-card p-8 space-y-6 cursor-pointer hover:border-primary/30 transition-all flex flex-col justify-between group"
                      >
                         <h4 className="text-xl font-black text-white line-clamp-2 group-hover:text-primary transition-colors">{c.title}</h4>
                         <div className="space-y-2">
                            <div className="flex justify-between text-[8px] font-black text-text-muted uppercase tracking-widest">
                              <span>Progress</span>
                              <span>{Math.round(c.progress)}%</span>
                            </div>
                            <div className="w-full h-1.5 bg-white/5 rounded-full overflow-hidden border border-white/5">
                              <div className="h-full bg-primary rounded-full transition-all duration-1000" style={{ width: `${c.progress}%` }}></div>
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
                <h3 className="text-3xl font-black text-white mb-2 uppercase tracking-tighter">Your Grid is Offline</h3>
                <p className="text-text-muted font-bold mb-8">You haven't been enrolled in any modules yet. Visit the catalog to begin your specialization.</p>
                <button 
                  onClick={() => setTab('browse')}
                  className="px-10 py-4 bg-primary text-white rounded-2xl text-xs font-black uppercase tracking-[0.2em] transform active:scale-95 transition-all crimson-glow"
                >
                  Explore Global Catalog
                </button>
              </div>
            )}
          </div>
        ) : (
          <div className="space-y-10">
            {/* Catalog Search */}
            <div className="max-w-2xl relative group">
              <div className="absolute inset-y-0 left-8 flex items-center pointer-events-none">
                <Search size={20} className="text-text-muted group-focus-within:text-primary transition-colors" />
              </div>
              <input 
                type="text" 
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search by topic, instructor, or specialization..."
                className="w-full bg-surface border border-border rounded-3xl pl-20 pr-10 py-6 text-base font-bold text-white focus:outline-none focus:border-primary/40 focus:ring-4 focus:ring-primary/10 transition-all shadow-2xl placeholder:text-text-muted/50"
              />
            </div>

            {/* Catalog Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
              {catalog.map(c => (
                <div key={c.id} className="glass-card flex flex-col group hover:border-primary/40 transition-all overflow-hidden relative">
                  <div className="aspect-video bg-surface-alt relative overflow-hidden border-b border-white/5">
                    {c.thumbnail_url ? (
                        <img src={c.thumbnail_url} alt={c.title} className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-700 opacity-60 group-hover:opacity-100 transition-opacity" />
                    ) : (
                        <div className="absolute inset-0 flex items-center justify-center">
                             <BookOpen className="text-primary/10" size={60} />
                        </div>
                    )}
                    <div className="absolute top-4 right-4 bg-primary/90 text-white text-[8px] font-black px-3 py-1.5 rounded-full uppercase tracking-widest backdrop-blur-md">
                        {c.category || 'Core'}
                    </div>
                  </div>
                  <div className="p-8 flex flex-col gap-6 flex-1">
                    <div>
                      <h4 className="text-xl font-black text-white group-hover:text-primary transition-colors line-clamp-2">{c.title}</h4>
                      <p className="text-[10px] font-black text-text-muted uppercase tracking-widest mt-1 italic">{c.teacher_name}</p>
                    </div>
                    <p className="text-xs font-medium text-text-muted line-clamp-3 leading-relaxed opacity-80">{c.description || "In-depth specialization module covering modern technical architectures and behavioral patterns."}</p>
                    
                    <div className="flex items-center gap-6 py-4 border-y border-white/5 mt-auto">
                       <div className="flex items-center gap-2 text-[9px] font-black text-text-muted uppercase tracking-widest">
                         <Play size={10} className="text-primary" /> {c.lecture_count || 0} Lectures
                       </div>
                       <div className="flex items-center gap-2 text-[9px] font-black text-text-muted uppercase tracking-widest">
                         <Users size={10} className="text-primary" /> {c.student_count || 0} Peers
                       </div>
                    </div>

                    <button 
                      onClick={() => handleEnroll(c.id)}
                      disabled={enrollingId === c.id}
                      className="w-full bg-white/5 hover:bg-primary hover:text-white border border-white/10 hover:border-primary text-text-muted rounded-2xl flex items-center justify-center gap-3 py-4 text-[10px] font-black uppercase tracking-[0.2em] transition-all group/btn"
                    >
                      {enrollingId === c.id ? (
                        <Loader2 className="animate-spin" size={16} />
                      ) : (
                        <>
                          Enroll Specialist <ArrowRight size={14} className="group-hover/btn:translate-x-1 transition-transform" />
                        </>
                      )}
                    </button>
                  </div>
                </div>
              ))}
            </div>

            {catalog.length === 0 && !loading && (
              <div className="text-center py-20 opacity-50">
                 <Search size={48} className="mx-auto mb-4" />
                 <p className="font-bold">No modules matching your search criteria were discovered.</p>
              </div>
            )}
          </div>
        )}

      </main>
    </div>
  );
}
