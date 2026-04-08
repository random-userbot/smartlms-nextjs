'use client';

import React, { useState, useEffect } from 'react';
import { 
  ShieldCheck, 
  Users, 
  BookOpen, 
  Activity, 
  BarChart3, 
  Settings, 
  UserPlus, 
  Trash2, 
  AlertCircle,
  TrendingUp,
  Cpu,
  Layers,
  Database,
  ChevronRight
} from 'lucide-react';
import { adminAPI } from '@/lib/api';
import Sidebar from '@/components/Sidebar';

export default function AdminPage() {
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadStats();
  }, []);

  const loadStats = async () => {
    try {
      const res = await adminAPI.getSystemStats();
      setStats(res.data);
    } catch (err) {
      console.error('Failed to load admin stats', err);
    } finally {
      setLoading(false);
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
      
      <main className="flex-1 ml-64 p-8 md:p-12 space-y-12">
        <div className="max-w-7xl mx-auto space-y-12">
          {/* Header */}
          <header className="flex flex-col md:flex-row md:items-end justify-between gap-6">
            <div>
              <div className="text-[10px] uppercase tracking-[0.3em] font-black text-primary mb-2">Root Administrative Node</div>
              <h1 className="text-6xl font-black tracking-tighter">System Control.</h1>
              <p className="text-text-muted font-bold mt-4 max-w-2xl text-lg leading-relaxed">
                Orchestrating global educational infrastructure, user access protocols, and system-wide performance indices.
              </p>
            </div>
            <div className="flex gap-4">
              <div className="px-6 py-3 bg-primary/10 border border-primary/20 rounded-2xl text-primary font-black text-xs uppercase tracking-widest flex items-center gap-2">
                <ShieldCheck size={16} /> Status: Nominal
              </div>
            </div>
          </header>

          {/* Stats Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {[
              { label: 'Total Users', value: stats?.total_users || 0, icon: Users, color: 'text-primary' },
              { label: 'Academic Staff', value: stats?.teachers || 0, icon: ShieldCheck, color: 'text-info' },
              { label: 'Active Students', value: stats?.students || 0, icon: UserPlus, color: 'text-success' },
              { label: 'Total Modules', value: stats?.courses || 0, icon: BookOpen, color: 'text-warning' },
            ].map((stat, i) => (
              <div key={i} className="glass-card p-8 border border-white/5 hover:border-primary/30 transition-all group cursor-default bg-surface/50">
                <div className="flex items-center justify-between mb-6">
                  <div className={`p-4 bg-background rounded-2xl border border-white/5 group-hover:scale-110 transition-transform ${stat.color}`}>
                    <stat.icon size={24} />
                  </div>
                  <TrendingUp size={20} className="text-success opacity-40" />
                </div>
                <div className="text-4xl font-black tracking-tight mb-1">{stat.value}</div>
                <div className="text-[10px] font-black text-text-muted uppercase tracking-[0.2em]">{stat.label}</div>
              </div>
            ))}
          </div>

          <div className="grid grid-cols-12 gap-8">
            {/* System Performance */}
            <div className="col-span-12 lg:col-span-7 space-y-6">
              <div className="glass-card p-10 border border-white/5 h-full space-y-8">
                <div className="flex items-center justify-between">
                  <h3 className="text-2xl font-black flex items-center gap-3">
                    <Cpu size={24} className="text-primary" /> Matrix Performance
                  </h3>
                  <span className="text-[10px] font-black uppercase tracking-widest text-text-muted">Real-time telemetrics</span>
                </div>

                <div className="grid grid-cols-2 gap-8">
                  {[
                    { label: 'API Latency', value: '12ms', pct: 88 },
                    { label: 'Success Rate', value: '99.9%', pct: 99 },
                    { label: 'Throughput', value: '1.2k/s', pct: 75 },
                    { label: 'Uptime', value: '32d 12h', pct: 100 },
                  ].map(m => (
                    <div key={m.label} className="space-y-3">
                      <div className="flex justify-between items-end">
                        <span className="text-[10px] font-black uppercase tracking-widest text-text-muted">{m.label}</span>
                        <span className="font-bold text-primary">{m.value}</span>
                      </div>
                      <div className="h-1.5 bg-background rounded-full overflow-hidden">
                        <div className="h-full bg-primary rounded-full transition-all duration-1000" style={{ width: `${m.pct}%` }}></div>
                      </div>
                    </div>
                  ))}
                </div>

                <div className="p-8 bg-primary/5 border border-primary/20 rounded-[2rem] space-y-4">
                  <div className="text-xs font-black uppercase tracking-widest text-primary flex items-center gap-2">
                    <Activity size={16} /> Operational Insights
                  </div>
                  <p className="text-sm font-medium text-white/90 leading-relaxed italic">
                    "System-wide enrollment spikes detected in Category: Technology. All clusters performing within expected parameters. AI-Tutor latency remains sub-50ms."
                  </p>
                </div>
              </div>
            </div>

            {/* Quick Actions */}
            <div className="col-span-12 lg:col-span-5 space-y-6">
              <div className="glass-card p-10 border border-white/5 h-full space-y-8">
                <div className="flex items-center justify-between">
                  <h3 className="text-2xl font-black flex items-center gap-3">
                    <Database size={24} className="text-primary" /> Control Nodes
                  </h3>
                </div>

                <div className="space-y-4">
                  {[
                    { label: 'User Indexing', desc: 'Manage all accounts and permissions', icon: Users, href: '/admin/users' },
                    { label: 'Teacher Validation', desc: 'Audit educational staff and scores', icon: ShieldCheck, href: '/admin/teachers' },
                    { label: 'Module Registry', desc: 'Audit system-wide course content', icon: Layers, href: '/admin/courses' },
                    { label: 'Matrix Config', desc: 'Adjust global system parameters', icon: Settings, href: '/admin/settings' },
                  ].map(action => (
                    <button 
                      key={action.label} 
                      className="w-full p-6 bg-white/5 border border-white/10 rounded-3xl hover:bg-white/10 hover:border-primary/40 transition-all flex items-center gap-6 group text-left"
                    >
                      <div className="w-14 h-14 bg-background rounded-2xl border border-white/5 flex items-center justify-center text-primary group-hover:scale-110 transition-transform">
                        <action.icon size={24} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="text-lg font-black tracking-tight">{action.label}</div>
                        <div className="text-[10px] font-black text-text-muted uppercase tracking-widest mt-0.5">{action.desc}</div>
                      </div>
                      <ChevronRight size={20} className="text-white/20 group-hover:text-primary group-hover:translate-x-1 transition-all" />
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
