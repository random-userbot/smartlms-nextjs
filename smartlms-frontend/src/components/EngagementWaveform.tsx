'use client';

import React, { useMemo } from 'react';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import { Activity } from 'lucide-react';

interface DataPoint {
  engagement: number | string;
}

interface EngagementWaveformProps {
  data: DataPoint[];
  color?: string;
  isLive?: boolean;
  mini?: boolean;
}

export default function EngagementWaveform({ 
  data, 
  color = '#CC3344',
  isLive = true,
  mini = false
}: EngagementWaveformProps) {
  
  const chartData = useMemo(() => {
    const validData = Array.isArray(data) ? data : [];
    if (validData.length === 0) return [];

    return validData.map((d, i) => {
      let val = typeof d.engagement === 'number' ? d.engagement : parseFloat(d.engagement as string);
      if (isNaN(val)) val = 50;
      return { index: i, engagement: val };
    });
  }, [data]);

  const currentScore = chartData.length > 0 ? chartData[chartData.length - 1].engagement : 0;

  if (chartData.length === 0) return (
    <div className={`w-full h-full flex flex-col items-center justify-center bg-surface/20 rounded-[2rem] border border-white/5 ${mini ? 'p-2' : 'p-8'}`}>
       <div className={`${mini ? 'w-4 h-4' : 'w-12 h-12'} rounded-2xl bg-white/5 flex items-center justify-center mb-4`}>
          <Activity size={mini ? 16 : 24} className="text-white/20 animate-pulse" />
       </div>
       {!mini && (
         <div className="text-white/20 text-[10px] font-black uppercase tracking-[0.4em] italic text-center">
            Loading Data...
         </div>
       )}
    </div>
  );

  return (
    <div className={`w-full h-full bg-surface/30 rounded-[2.5rem] border border-white/5 ${mini ? 'p-3' : 'p-6'} flex flex-col relative overflow-hidden group transition-all hover:bg-surface/40`}>
      
      {/* Header Section */}
      {!mini && (
        <div className="flex items-center justify-between mb-4 z-10">
          <div className="flex flex-col">
            <h3 className="text-base font-bold text-foreground">Class Engagement</h3>
          </div>
          
          <div className="flex items-center gap-4">
            <div className="flex flex-col items-end">
              <span className="text-[10px] font-bold text-text-muted">CURRENT</span>
              <span className="text-xl font-black text-foreground">{currentScore.toFixed(1)}%</span>
            </div>
            {isLive && (
              <div className="px-3 py-1 bg-success/10 border border-success/20 rounded-xl flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-success animate-pulse" />
                <span className="text-[10px] font-bold text-success uppercase">Live</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Main Chart Area */}
      <div className={`flex-1 w-full relative ${mini ? 'min-h-0' : 'min-h-[150px]'}`}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
            <XAxis dataKey="index" hide />
            <YAxis domain={[0, 100]} hide />
            <Tooltip 
              contentStyle={{ backgroundColor: '#111', borderColor: 'rgba(255,255,255,0.1)', borderRadius: '1rem', fontSize: '12px' }}
              itemStyle={{ color: '#fff', fontWeight: 'bold' }}
              labelStyle={{ display: 'none' }}
              formatter={(val: any) => [`${parseFloat(val || 0).toFixed(1)}%`, 'Focus']}
            />
            <Line 
              type="monotone" 
              dataKey="engagement" 
              stroke={color} 
              strokeWidth={3} 
              dot={false}
              activeDot={{ r: 6, fill: color, stroke: '#111', strokeWidth: 2 }}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
