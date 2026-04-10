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
  
  const { pathData, lineData, ghostLine, latestY } = useMemo(() => {
    if (!data || !Array.isArray(data) || data.length === 0) return { pathData: '', lineData: '', ghostLine: '', latestY: 100 };

    const engagementValues = Array.isArray(data) ? data.map(d => d.engagement || 0) : [0];
    const safeEngagementValues = engagementValues.length > 0 ? engagementValues : [0];
    const minVal = Math.min(...safeEngagementValues);
    const maxVal = Math.max(...safeEngagementValues);
    
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
        {/* Y-Axis Label */}
        <div className="absolute -left-6 top-1/2 -translate-y-1/2 -rotate-90 origin-center whitespace-nowrap">
           <span className="text-[8px] font-black text-white/20 uppercase tracking-[0.4em]">ENGAGEMENT_INDEX</span>
        </div>

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
                  <line key={y} x1="0" y1={y} x2="100" y2={y} stroke="white" strokeWidth="0.1" strokeDasharray="1,2" />
              ))}
              {[25, 50, 75].map(x => (
                  <line key={x} x1={x} y1="0" x2={x} y2="100" stroke="white" strokeWidth="0.1" strokeDasharray="1,2" />
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

          {/* Main Engagement Pulse Line */}
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

          {/* Trailing Engagement Node */}
          <motion.g animate={{ y: latestY }} transition={{ duration: 0.6, ease: "linear" }}>
              <circle cx="100" cy="0" r="3" fill={color} opacity="0.2" style={{ filter: 'url(#neonPulse)' }} />
              <motion.circle 
                  cx="100" cy="0" r="1.5" 
                  fill="white"
                  animate={{ scale: [1, 1.8, 1], opacity: [0.8, 1, 0.8] }}
                  transition={{ repeat: Infinity, duration: 2 }}
              />
          </motion.g>

          {/* Horizontal Line Labels */}
          <g className="text-[2px] font-black" fill="white" fillOpacity="0.2">
             <text x="1" y="22">INTENSITY_HIGH</text>
             <text x="1" y="52">INTENSITY_MED</text>
             <text x="1" y="82">INTENSITY_LOW</text>
          </g>
        </svg>

        {/* X-Axis Label */}
        <div className="absolute -bottom-6 left-1/2 -translate-x-1/2 whitespace-nowrap">
           <span className="text-[8px] font-black text-white/20 uppercase tracking-[0.4em]">TELEMETRY_TIMELINE</span>
        </div>
      </div>

      {/* Decorative scanline */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden mix-blend-overlay opacity-10">
         <motion.div 
            className="w-full h-1/2 bg-gradient-to-b from-white to-transparent"
            animate={{ top: ['-100%', '200%'] }}
            transition={{ duration: 4, repeat: Infinity, ease: 'linear' }}
         />
      </div>
    </div>
  );
}
