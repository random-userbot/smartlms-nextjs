'use client';

import React, { useMemo } from 'react';
import { motion } from 'framer-motion';
import { Activity } from 'lucide-react';

interface DataPoint {
  engagement: number;
}

interface EngagementWaveformProps {
  data: DataPoint[];
  color?: string;
  isLive?: boolean;
}

const getSmoothPath = (points: [number, number][]) => {
  if (points.length < 2) return '';
  let d = `M ${points[0][0]},${points[0][1]}`;
  for (let i = 0; i < points.length - 1; i++) {
    const curr = points[i];
    const next = points[i + 1];
    const midX = (curr[0] + next[0]) / 2;
    const midY = (curr[1] + next[1]) / 2;
    d += ` Q ${curr[0]},${curr[1]} ${midX},${midY}`;
  }
  const last = points[points.length - 1];
  d += ` L ${last[0]},${last[1]}`;
  return d;
};

export default function EngagementWaveform({ 
  data, 
  color = '#CC3344',
  isLive = true
}: EngagementWaveformProps) {
  
  const { lineData, latestY } = useMemo(() => {
    if (!data || !Array.isArray(data) || data.length === 0) return { lineData: '', latestY: 100 };

    const engagementValues = data.map(d => d.engagement).filter(v => typeof v === 'number' && !isNaN(v));
    if (engagementValues.length === 0) return { lineData: '', latestY: 100 };
    
    const minVal = Math.min(...engagementValues);
    const maxVal = Math.max(...engagementValues);
    
    const padding = 15;
    const range = Math.max(25, maxVal - minVal);
    const center = (maxVal + minVal) / 2;
    const yMin = Math.max(0, center - (range / 2) - padding);
    const yMax = Math.min(100, center + (range / 2) + padding);
    const dynamicRange = Math.max(1, yMax - yMin);

    const coords: [number, number][] = data.map((pt, i) => {
      const x = (i / Math.max(1, data.length - 1)) * 100;
      let val = typeof pt.engagement === 'number' && !isNaN(pt.engagement) ? pt.engagement : 50;
      const relativePos = dynamicRange > 0 ? (val - yMin) / dynamicRange : 0.5;
      const y = 100 - (relativePos * 100);
      return [x, isNaN(y) ? 50 : y];
    });

    const smoothLine = getSmoothPath(coords);

    return { 
      lineData: smoothLine, 
      latestY: coords[coords.length - 1][1]
    };
  }, [data]);

  if (!data || data.length === 0) return (
    <div className="w-full h-full flex flex-col items-center justify-center bg-surface/20 rounded-[2rem] border border-white/5 p-8">
       <div className="w-12 h-12 rounded-2xl bg-white/5 flex items-center justify-center mb-4">
          <Activity size={24} className="text-white/20 animate-pulse" />
       </div>
       <div className="text-white/20 text-[10px] font-black uppercase tracking-[0.4em] italic text-center">
          Searching for Telemetry Stream...
       </div>
    </div>
  );

  return (
    <div className="w-full h-full bg-surface/30 rounded-[2.5rem] border border-white/5 p-8 flex flex-col relative overflow-hidden group transition-all hover:bg-surface/40">
      
      {/* Header Section */}
      <div className="flex items-center justify-between mb-8 z-10">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-2xl bg-primary/10 flex items-center justify-center text-primary crimson-glow">
            <Activity size={24} />
          </div>
          <div className="flex flex-col">
            <h3 className="text-base font-black text-foreground uppercase tracking-wider italic">Class Engagement Timeline</h3>
            <span className="text-[9px] font-black text-white/30 uppercase tracking-[0.3em]">1-MINUTE ACTIVITY RESOLUTION</span>
          </div>
        </div>
        
        <div className="flex items-center gap-4">
          <div className="flex flex-col items-end">
            <span className="text-[9px] font-black text-white/40 uppercase tracking-widest">Global INDEX</span>
            <span className="text-xl font-black text-foreground tracking-tighter italic">{(data[data.length-1]?.engagement || 0).toFixed(1)}%</span>
          </div>
          {isLive && (
            <div className="px-4 py-2 bg-success/10 border border-success/20 rounded-xl flex items-center gap-3">
              <div className="w-2 h-2 rounded-full bg-success animate-pulse shadow-[0_0_8px_rgba(34,197,94,0.5)]" />
              <span className="text-[9px] font-black text-success uppercase tracking-widest">LIVE FLOW</span>
            </div>
          )}
        </div>
      </div>

      {/* Main Wave Area */}
      <div className="flex-1 relative">
        <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="w-full h-full overflow-visible">
          <defs>
            <filter id="simpleLineGlow">
              <feGaussianBlur stdDeviation="0.8" result="blur" />
              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>
          </defs>

          {/* Technical Grid Overlay (Minimal) */}
          <g opacity="0.05">
              {[25, 50, 75].map(y => (
                  <line key={y} x1="0" y1={y} x2="100" y2={y} stroke="white" strokeWidth="0.1" strokeDasharray="1,2" />
              ))}
          </g>

          {/* Main Engagement Line */}
          <motion.path 
            d={lineData} 
            fill="none" 
            stroke={color} 
            strokeWidth="1.2" 
            strokeLinecap="round" 
            strokeLinejoin="round"
            animate={{ d: lineData }}
            transition={{ duration: 0.8, ease: "linear" }}
            style={{ filter: 'url(#simpleLineGlow)' }}
          />

          {/* Trailing Node */}
          <motion.circle 
              animate={{ cy: latestY }}
              cx="100" r="1.2" 
              fill={color}
              className="crimson-glow"
              transition={{ duration: 0.8, ease: "linear" }}
          />
        </svg>

        {/* X-Axis Label */}
        <div className="absolute -bottom-6 left-1/2 -translate-x-1/2 whitespace-nowrap">
           <span className="text-[8px] font-black text-white/10 uppercase tracking-[0.4em]">REAL_TIME_ENROLLMENT_STREAM</span>
        </div>
      </div>
    </div>
  );
}
