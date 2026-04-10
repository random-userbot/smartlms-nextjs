'use client';

import React, { useState, useEffect } from 'react';
import { 
  LineChart, 
  Line, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer, 
  Legend 
} from 'recharts';
import { analyticsAPI } from '@/lib/api';
import { Users, Activity, Filter, Clock } from 'lucide-react';

interface MultiStudentWavesProps {
  lectureId: string;
  selectedStudentIds?: string[];
}

export default function MultiStudentWaves({ 
  lectureId, 
  selectedStudentIds = [] 
}: { 
  lectureId: string; 
  selectedStudentIds?: string[];
}) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!lectureId) return;
    setLoading(true);
    
    const studentIdsParam = selectedStudentIds.length > 0 ? selectedStudentIds.join(',') : undefined;
    
    analyticsAPI.getLectureWaves(lectureId, studentIdsParam)
      .then(res => {
        // Transform data for Recharts
        // The API returns { timeline: [0, 1, 2...], students: [{ name, wave: [score,...] }] }
        // Recharts needs [ { minute: 0, studentA: 80, studentB: 70 }, ... ]
        const timeline = Array.isArray(res.data?.timeline) ? res.data.timeline : [];
        const students = Array.isArray(res.data?.students) ? res.data.students : [];
        
        const chartData = timeline.map((min: number, idx: number) => {
          const point: any = { minute: min };
          students.forEach((s: any) => {
            if (s && s.wave && Array.isArray(s.wave)) {
              point[s.student_name] = s.wave[idx];
            }
            // Store lapses as hidden properties for the custom tooltip
            point[`${s.student_name}_lapses`] = (s && Array.isArray(s.lapse_wave)) ? s.lapse_wave[idx] : 0;
            point[`${s.student_name}_tabs`] = (s && Array.isArray(s.tab_wave)) ? s.tab_wave[idx] : 0;
          });
          return point;
        });
        
        setData({
          chartData,
          studentNames: students.map((s: any) => s.student_name || 'Unknown')
        });
      })
      .catch(err => console.error("Failed to fetch wave data:", err))
      .finally(() => setLoading(false));
  }, [lectureId, selectedStudentIds]);

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-[#111] border border-white/10 p-4 rounded-2xl shadow-2xl backdrop-blur-xl">
          <div className="text-[10px] font-black text-text-muted uppercase tracking-widest mb-3 flex items-center gap-2">
            <Clock size={10} /> Minute {label}
          </div>
          <div className="space-y-2">
            {payload.map((p: any, i: number) => {
              const lapses = p.payload[`${p.name}_lapses`];
              const tabs = p.payload[`${p.name}_tabs`];
              return (
                <div key={i} className="flex flex-col gap-1.5 border-l-2 pl-3 py-1" style={{ borderColor: p.color }}>
                   <div className="flex items-center justify-between gap-6">
                      <span className="text-xs font-bold text-white">{p.name}</span>
                      <span className="text-xs font-black text-white">{p.value?.toFixed(1)}%</span>
                   </div>
                   <div className="flex flex-col gap-1">
                     {lapses > 0 && (
                       <div className="flex items-center gap-1.5 animate-pulse">
                          <Activity size={10} className="text-primary" />
                          <span className="text-[9px] font-black text-primary uppercase tracking-tighter">
                            {lapses} visibility lapses
                          </span>
                       </div>
                     )}
                     {tabs > 0 && (
                       <div className="flex items-center gap-1.5">
                          <Filter size={10} className="text-info" />
                          <span className="text-[9px] font-black text-info uppercase tracking-tighter">
                            {tabs} tab switches
                          </span>
                       </div>
                     )}
                   </div>
                </div>
              );
            })}
          </div>
        </div>
      );
    }
    return null;
  };

  if (loading) {
    return (
      <div className="w-full h-[400px] flex items-center justify-center bg-white/5 rounded-3xl border border-white/5">
        <div className="flex flex-col items-center gap-4">
          <div className="w-10 h-10 border-4 border-primary/20 border-t-primary rounded-full animate-spin"></div>
          <div className="text-[10px] font-black text-text-muted uppercase tracking-widest">Hydrating Wave Engine...</div>
        </div>
      </div>
    );
  }

  if (!data || data.chartData.length === 0) {
    return (
      <div className="w-full h-[400px] flex items-center justify-center bg-white/5 rounded-3xl border border-white/5 text-text-muted text-xs font-bold uppercase tracking-widest">
        No waveform data detected for this segment.
      </div>
    );
  }

  // Predefined high-fidelity colors
  const colors = ['#CC3344', '#4488FF', '#FFBB33', '#33CC99', '#AA66FF', '#FF8844'];

  return (
    <div className="w-full h-[450px] glass-card p-8 space-y-6 relative overflow-hidden group">
      <div className="flex items-center justify-between relative z-10">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-primary/20 rounded-xl border border-primary/40">
            <Activity size={20} className="text-primary" />
          </div>
          <div>
            <h3 className="text-xl font-black text-white tracking-tight">Collective Engagement Waves</h3>
            <p className="text-[10px] font-bold text-text-muted uppercase tracking-widest">1-Minute Resolution Pulse</p>
          </div>
        </div>
        <div className="flex items-center gap-4">
           <div className="hidden md:flex items-center gap-2 px-4 py-2 bg-white/5 rounded-full border border-white/10">
             <div className="w-2 h-2 bg-primary rounded-full animate-pulse"></div>
             <span className="text-[10px] font-black text-white uppercase tracking-widest">Live Flow</span>
           </div>
        </div>
      </div>

      <div className="h-[320px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data.chartData} margin={{ top: 20, right: 30, left: 0, bottom: 0 }}>
            <defs>
              {data.studentNames.map((name: string, i: number) => (
                <linearGradient key={`grad-${i}`} id={`color-${i}`} x1="0" y2="1">
                  <stop offset="5%" stopColor={colors[i % colors.length]} stopOpacity={0.8}/>
                  <stop offset="95%" stopColor={colors[i % colors.length]} stopOpacity={0.1}/>
                </linearGradient>
              ))}
            </defs>
            <CartesianGrid strokeDasharray="10 10" stroke="#ffffff05" vertical={true} />
            <XAxis 
              dataKey="minute" 
              stroke="#ffffff20" 
              fontSize={10} 
              tickLine={false} 
              axisLine={false}
              label={{ value: 'TELEMETRY_TIMELINE', position: 'insideBottomRight', offset: -5, fill: '#ffffff20', fontSize: 8, fontWeight: 'black', letterSpacing: '0.2em' }}
            />
            <YAxis 
              stroke="#ffffff20" 
              fontSize={10} 
              tickLine={false} 
              axisLine={false}
              domain={[0, 100]}
              label={{ value: 'SYNC_INDEX', angle: -90, position: 'insideLeft', fill: '#ffffff20', fontSize: 8, fontWeight: 'black', letterSpacing: '0.2em' }}
            />
            <Tooltip 
              content={<CustomTooltip />}
            />
            <Legend iconType="circle" wrapperStyle={{ paddingTop: '20px', fontSize: '10px', fontWeight: 'bold', textTransform: 'uppercase', letterSpacing: '0.1em' }} />
            {data.studentNames.map((name: string, i: number) => (
              <Line 
                key={name}
                type="monotone" 
                dataKey={name} 
                stroke={colors[i % colors.length]} 
                strokeWidth={3}
                dot={false}
                activeDot={{ r: 6, fill: colors[i % colors.length], stroke: '#fff', strokeWidth: 2 }}
                animationDuration={1500}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="absolute top-0 right-0 p-12 opacity-5 pointer-events-none">
        <Users size={200} className="text-white" />
      </div>
    </div>
  );
}
