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
    
    // Smooth the points slightly or cap them for SVG performance
    const maxPoints = 200;
    if (data.length <= maxPoints) return data;
    
    const step = Math.floor(data.length / maxPoints);
    return data.filter((_, i) => i % step === 0);
  }, [data]);

  const { pathData, segments } = useMemo(() => {
    if (points.length < 2) return { pathData: '', segments: [] };
    
    const width = 1000;
    const height = 100;
    const step = width / (points.length - 1);
    
    let d = `M 0,${height - points[0].engagement}`;
    const segs: { x: number; y: number; color: string }[] = [];
    
    points.forEach((pt, i) => {
      const x = i * step;
      const y = height - Math.max(5, pt.engagement);
      d += ` L ${x},${y}`;
      
      // Map cognitive state to color
      let color = '#3b82f6'; // Flow (Azure)
      if ((pt.frustration || 0) > 30) color = '#ef4444'; // Frustration (Crimson)
      else if ((pt.confusion || 0) > 30) color = '#f59e0b'; // Struggle (Amber)
      else if (pt.engagement > 75) color = '#10b981'; // Focus (Jade)
      
      segs.push({ x, y, color });
    });
    
    // Fill to bottom
    const fillPath = `${d} L ${width},${height} L 0,${height} Z`;
    
    return { pathData: fillPath, segments: segs };
  }, [points]);

  if (!data || data.length === 0) {
    return (
      <div className="w-full h-full flex flex-col items-center justify-center bg-white/5 rounded-3xl border border-white/5 animate-pulse">
        <div className="text-[10px] font-black text-white/20 uppercase tracking-[0.4em] mb-2 text-center">Neural Sync Initializing...</div>
        <div className="w-48 h-1 bg-white/5 rounded-full overflow-hidden">
           <motion.div className="h-full bg-primary" animate={{ x: ['-100%', '100%'] }} transition={{ duration: 1.5, repeat: Infinity }} />
        </div>
      </div>
    );
  }

  return (
    <div className="w-full h-full flex flex-col space-y-4">
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-black text-text-muted uppercase tracking-widest flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-primary animate-ping" /> Global Cognitive Map
        </span>
        <div className="flex gap-4 text-[7px] font-black uppercase tracking-widest opacity-60">
           <span className="flex items-center gap-1"><div className="w-1.5 h-1.5 rounded-full bg-[#10b981]" /> Focus</span>
           <span className="flex items-center gap-1"><div className="w-1.5 h-1.5 rounded-full bg-[#3b82f6]" /> Flow</span>
           <span className="flex items-center gap-1"><div className="w-1.5 h-1.5 rounded-full bg-[#f59e0b]" /> Difficulty</span>
           <span className="flex items-center gap-1"><div className="w-1.5 h-1.5 rounded-full bg-[#ef4444]" /> Friction</span>
        </div>
      </div>

      <div className="flex-1 relative bg-surface/40 rounded-3xl border border-white/5 overflow-hidden group">
        <svg 
          viewBox="0 0 1000 100" 
          preserveAspectRatio="none" 
          className="w-full h-full"
        >
          <defs>
            <linearGradient id="heatGradient" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor="#8833FF" stopOpacity="0.4" />
              <stop offset="100%" stopColor="#8833FF" stopOpacity="0" />
            </linearGradient>
            <filter id="glow">
               <feGaussianBlur stdDeviation="2" result="blur" />
               <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>
          </defs>

          {/* Background Grid Lines */}
          <line x1="0" y1="25" x2="1000" y2="25" stroke="white" strokeOpacity="0.05" strokeDasharray="5,5" />
          <line x1="0" y1="50" x2="1000" y2="50" stroke="white" strokeOpacity="0.05" strokeDasharray="5,5" />
          <line x1="0" y1="75" x2="1000" y2="75" stroke="white" strokeOpacity="0.05" strokeDasharray="5,5" />

          {/* The Waveform Path */}
          <motion.path 
            d={pathData}
            fill="url(#heatGradient)"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
          />

          {/* Color-Coded Segments */}
          {segments.map((seg, i) => (
            i % 2 === 0 && (
              <motion.circle
                key={i}
                cx={seg.x}
                cy={seg.y}
                r="1.2"
                fill={seg.color}
                style={{ filter: 'url(#glow)' }}
                initial={{ opacity: 0, scale: 0 }}
                animate={{ opacity: 0.8, scale: 1 }}
              />
            )
          ))}

          {/* Connection Line */}
          {segments.length > 1 && (
             <motion.path 
               d={`M ${segments.map(s => `${s.x},${s.y}`).join(' L ')}`}
               fill="none"
               stroke="white"
               strokeWidth="0.5"
               strokeOpacity="0.1"
             />
          )}

          {/* Latest Point Indicator */}
          {segments.length > 0 && (
            <motion.circle
              cx={segments[segments.length - 1].x}
              cy={segments[segments.length - 1].y}
              r="4"
              fill={segments[segments.length - 1].color}
              initial={false}
              animate={{ 
                r: [3, 6, 3],
                opacity: [0.5, 1, 0.5]
              }}
              transition={{ repeat: Infinity, duration: 2 }}
              style={{ filter: 'url(#glow)' }}
            />
          )}
        </svg>

        {/* Scanline Overlay */}
        <motion.div 
          className="absolute inset-y-0 w-px bg-white/20 z-10"
          animate={{ left: ['0%', '100%'] }}
          transition={{ duration: 10, repeat: Infinity, ease: 'linear' }}
        />
      </div>

      <div className="flex justify-between px-2 text-[6px] font-black text-text-muted uppercase tracking-[0.2em] opacity-40">
        <span>Session Start</span>
        <span>Forensic Timeline Analysis</span>
        <span>Current Moment</span>
      </div>
    </div>
  );
}
