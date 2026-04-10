'use client';

import React, { useMemo } from 'react';
import { motion } from 'framer-motion';
import { Activity, Zap, Brain, AlertCircle } from 'lucide-react';

interface HeatPoint {
  timestamp: number;
  engagement: number;
  confusion?: number;
  boredom?: number;
  frustration?: number;
}

interface EngagementHeatmapProps {
  data: HeatPoint[];
}

export default function EngagementHeatmap({ data }: EngagementHeatmapProps) {
  const points = useMemo(() => {
    if (!data || data.length === 0) return [];
    const maxPoints = 150;
    if (data.length <= maxPoints) return data;
    const step = Math.floor(data.length / maxPoints);
    return data.filter((_, i) => i % step === 0);
  }, [data]);

  const { pathData, segments } = useMemo(() => {
    if (points.length < 2) return { pathData: '', segments: [] };
    
    const width = 1000;
    const height = 100;
    const step = width / (points.length - 1);
    
    const segs: { x: number; y: number; color: string; icon: any; label: string }[] = [];
    
    // Create Smooth Cubic Path
    let d = `M 0,${height - points[0].engagement}`;
    
    points.forEach((pt, i) => {
      const x = i * step;
      const y = height - Math.max(5, pt.engagement);
      
      if (i > 0) {
          const prevX = (i - 1) * step;
          const prevY = height - Math.max(5, points[i-1].engagement);
          const cpX1 = prevX + (x - prevX) / 2;
          const cpX2 = prevX + (x - prevX) / 2;
          d += ` C ${cpX1},${prevY} ${cpX2},${y} ${x},${y}`;
      }
      
      let color = '#3b82f6'; // Blue for normal Sync
      let icon = Brain;
      let label = 'SYNC';

      if ((pt.frustration || 0) > 40) { 
        color = '#ef4444'; 
        icon = AlertCircle;
        label = 'FRICTION'; 
      } else if ((pt.confusion || 0) > 40) { 
        color = '#f59e0b'; 
        icon = Zap;
        label = 'STRUGGLE'; 
      } else if (pt.engagement > 80) { 
        color = '#C026D3'; 
        icon = Activity;
        label = 'PEAK'; 
      }
      
      segs.push({ x, y, color, icon, label });
    });
    
    const fillPath = `${d} L 1000,100 L 0,100 Z`;
    return { pathData: fillPath, segments: segs };
  }, [points]);

  if (!data || data.length === 0) {
    return (
      <div className="w-full h-full flex flex-col items-center justify-center bg-white/5 rounded-[2rem] border border-white/5 py-12">
        <div className="w-12 h-12 rounded-2xl bg-white/5 flex items-center justify-center mb-4">
           <Activity size={24} className="text-white/10" />
        </div>
        <div className="text-[10px] font-black text-white/20 uppercase tracking-[0.5em] italic">Telemetry_Stream_Empty</div>
      </div>
    );
  }

  return (
    <div className="w-full h-full flex flex-col space-y-6">
      
      {/* Forensic Header */}
      <div className="flex items-center justify-between px-2">
        <div className="flex items-center gap-4">
          <div className="w-10 h-10 rounded-xl bg-purple-500/10 flex items-center justify-center text-purple-400">
             <Brain size={20} />
          </div>
          <div className="flex flex-col">
             <h4 className="text-[11px] font-black text-foreground uppercase tracking-wider italic">Engagement Intensity Timeline</h4>
             <span className="text-[8px] font-black text-white/30 uppercase tracking-[0.3em]">SESSION_ACTIVITY_DATA</span>
          </div>
        </div>
        
        <div className="flex items-center gap-6">
           {[
             { label: 'Peak', color: 'bg-fuchsia-500' },
             { label: 'Struggle', color: 'bg-amber-500' },
             { label: 'Friction', color: 'bg-red-500' },
             { label: 'Sync', color: 'bg-blue-500' }
           ].map(item => (
             <div key={item.label} className="flex items-center gap-2">
                <div className={`w-1.5 h-1.5 rounded-full ${item.color} shadow-[0_0_8px_rgba(0,0,0,0.5)]`} />
                <span className="text-[8px] font-black text-white/40 uppercase tracking-widest">{item.label}</span>
             </div>
           ))}
        </div>
      </div>

      <div className="flex-1 relative bg-surface/20 rounded-[2rem] border border-white/5 overflow-hidden group">
        <svg viewBox="0 0 1000 100" preserveAspectRatio="none" className="w-full h-full">
          <defs>
            <linearGradient id="forensicGrad" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor="#C026D3" stopOpacity="0.2" />
              <stop offset="60%" stopColor="#C026D3" stopOpacity="0.05" />
              <stop offset="100%" stopColor="#C026D3" stopOpacity="0" />
            </linearGradient>
            
            <filter id="waveGlow">
              <feGaussianBlur stdDeviation="1.5" result="blur" />
              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>
          </defs>

          {/* HUD Grid */}
          <g opacity="0.05">
              {[20, 40, 60, 80].map(y => <line key={y} x1="0" y1={y} x2="1000" y2={y} stroke="white" strokeWidth="1" strokeDasharray="5,10" />)}
              {[100, 200, 300, 400, 500, 600, 700, 800, 900].map(x => <line key={x} x1={x} y1="0" x2={x} y2="100" stroke="white" strokeWidth="1" strokeDasharray="5,10" />)}
          </g>

          {/* Area Map */}
          <motion.path 
            d={pathData}
            fill="url(#forensicGrad)"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
          />

          {/* Continuous Curve */}
          <motion.path 
             d={pathData.split(' L 1000,100')[0]}
             fill="none"
             stroke="#C026D3"
             strokeWidth="1.5"
             strokeOpacity="0.8"
             style={{ filter: 'url(#waveGlow)' }}
             initial={{ pathLength: 0 }}
             animate={{ pathLength: 1 }}
             transition={{ duration: 2.5, ease: "easeInOut" }}
          />

          {/* State Markers */}
          {segments.map((seg, i) => (
            // Only show markers for significant events or at sparse intervals
            (seg.label !== 'SYNC' || i % 15 === 0) && (
              <g key={i}>
                <motion.circle 
                   cx={seg.x} cy={seg.y} r="2.5" 
                   fill={seg.color} 
                   initial={{ scale: 0 }}
                   animate={{ scale: 1 }}
                   transition={{ delay: i * 0.01 }}
                />
                {seg.label !== 'SYNC' && (
                  <>
                    <motion.circle 
                       cx={seg.x} cy={seg.y} r="6" 
                       fill="none" stroke={seg.color} 
                       strokeWidth="0.5" 
                       animate={{ scale: [1, 2], opacity: [0.5, 0] }}
                       transition={{ repeat: Infinity, duration: 2 }}
                    />
                    <text 
                      x={seg.x} y={seg.y - 8} 
                      className="text-[6px] font-black" 
                      fill={seg.color} 
                      textAnchor="middle"
                    >
                      {seg.label}
                    </text>
                  </>
                )}
              </g>
            )
          ))}
        </svg>

        {/* Technical Label Overlays */}
        <div className="absolute top-4 left-4 flex flex-col gap-1">
           <span className="text-[7px] font-black text-white/20 uppercase tracking-[0.2em]">BUFFER_STATUS: STABLE</span>
           <span className="text-[7px] font-black text-white/20 uppercase tracking-[0.2em]">RESOLUTION: 1Hz</span>
        </div>

        {/* Scanning Line */}
        <motion.div 
           className="absolute inset-y-0 w-[2px] bg-gradient-to-b from-transparent via-white/20 to-transparent z-10"
           animate={{ left: ['0%', '100%'] }}
           transition={{ duration: 20, repeat: Infinity, ease: 'linear' }}
        />
      </div>

      {/* Footer Axes */}
      <div className="flex justify-between px-4 text-[8px] font-black text-white/20 uppercase tracking-[0.4em] italic">
        <span>SESSION_ORIGIN</span>
        <div className="flex items-center gap-8">
           <span className="flex items-center gap-2"><div className="w-1 h-3 bg-white/10 rounded-full" /> CH_01: ENGAGEMENT_INDEX</span>
           <span className="flex items-center gap-2"><div className="w-1 h-3 bg-white/10 rounded-full" /> CH_02: BIOMETRIC_LOAD</span>
        </div>
        <span>CURRENT_HORIZON</span>
      </div>
    </div>
  );
}
