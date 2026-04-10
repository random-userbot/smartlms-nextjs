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
  color = '#CC3344' 
}: EngagementWaveformProps) {
  
  const { pathData, lineData, ghostLine, latestY } = useMemo(() => {
    if (!data || data.length === 0) return { pathData: '', lineData: '', ghostLine: '', latestY: 100 };

    const engagementValues = data.map(d => d.engagement);
    const minVal = Math.min(...engagementValues);
    const maxVal = Math.max(...engagementValues);
    
    // Smooth the ripple
    const padding = 15;
    const range = Math.max(25, maxVal - minVal);
    const center = (maxVal + minVal) / 2;
    const yMin = Math.max(0, center - (range / 2) - padding);
    const yMax = Math.min(100, center + (range / 2) + padding);
    const dynamicRange = Math.max(1, yMax - yMin);

    const coords: [number, number][] = data.map((pt, i) => {
      const x = (i / Math.max(1, data.length - 1)) * 100;
      const val = isNaN(pt.engagement) ? 50 : pt.engagement;
      const relativePos = (val - yMin) / dynamicRange;
      return [x, 100 - (relativePos * 100)];
    });

    // Create a lagging ghost line
    const ghostCoords: [number, number][] = coords.map(([x, y], i) => {
        const lag = Math.sin(i * 0.5) * 2;
        return [x, y + lag];
    });

    const smoothLine = getSmoothPath(coords);
    const smoothGhost = getSmoothPath(ghostCoords);
    const smoothPath = `${smoothLine} L 100,100 L 0,100 Z`;

    return { 
      pathData: smoothPath, 
      lineData: smoothLine, 
      ghostLine: smoothGhost,
      latestY: coords[coords.length - 1][1]
    };
  }, [data]);

  if (!data || data.length === 0) return (
    <div className="w-full h-full flex items-center justify-center text-primary/30 text-[9px] font-black uppercase tracking-[0.4em] italic">
      Waiting for Neural Sync...
    </div>
  );

  return (
    <div className="w-full h-full relative group">
      <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="w-full h-full overflow-visible">
        <defs>
          <linearGradient id="mainGradient" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity="0.4" />
            <stop offset="60%" stopColor={color} stopOpacity="0.05" />
            <stop offset="100%" stopColor={color} stopOpacity="0" />
          </linearGradient>
          
          <filter id="neonPulse">
            <feGaussianBlur stdDeviation="1.2" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
          </filter>

          <filter id="ghostBlur">
            <feGaussianBlur stdDeviation="2.5" />
          </filter>
        </defs>

        {/* Technical Grid Overlay */}
        <g opacity="0.1">
            {[20, 40, 60, 80].map(y => (
                <line key={y} x1="0" y1={y} x2="100" y2={y} stroke="white" strokeWidth="0.15" strokeDasharray="1,2" />
            ))}
            {[25, 50, 75].map(x => (
                <line key={x} x1={x} y1="0" x2={x} y2="100" stroke="white" strokeWidth="0.15" strokeDasharray="1,2" />
            ))}
        </g>

        {/* Ghost Wave (Lagging Echo) */}
        <motion.path 
          d={ghostLine} 
          fill="none" 
          stroke={color} 
          strokeWidth="0.8" 
          opacity="0.15"
          style={{ filter: 'url(#ghostBlur)' }}
          animate={{ d: ghostLine }}
          transition={{ duration: 1.2, ease: "linear" }}
        />

        {/* Ambient Area Fill */}
        <motion.path 
          d={pathData} 
          fill="url(#mainGradient)"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
        />

        {/* Main Neural Pulse Line */}
        <motion.path 
          d={lineData} 
          fill="none" 
          stroke={color} 
          strokeWidth="1.5" 
          strokeLinecap="round" 
          strokeLinejoin="round"
          animate={{ d: lineData }}
          transition={{ duration: 0.6, ease: "linear" }}
          style={{ filter: 'url(#neonPulse)' }}
        />

        {/* Trailing Sync Node */}
        <motion.g animate={{ y: latestY }} transition={{ duration: 0.6, ease: "linear" }}>
            <circle cx="100" cy="0" r="3" fill={color} opacity="0.2" style={{ filter: 'url(#neonPulse)' }} />
            <motion.circle 
                cx="100" cy="0" r="1.5" 
                fill="white"
                animate={{ scale: [1, 1.8, 1], opacity: [0.8, 1, 0.8] }}
                transition={{ repeat: Infinity, duration: 2 }}
            />
        </motion.g>

        {/* Real-time HUD Elements */}
        <rect x="0" y="0" width="100" height="100" fill="none" stroke="white" strokeWidth="0.2" strokeOpacity="0.05" />
      </svg>

      {/* Foreground Overlays */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden mix-blend-overlay opacity-20">
         <motion.div 
            className="w-full h-1/2 bg-gradient-to-b from-white to-transparent"
            animate={{ top: ['-100%', '200%'] }}
            transition={{ duration: 4, repeat: Infinity, ease: 'linear' }}
         />
      </div>

      <div className="absolute top-2 right-4 flex items-center gap-3">
         <div className="flex flex-col items-end">
            <span className="text-[7px] font-black text-white/40 uppercase tracking-[0.2em]">Neural_Sync</span>
            <span className="text-[10px] font-black text-white tracking-widest italic">{((data[data.length-1]?.engagement || 0)).toFixed(1)}%</span>
         </div>
         <div className={`w-1 h-3 rounded-full animate-pulse ${data[data.length-1]?.engagement > 70 ? 'bg-primary' : 'bg-white/20'}`} />
      </div>
    </div>
  );
}
