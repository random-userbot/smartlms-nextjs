'use client';

import React, { useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

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
    
    const segs: { x: number; y: number; color: string; label: string }[] = [];
    
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
      
      let color = '#3b82f6'; 
      let label = 'SYNC';
      if ((pt.frustration || 0) > 30) { color = '#ef4444'; label = 'FRICTION'; }
      else if ((pt.confusion || 0) > 30) { color = '#f59e0b'; label = 'STRUGGLE'; }
      else if (pt.engagement > 80) { color = '#C026D3'; label = 'PEAK'; }
      
      segs.push({ x, y, color, label });
    });
    
    const fillPath = `${d} L 1000,100 L 0,100 Z`;
    return { pathData: fillPath, segments: segs };
  }, [points]);

  if (!data || data.length === 0) {
    return (
      <div className="w-full h-full flex flex-col items-center justify-center bg-white/5 rounded-3xl border border-white/5">
        <div className="text-[9px] font-black text-white/10 uppercase tracking-[0.5em]">Forensic_Buffer_Empty</div>
      </div>
    );
  }

  return (
    <div className="w-full h-full flex flex-col space-y-4">
      <div className="flex items-center justify-between px-2">
        <div className="flex items-center gap-4">
            <span className="text-[9px] font-black text-white/40 uppercase tracking-widest flex items-center gap-2">
                <div className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse shadow-[0_0_8px_rgba(204,51,68,0.5)]" /> 
                Forensic Timeline
            </span>
        </div>
        <div className="flex gap-4 text-[7px] font-black uppercase tracking-widest opacity-40">
           {['Sync', 'Struggle', 'Friction', 'Peak'].map((tag, idx) => (
               <span key={tag} className="flex items-center gap-1.5">
                   <div className={`w-1 h-1 rounded-full ${idx === 0 ? 'bg-blue-400' : idx === 1 ? 'bg-amber-400' : idx === 2 ? 'bg-red-400' : 'bg-fuchsia-400'}`} />
                   {tag}
               </span>
           ))}
        </div>
      </div>

      <div className="flex-1 relative bg-surface/20 rounded-2xl border border-white/5 overflow-hidden group">
        <svg viewBox="0 0 1000 100" preserveAspectRatio="none" className="w-full h-full">
          <defs>
            <linearGradient id="forensicGrad" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor="#C026D3" stopOpacity="0.2" />
              <stop offset="100%" stopColor="#C026D3" stopOpacity="0" />
            </linearGradient>
          </defs>

          {/* HUD Grid */}
          <g opacity="0.05">
              {[25, 50, 75].map(y => <line key={y} x1="0" y1={y} x2="1000" y2={y} stroke="white" strokeWidth="1" strokeDasharray="10,20" />)}
              {[200, 400, 600, 800].map(x => <line key={x} x1={x} y1="0" x2={x} y2="100" stroke="white" strokeWidth="1" strokeDasharray="5,15" />)}
          </g>

          {/* Area Map */}
          <motion.path 
            d={pathData}
            fill="url(#forensicGrad)"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
          />

          {/* State Nodes */}
          {segments.map((seg, i) => (
            i % 5 === 0 && (
              <g key={i}>
                <circle cx={seg.x} cy={seg.y} r="1.5" fill={seg.color} opacity="0.5" />
                {seg.label !== 'SYNC' && (
                    <circle cx={seg.x} cy={seg.y} r="3" fill="none" stroke={seg.color} strokeWidth="0.5" className="animate-ping" />
                )}
              </g>
            )
          ))}

          {/* Continuous Curve */}
          <motion.path 
             d={pathData.split(' L 1000,100')[0]} // Just the line, not the fill
             fill="none"
             stroke="white"
             strokeWidth="1"
             strokeOpacity="0.15"
             initial={{ pathLength: 0 }}
             animate={{ pathLength: 1 }}
             transition={{ duration: 2 }}
          />
        </svg>

        {/* HUD Scanning Line */}
        <motion.div 
           className="absolute inset-y-0 w-[2px] bg-gradient-to-b from-transparent via-white/40 to-transparent z-10"
           animate={{ left: ['0%', '100%'] }}
           transition={{ duration: 15, repeat: Infinity, ease: 'linear' }}
        />
      </div>

      <div className="flex justify-between px-4 text-[7px] font-black text-white/20 uppercase tracking-[0.3em]">
        <span>SESSION_BOOT</span>
        <span className="animate-pulse">COGNITIVE_RESONANCE_MONITOR: ACTIVE</span>
        <span>REAL_TIME</span>
      </div>
    </div>
  );
}
