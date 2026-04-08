"use client";

import React, { useEffect, useState } from 'react';
import { 
  Users, 
  BookOpen, 
  Calendar, 
  Activity, 
  TrendingUp, 
  Star, 
  AlertTriangle,
  ArrowUpRight,
  UserCheck,
  ShieldAlert,
  Zap,
  Target
} from 'lucide-react';
import { adminAPI } from '@/lib/api';
import { 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer, 
  AreaChart, 
  Area,
  PieChart,
  Pie,
  Cell
} from 'recharts';

export default function AdminDashboard() {
  const [stats, setStats] = useState<any>(null);
  const [teachers, setTeachers] = useState<any[]>([]);
  const [systemStatus, setSystemStatus] = useState<'healthy' | 'degraded' | 'loading'>('loading');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [statsData, teachersData] = await Promise.all([
          adminAPI.getSystemStats(),
          adminAPI.listTeachers(),
        ]);
        setStats(statsData.data);
        setTeachers(teachersData.data);
        
        // Check real health
        const healthRes = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/health`);
        if (healthRes.ok) {
          const health = await healthRes.json();
          setSystemStatus(health.status || 'healthy');
        } else {
          setSystemStatus('degraded');
        }
      } catch (err) {
        console.error('Failed to fetch admin stats:', err);
        setSystemStatus('degraded');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444'];

  const mockHeatmapData = [
    { name: 'Mon', engagement: 65, active: 40 },
    { name: 'Tue', engagement: 72, active: 45 },
    { name: 'Wed', engagement: 85, active: 55 },
    { name: 'Thu', engagement: 78, active: 50 },
    { name: 'Fri', engagement: 90, active: 62 },
    { name: 'Sat', engagement: 45, active: 25 },
    { name: 'Sun', engagement: 50, active: 30 },
  ];

  if (loading) return (
    <div className="flex items-center justify-center h-96">
      <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
    </div>
  );

  return (
    <div className="space-y-8 animate-in fade-in duration-700">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-white mb-2 underline decoration-blue-500 decoration-4 underline-offset-8">
            Command Center Overview
          </h1>
          <p className="text-slate-400">Global cognitive resonance and pedagogical orchestration</p>
        </div>
        
        <div className={`flex items-center gap-2 px-4 py-2 rounded-2xl border ${
          systemStatus === 'healthy' ? 'bg-blue-500/10 border-blue-500/20 text-blue-400' : 
          systemStatus === 'loading' ? 'bg-slate-500/10 border-slate-500/20 text-slate-400' :
          'bg-red-500/10 border-red-500/20 text-red-500'
        }`}>
          <Zap className={`w-4 h-4 ${systemStatus === 'healthy' ? 'animate-pulse' : ''}`} />
          <span className="text-sm font-semibold">
            {systemStatus === 'healthy' ? 'System Live & Healthy' : 
             systemStatus === 'loading' ? 'Checking Pulse...' : 'System Degraded'}
          </span>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard 
          title="Total Students" 
          value={stats?.students || 0} 
          icon={Users} 
          trend="+12%" 
          color="blue" 
          subtitle="Cross-platform active"
        />
        <StatCard 
          title="Active Teachers" 
          value={stats?.teachers || 0} 
          icon={UserCheck} 
          trend="+3" 
          color="emerald" 
          subtitle="Certified instructors"
        />
        <StatCard 
          title="Cognitive Sessions" 
          value={stats?.engagement_sessions || 0} 
          icon={Activity} 
          trend="+40%" 
          color="amber" 
          subtitle="Aika telemetry logs"
        />
        <StatCard 
          title="System Health" 
          value={systemStatus === 'healthy' ? '100%' : 'Critical'} 
          icon={ShieldAlert} 
          trend={systemStatus === 'healthy' ? 'Stable' : 'Unstable'} 
          color={systemStatus === 'healthy' ? 'blue' : 'red'} 
          subtitle={systemStatus === 'healthy' ? 'Uptime: 99.9%' : 'Investigation Required'} 
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Engagement Charts */}
        <div className="lg:col-span-2 space-y-8">
          <div className="bg-slate-900/50 backdrop-blur-xl border border-slate-800 rounded-3xl p-6 shadow-2xl">
            <div className="flex items-center justify-between mb-8">
              <div>
                <h3 className="text-xl font-bold text-white flex items-center gap-2">
                  <TrendingUp className="w-5 h-5 text-blue-500" />
                  Cognitive Resonance Trends
                </h3>
                <p className="text-sm text-slate-400">Predicted Engagement vs. Actual Active Participation</p>
              </div>
            </div>
            
            <div className="h-80 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={mockHeatmapData}>
                  <defs>
                    <linearGradient id="colorEng" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                    </linearGradient>
                    <linearGradient id="colorAct" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#10b981" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                  <XAxis dataKey="name" stroke="#64748b" axisLine={false} tickLine={false} />
                  <YAxis stroke="#64748b" axisLine={false} tickLine={false} />
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #1e293b', borderRadius: '12px' }}
                    itemStyle={{ color: '#f1f5f9' }}
                  />
                  <Area type="monotone" dataKey="engagement" stroke="#3b82f6" strokeWidth={3} fillOpacity={1} fill="url(#colorEng)" />
                  <Area type="monotone" dataKey="active" stroke="#10b981" strokeWidth={3} fillOpacity={1} fill="url(#colorAct)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Teacher Performance */}
          <div className="bg-slate-900/50 backdrop-blur-xl border border-slate-800 rounded-3xl p-6 shadow-2xl overflow-hidden">
            <div className="flex items-center justify-between mb-6 px-2">
              <h3 className="text-xl font-bold text-white flex items-center gap-2">
                <Star className="w-5 h-5 text-amber-500" />
                Teacher Performance Grid
              </h3>
              <button className="text-sm text-blue-400 font-medium hover:underline">View All</button>
            </div>
            
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead className="bg-slate-800/50 text-slate-400 text-xs uppercase tracking-wider">
                  <tr>
                    <th className="px-6 py-4 font-semibold">Teacher</th>
                    <th className="px-6 py-4 font-semibold">Courses</th>
                    <th className="px-6 py-4 font-semibold">Score</th>
                    <th className="px-6 py-4 font-semibold">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800">
                  {teachers.slice(0, 5).map((teacher) => (
                    <tr key={teacher.id} className="group hover:bg-slate-800/30 transition-colors cursor-pointer">
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-3">
                          <div className="w-8 h-8 rounded-full bg-slate-700 flex items-center justify-center text-xs font-bold text-slate-300">
                            {teacher.full_name[0]}
                          </div>
                          <div>
                            <p className="text-sm font-semibold text-slate-200">{teacher.full_name}</p>
                            <p className="text-xs text-slate-500">{teacher.email}</p>
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4 text-sm text-slate-400">{teacher.course_count}</td>
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-bold text-amber-400">{(teacher.overall_teaching_score || 0).toFixed(1)}</span>
                          <div className="w-20 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                            <div 
                              className="h-full bg-amber-500" 
                              style={{ width: `${(teacher.overall_teaching_score || 0) * 10}%` }}
                            ></div>
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4 text-sm">
                        <span className={`px-2 py-1 rounded-full text-[10px] uppercase font-bold tracking-widest ${
                          teacher.is_active ? 'bg-emerald-500/10 text-emerald-500' : 'bg-red-500/10 text-red-500'
                        }`}>
                          {teacher.is_active ? 'Active' : 'Locked'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Sidebar / Distribution */}
        <div className="space-y-8">
          <div className="bg-slate-900/50 backdrop-blur-xl border border-slate-800 rounded-3xl p-6 shadow-2xl">
            <h3 className="text-xl font-bold text-white mb-6 flex items-center gap-2">
              <Target className="w-5 h-5 text-purple-500" />
              Cognitive Health
            </h3>
            <div className="h-64 flex items-center justify-center">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={[
                      { name: 'Satisfied', value: 70 },
                      { name: 'Neutral', value: 20 },
                      { name: 'At Risk', value: 10 },
                    ]}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={80}
                    paddingAngle={5}
                    dataKey="value"
                  >
                    {COLORS.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="mt-4 space-y-3">
              <div className="flex justify-between items-center text-sm">
                <span className="text-slate-400">Global Avg Engagement</span>
                <span className="text-white font-bold">78%</span>
              </div>
              <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
                <div className="bg-blue-500 h-full w-[78%]"></div>
              </div>
            </div>
          </div>

          <div className="bg-slate-900/50 backdrop-blur-xl border border-slate-800 rounded-3xl p-6 shadow-2xl relative overflow-hidden group">
            <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
              <AlertTriangle className="w-24 h-24 text-red-500" />
            </div>
            <h3 className="text-lg font-bold text-white mb-4">Critical Interventions</h3>
            <div className="space-y-4">
              <div className="bg-red-500/10 border-l-4 border-red-500 p-3 rounded-r-xl">
                <p className="text-xs font-bold text-red-400 uppercase tracking-widest mb-1">Low Engagement Alert</p>
                <p className="text-sm text-slate-300">Physics 101: 14 students dropped 30% below mean.</p>
              </div>
              <div className="bg-amber-500/10 border-l-4 border-amber-500 p-3 rounded-r-xl">
                <p className="text-xs font-bold text-amber-400 uppercase tracking-widest mb-1">Course Underperforming</p>
                <p className="text-sm text-slate-300">Organic Chemistry: High bounce rate on lecture 4.</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function StatCard({ title, value, icon: Icon, trend, color, subtitle }: any) {
  const colorMap: any = {
    blue: 'bg-blue-500/10 text-blue-500 border-blue-500/20',
    emerald: 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20',
    amber: 'bg-amber-500/10 text-amber-500 border-amber-500/20',
    red: 'bg-red-500/10 text-red-500 border-red-500/20',
  };

  return (
    <div className="bg-slate-900/50 backdrop-blur-sm border border-slate-800 p-6 rounded-3xl shadow-xl hover:shadow-2xl hover:border-slate-700 transition-all duration-300 group">
      <div className="flex justify-between items-start mb-4">
        <div className={`p-3 rounded-2xl ${colorMap[color]}`}>
          <Icon className="w-6 h-6" />
        </div>
        <span className={`text-xs font-bold px-2 py-1 rounded-full ${
          trend.includes('+') ? 'bg-emerald-500/10 text-emerald-500' : 'bg-slate-800 text-slate-400'
        }`}>
          {trend}
        </span>
      </div>
      <p className="text-slate-400 text-sm font-medium mb-1">{title}</p>
      <h4 className="text-3xl font-bold text-white mb-1">{value}</h4>
      <p className="text-xs text-slate-500 group-hover:text-slate-400 transition-colors">{subtitle}</p>
    </div>
  );
}
