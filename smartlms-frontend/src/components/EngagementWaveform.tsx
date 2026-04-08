'use client';

import React, { useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

interface DataPoint {
  engagement: number;
}

interface EngagementWaveformProps {
  data: DataPoint[];
  height?: number;
  color?: string;
}

/**
 * Creates a smooth Bezier path from a set of points.
 * @param points Array of [x, y] coordinates
 * @returns SVG path string
 */
const getSmoothPath = (points: [number, number][]) => {
  if (points.length < 2) return '';
  
  let d = `M ${points[0][0]},${points[0][1]}`;
  
  for (let i = 0; i < points.length - 1; i++) {
    const curr = points[i];
    const next = points[i + 1];
    const midX = (curr[0] + next[0]) / 2;
    const midY = (curr[1] + next[1]) / 2;
    
    // We use a quadratic curve for simplicity and performance in live streams
    d += ` Q ${curr[0]},${curr[1]} ${midX},${midY}`;
  }
  
  const last = points[points.length - 1];
  d += ` L ${last[0]},${last[1]}`;
  
  return d;
};

export default function EngagementWaveform({ 
  data, 
  height = 100, 
  color = '#CC3344' 
}: EngagementWaveformProps) {
  
  const { pathData, lineData, points, latestY } = useMemo(() => {
    if (!data || data.length === 0) return { pathData: '', lineData: '', points: [], latestY: 100 };

    // 1. Calculate relative scaling to avoid 'flat bar' look
    // Even if scores are high (e.g. 75, 76, 75), we want to see the ripple.
    const engagementValues = data.map(d => d.engagement);
    const minVal = Math.min(...engagementValues);
    const maxVal = Math.max(...engagementValues);
    
    // Ensure at least a 20% vertical range for visible 'waves'
    const padding = 10;
    const range = Math.max(20, maxVal - minVal);
    const center = (maxVal + minVal) / 2;
    const yMin = Math.max(0, center - (range / 2) - padding);
    const yMax = Math.min(100, center + (range / 2) + padding);
    
    // Safety check: Avoid division by zero
    const dynamicRange = Math.max(1, yMax - yMin);

    const coords: [number, number][] = data.map((pt, i) => {
      const x = (i / Math.max(1, data.length - 1)) * 100;
      
      // Safety check: handle NaN or undefined engagement
      const val = isNaN(pt.engagement) || pt.engagement === undefined ? 50 : pt.engagement;
      
      // Map engagement 0..100 to 100..0 with dynamic scaling
      const relativePos = (val - yMin) / dynamicRange;
      const y = 100 - (relativePos * 100);
      return [x, isNaN(y) ? 50 : y];
    });

    const smoothLine = getSmoothPath(coords);
    const smoothPath = `${smoothLine} L 100,100 L 0,100 Z`;

    return { 
      pathData: smoothPath, 
      lineData: smoothLine, 
      points: coords,
      latestY: coords[coords.length - 1][1]
    };
  }, [data]);

  if (!data || data.length === 0) return (
    <div className="w-full h-full flex items-center justify-center text-text-muted text-[10px] font-black uppercase tracking-[0.2em] opacity-50">
      <div className="flex flex-col items-center gap-4">
        <div className="w-12 h-[1px] bg-white/10 animate-pulse" />
        No focus data yet
      </div>
    </div>
  );

  return (
    <div className="w-full h-full relative group">
      <svg 
        viewBox="0 0 100 100" 
        preserveAspectRatio="none" 
        className="w-full h-full"
      >
        <defs>
          <linearGradient id="cyberGradient" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity="0.3" />
            <stop offset="60%" stopColor={color} stopOpacity="0.05" />
            <stop offset="100%" stopColor={color} stopOpacity="0" />
          </linearGradient>
          
          <filter id="cyberGlow">
            <feGaussianBlur stdDeviation="1.5" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
          </filter>
        </defs>

        {/* Dynamic Grid Alignment Lines */}
        <line x1="0" y1="20" x2="100" y2="20" stroke="white" strokeOpacity="0.03" strokeDasharray="2,2" />
        <line x1="0" y1="50" x2="100" y2="50" stroke="white" strokeOpacity="0.03" strokeDasharray="2,2" />
        <line x1="0" y1="80" x2="100" y2="80" stroke="white" strokeOpacity="0.03" strokeDasharray="2,2" />

        {/* Background 'Pulse Echo' Path (Delayed/Faded) */}
        <motion.path 
          d={pathData} 
          fill="url(#cyberGradient)"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 1 }}
        />

        {/* Main Focus Line */}
        <motion.path 
          d={lineData} 
          fill="none" 
          stroke={color} 
          strokeWidth="1.2" 
          strokeLinecap="round" 
          strokeLinejoin="round"
          initial={false}
          animate={{ d: lineData }}
          transition={{ duration: 0.8, ease: "linear" }}
          style={{ filter: 'url(#cyberGlow)' }}
          className="drop-shadow-[0_0_12px_rgba(204,51,68,0.5)]"
        />

        {/* Trailing Active Node (Pulsing Dot) */}
        <AnimatePresence mode="wait">
          <motion.circle 
            key="latest-dot"
            cx="100"
            cy={latestY}
            r="1.8"
            fill={color}
            initial={{ scale: 0 }}
            animate={{ scale: [1, 1.8, 1] }}
            transition={{ repeat: Infinity, duration: 1.5 }}
            style={{ filter: 'url(#cyberGlow)' }}
          />
        </AnimatePresence>

        {/* Scanline Effect */}
        <motion.rect
          x="-1"
          y="0"
          width="2"
          height="100"
          fill={color}
          fillOpacity="0.1"
          animate={{ x: ["0%", "100%", "0%"] }}
          transition={{ duration: 8, repeat: Infinity, ease: "linear" }}
        />
      </svg>

      {/* Session Details */}
      <div className="absolute top-4 left-6 flex flex-col gap-1 pointer-events-none">
        <span className="text-[8px] font-black text-text-muted hover:text-white transition-colors tracking-widest uppercase">
          Focus Change: {((Math.max(...data.map(d => d.engagement)) - Math.min(...data.map(d => d.engagement))) || 0).toFixed(1)}%
        </span>
        <div className="h-1 w-24 bg-white/5 rounded-full overflow-hidden">
          <motion.div 
            className="h-full bg-primary" 
            animate={{ width: `${Math.min(100, data[data.length-1]?.engagement || 0)}%` }} 
          />
        </div>
      </div>
    </div>
  );
}
