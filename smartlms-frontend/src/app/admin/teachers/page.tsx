"use client";

import React, { useEffect, useState } from 'react';
import { 
  Users, 
  Search, 
  Plus, 
  MoreVertical, 
  CheckCircle, 
  XCircle, 
  Mail, 
  ExternalLink,
  BookOpen,
  TrendingDown,
  TrendingUp,
  BarChart,
  ShieldCheck,
  Award,
  Lock,
  Unlock
} from 'lucide-react';
import { adminAPI } from '@/lib/api';

export default function TeachersPage() {
  const [teachers, setTeachers] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

  const fetchTeachers = async () => {
    try {
      const data = await adminAPI.listTeachers();
      setTeachers(data.data);
    } catch (err) {
      console.error('Failed to fetch teachers:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTeachers();
  }, []);

  const handleToggleStatus = async (id: string) => {
    try {
      await adminAPI.toggleUserActive(id);
      fetchTeachers();
    } catch (err) {
      console.error('Failed to toggle status:', err);
    }
  };

  const filteredTeachers = teachers.filter(t => 
    t.full_name.toLowerCase().includes(search.toLowerCase()) || 
    t.email.toLowerCase().includes(search.toLowerCase())
  );

  if (loading) return (
    <div className="flex items-center justify-center h-96">
      <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
    </div>
  );

  return (
    <div className="space-y-8 animate-in slide-in-from-right duration-700">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-white mb-2 flex items-center gap-2">
            <Users className="w-8 h-8 text-emerald-500" />
            Teacher Management
          </h1>
          <p className="text-slate-400">Moderating SmartLMS instructional excellence and content integrity</p>
        </div>
        
        <button className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white px-6 py-3 rounded-2xl font-bold transition-all shadow-lg shadow-blue-500/20 active:scale-95 group">
          <Plus className="w-5 h-5 group-hover:rotate-90 transition-transform duration-300" />
          Onboard New Teacher
        </button>
      </div>

      <div className="bg-slate-900/50 backdrop-blur-xl border border-slate-800 rounded-3xl p-8 shadow-2xl flex flex-col md:flex-row gap-6 md:items-center justify-between">
        <div className="relative flex-1 max-w-lg">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-500" />
          <input 
            type="text" 
            placeholder="Search teachers by name, email, or course..." 
            className="w-full bg-slate-950/50 border border-slate-800 rounded-2xl py-3 pl-12 pr-4 text-sm focus:outline-none focus:border-blue-500/50 transition-all focus:ring-4 focus:ring-blue-500/5"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        
        <div className="flex items-center gap-4">
           <div className="bg-emerald-500/10 border border-emerald-500/20 px-4 py-2 rounded-xl flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
              <span className="text-xs font-bold text-emerald-500 uppercase tracking-widest">Active: {teachers.filter(t => t.is_active).length}</span>
           </div>
           <div className="bg-red-500/10 border border-red-500/20 px-4 py-2 rounded-xl flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-red-500"></span>
              <span className="text-xs font-bold text-red-500 uppercase tracking-widest">Locked: {teachers.filter(t => !t.is_active).length}</span>
           </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6">
        {filteredTeachers.map((teacher) => (
          <div key={teacher.id} className="bg-slate-900/50 backdrop-blur-xl border border-slate-800 rounded-3xl p-6 shadow-xl hover:border-slate-700 transition-all group overflow-hidden relative">
            <div className="absolute top-0 right-0 p-8 opacity-5 group-hover:opacity-10 transition-opacity">
              <Award className="w-40 h-40 text-blue-500" />
            </div>
            
            <div className="flex flex-col xl:flex-row gap-8 items-start xl:items-center relative z-10">
              {/* Profile Section */}
              <div className="flex items-center gap-6 min-w-[300px]">
                <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-slate-800 to-slate-900 border border-slate-700 flex items-center justify-center text-3xl font-black text-slate-100 shadow-xl group-hover:scale-105 transition-transform duration-500">
                  {teacher.full_name[0]}
                </div>
                <div>
                  <h3 className="text-xl font-bold text-white mb-1 flex items-center gap-2">
                    {teacher.full_name}
                    {teacher.is_active ? <ShieldCheck className="w-4 h-4 text-emerald-500" /> : <Lock className="w-4 h-4 text-red-500" />}
                  </h3>
                  <div className="flex items-center gap-2 text-sm text-slate-400 mb-1">
                    <Mail className="w-3 h-3" />
                    {teacher.email}
                  </div>
                  <p className="text-xs text-slate-600 uppercase tracking-widest font-black">Teacher ID: {teacher.id.slice(0, 8)}</p>
                </div>
              </div>

              {/* Stats Section */}
              <div className="flex-1 grid grid-cols-2 md:grid-cols-4 gap-4 w-full xl:w-auto">
                 <div className="bg-slate-950/50 border border-slate-800/50 p-4 rounded-2xl group-hover:bg-slate-950 transition-colors">
                    <p className="text-[10px] uppercase font-bold text-slate-600 tracking-widest mb-1 flex items-center gap-1">
                      <BookOpen className="w-3 h-3" /> Courses
                    </p>
                    <p className="text-xl font-black text-slate-200">{teacher.course_count}</p>
                 </div>
                 
                 <div className="bg-slate-950/50 border border-slate-800/50 p-4 rounded-2xl group-hover:bg-slate-950 transition-colors">
                    <p className="text-[10px] uppercase font-bold text-slate-600 tracking-widest mb-1 flex items-center gap-1">
                      <TrendingUp className="w-3 h-3" /> Pedagogical Score
                    </p>
                    <div className="flex items-baseline gap-1">
                      <p className="text-xl font-black text-amber-500">{(teacher.overall_teaching_score || 0).toFixed(1)}</p>
                      <span className="text-[10px] text-slate-500">/ 10.0</span>
                    </div>
                 </div>
                 
                 <div className="bg-slate-950/50 border border-slate-800/50 p-4 rounded-2xl group-hover:bg-slate-950 transition-colors">
                    <p className="text-[10px] uppercase font-bold text-slate-600 tracking-widest mb-1 flex items-center gap-1">
                      <BarChart className="w-3 h-3" /> Last Active
                    </p>
                    <p className="text-sm font-bold text-slate-300">
                      {teacher.last_login ? new Date(teacher.last_login).toLocaleDateString() : 'N/A'}
                    </p>
                 </div>
                 
                 <div className="bg-slate-950/50 border border-slate-800/50 p-4 rounded-2xl group-hover:bg-slate-950 transition-colors flex items-center justify-between">
                    <div>
                      <p className="text-[10px] uppercase font-bold text-slate-600 tracking-widest mb-1">Status</p>
                      <p className={`text-sm font-bold ${teacher.is_active ? 'text-emerald-500' : 'text-red-500'}`}>
                        {teacher.is_active ? 'Active' : 'Locked'}
                      </p>
                    </div>
                    <button 
                      onClick={() => handleToggleStatus(teacher.id)}
                      className={`p-2 rounded-xl transition-all duration-300 ${
                        teacher.is_active ? 'text-slate-500 hover:bg-red-500/10 hover:text-red-500' : 'text-emerald-500 hover:bg-emerald-500/10'
                      }`}
                    >
                      {teacher.is_active ? <Lock className="w-5 h-5" /> : <Unlock className="w-5 h-5" />}
                    </button>
                 </div>
              </div>

              {/* Actions */}
              <div className="flex gap-2 w-full xl:w-auto">
                 <button className="flex-1 xl:flex-none flex items-center justify-center gap-2 bg-slate-800 hover:bg-slate-700 text-slate-300 px-6 py-3 rounded-2xl font-bold transition-all active:scale-95">
                   <ExternalLink className="w-4 h-4" />
                   Review Analytics
                 </button>
                 <button className="p-3 bg-slate-800 hover:bg-slate-700 text-slate-500 rounded-2xl transition-all active:scale-95">
                   <MoreVertical className="w-5 h-5" />
                 </button>
              </div>
            </div>

            {/* Score Breakdown Sparklines placeholder */}
            {teacher.score_breakdown && (
              <div className="mt-6 pt-6 border-t border-slate-800/50 grid grid-cols-2 lg:grid-cols-4 gap-8">
                 {Object.entries(teacher.score_breakdown).slice(0, 4).map(([key, value]: any) => (
                   <div key={key}>
                      <div className="flex justify-between text-[10px] uppercase font-black text-slate-600 mb-1">
                        <span>{key.replace(/_/g, ' ')}</span>
                        <span className="text-blue-500 font-black">{Math.round(value * 100)}%</span>
                      </div>
                      <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
                        <div className="bg-blue-600 h-full transition-all duration-1000" style={{ width: `${value * 100}%` }}></div>
                      </div>
                   </div>
                 ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
