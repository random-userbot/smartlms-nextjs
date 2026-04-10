'use client';

import React from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useAuth } from '@/context/AuthContext';
import { analyticsAPI } from '@/lib/api';
import { 
  Activity, 
  Clock, 
  Brain, 
  Zap, 
  TrendingUp, 
  AlertCircle,
  ChevronRight,
  Target,
  ArrowUpRight,
  Star, 
  MessageSquare, 
  Send, 
  Sparkles, 
  LayoutDashboard,
  Bot
} from 'lucide-react';
import Sidebar from '@/components/Sidebar';
import Link from 'next/link';

import NavigationHeader from '@/components/NavigationHeader';

export default function DashboardPage() {
  const { user } = useAuth();
  const router = useRouter();
  const [data, setData] = React.useState<any>(null);
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    if (!user) return;
    
    // Role-based redirection
    if (user.role === 'teacher') {
      router?.push('/teacher');
      return;
    }
    if (user.role === 'admin') {
      router?.push('/admin');
      return;
    }

    analyticsAPI.getStudentDashboard()
      .then(res => setData(res.data))
      .catch(err => console.error("Failed to load dashboard:", err))
      .finally(() => setLoading(false));
  }, [user, router]);

  if (loading || user?.role !== 'student') {
    return (
      <div className="flex min-h-screen bg-background items-center justify-center">
        <div className="w-12 h-12 border-4 border-primary/20 border-t-primary rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="flex h-screen bg-background overflow-hidden font-sans text-foreground">
      <Sidebar />
      <main className="flex-1 ml-64 p-12 overflow-y-auto space-y-12 animate-fade-in custom-scrollbar">
        
        <NavigationHeader 
          title={`Welcome, ${data?.full_name?.split(' ')[0] || user?.full_name?.split(' ')[0] || 'User'}`}
          subtitle="Sync Established"
          showBack={false}
        />

        {/* Welcome Section Description */}
        <section className="flex flex-col md:flex-row md:items-end justify-between gap-8 -mt-10">
          <div className="max-w-2xl">
            <p className="text-text-muted font-bold text-lg leading-relaxed">
              {data?.aika_insight || "System active. Aika has established a stable neural link. Ready for the next module?"}
            </p>
          </div>
          <div className="flex gap-4">
            <Link href="/courses" className="bg-primary hover:bg-primary-hover text-white py-4 px-10 text-xs font-black uppercase tracking-widest flex items-center gap-3 rounded-2xl transition-all shadow-lg shadow-primary/20">
              Resume Journey <ArrowUpRight size={18} />
            </Link>
          </div>
        </section>

        {/* Bento Intelligence Grid */}
        <div className="grid grid-cols-12 gap-8">
          
          {/* Main Focus Pulse (Bento 8) */}
          <div className="col-span-12 lg:col-span-8 glass-card p-10 flex flex-col gap-10 relative overflow-hidden group">
            <Activity className="absolute -right-10 -top-10 text-primary/5 group-hover:scale-110 transition-transform duration-1000" size={320} />
            <div className="flex justify-between items-start relative z-10">
              <div>
                <h3 className="text-2xl font-black text-foreground">Focus Pulse</h3>
                <div className="text-[10px] font-black text-primary uppercase tracking-widest mt-1">Real-time Engagement Baseline</div>
              </div>
              <div className="px-5 py-2 bg-primary/10 border border-primary/20 rounded-xl text-[10px] font-black text-primary uppercase tracking-widest">
                Aggregated
              </div>
            </div>
            
            <div className="h-48 w-full flex items-end gap-1 relative z-10">
              {(Array.isArray(data?.focus_pulse) ? data.focus_pulse : []).map((h: number, i: number) => (
                <div 
                  key={i} 
                  className="flex-1 bg-primary/20 rounded-full transition-all duration-1000 group-hover:bg-primary/40"
                  style={{ height: `${h}%`, transitionDelay: `${i * 20}ms` }}
                ></div>
              ))}
            </div>

            <div className="grid grid-cols-3 gap-8 relative z-10 border-t border-border pt-10">
               <div>
                 <div className="text-[8px] font-black text-text-muted uppercase tracking-widest">Average Focus</div>
                 <div className="text-3xl font-black text-foreground shimmer">{data?.average_focus || '0'}%</div>
               </div>
               <div>
                 <div className="text-[8px] font-black text-text-muted uppercase tracking-widest">Active Time</div>
                 <div className="text-3xl font-black text-foreground">{data?.active_time_hours || '0'}h</div>
               </div>
               <div>
                 <div className="text-[8px] font-black text-text-muted uppercase tracking-widest">Growth</div>
                 <div className="text-3xl font-black text-success">+{data?.growth_percent || '0'}%</div>
               </div>
            </div>
          </div>

          {/* Quick Consultation (Bento 4) */}
          <div className="col-span-12 lg:col-span-4 glass-card p-10 bg-primary/5 border-primary/20 flex flex-col justify-between hover:border-primary/40 transition-all">
             <div className="flex flex-col gap-6">
                <div className="w-12 h-12 rounded-2xl bg-primary flex items-center justify-center text-foreground crimson-glow">
                  <Bot size={24} />
                </div>
                 <div>
                    <h3 className="text-2xl font-black text-foreground">Ask Aika</h3>
                    <p className="text-xs font-medium text-foreground/70 mt-3 leading-relaxed italic">
                      "{data?.aika_insight || 'Your learning synchronization is proceeding as expected.'}"
                    </p>
                 </div>
             </div>
             <Link href="/ai-tutor" className="w-full py-4 text-[10px] font-black uppercase tracking-widest text-primary border border-primary/20 rounded-xl text-center hover:bg-primary hover:text-foreground transition-all">
                Enter AI Space
             </Link>
          </div>

          {/* Progress Nodes (Bento 6) */}
          <div className="col-span-12 lg:col-span-6 glass-card p-10 flex flex-col gap-8">
            <h3 className="text-xl font-black text-foreground flex items-center gap-3">
              <Target size={20} className="text-primary" /> Active Nodes
            </h3>
            <div className="space-y-6">
              {data?.active_nodes?.length > 0 ? (
                data.active_nodes.map((node: any, i: number) => (
                  <div key={i} className="space-y-2">
                    <div className="flex justify-between text-[10px] font-black uppercase tracking-widest">
                      <span className="text-foreground">{node.title}</span>
                      <span className="text-primary">{node.progress}%</span>
                    </div>
                    <div className="w-full h-2 bg-surface-alt rounded-full overflow-hidden border border-border">
                      <div className="h-full bg-primary rounded-full transition-all duration-1000" style={{ width: `${node.progress}%` }}></div>
                    </div>
                  </div>
                ))
              ) : (
                <p className="text-xs font-bold text-text-muted italic">No active nodes detected. Enroll in a course to begin sync.</p>
              )}
            </div>
            <Link href="/courses" className="text-[10px] font-black text-primary uppercase tracking-widest hover:text-foreground transition-colors mt-auto">View All Nodes &rarr;</Link>
          </div>

          {/* Cognitive Goal (Bento 6) */}
          <div className="col-span-12 lg:col-span-6 glass-card p-10 flex items-center gap-8 border-success/20">
            <div className="w-24 h-24 rounded-full border-8 border-success/10 flex items-center justify-center text-success font-black text-2xl relative overflow-hidden">
               <div className="absolute inset-0 bg-success/5 animate-pulse"></div>
               {data?.daily_goal_progress || 0}%
            </div>
            <div>
              <h3 className="text-xl font-black text-foreground">Daily Learning Goal</h3>
              <p className="text-xs font-medium text-text-muted mt-2">Finish 1 more module today to maintain your streak.</p>
              <div className="mt-4 flex gap-2">
                {[1, 2, 3, 4, 5, 0, 0].map((v, i) => (
                  <div key={i} className={`w-2 h-2 rounded-full ${v > 0 ? 'bg-success' : 'bg-surface-alt border border-border'}`}></div>
                ))}
              </div>
            </div>
          </div>

        </div>

      </main>
    </div>
  );
}
