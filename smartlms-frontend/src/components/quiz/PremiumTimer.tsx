'use client';

import React, { useEffect, useState } from 'react';
import { Clock, AlertCircle } from 'lucide-react';

interface PremiumTimerProps {
  seconds: number;
  totalSeconds: number;
}

export default function PremiumTimer({ seconds, totalSeconds }: PremiumTimerProps) {
  const [pulse, setPulse] = useState(false);
  
  const minutes = Math.floor(seconds / 60);
  const secs = seconds % 60;
  const percentage = (seconds / totalSeconds) * 100;

  // HSL Color calculation: 200 (Blue/Safe) to 0 (Red/Urgent)
  const hue = (percentage / 100) * 200;
  const isUrgent = seconds < 60;

  useEffect(() => {
    if (isUrgent) {
      const interval = setInterval(() => setPulse(p => !p), 500);
      return () => clearInterval(interval);
    }
  }, [isUrgent]);

  return (
    <div className="flex flex-col items-center gap-2">
      <div 
        className={`relative w-48 h-48 rounded-full flex items-center justify-center transition-all duration-700
          ${isUrgent && pulse ? 'scale-105' : 'scale-100'}`}
        style={{
          background: `conic-gradient(hsla(${hue}, 70%, 50%, 0.2) ${percentage}%, transparent 0)`,
          boxShadow: `0 0 40px hsla(${hue}, 70%, 50%, 0.1), inset 0 0 20px hsla(${hue}, 70%, 50%, 0.05)`
        }}
      >
        {/* SVG Progress Ring */}
        <svg className="absolute inset-0 w-full h-full -rotate-90">
          <circle
            cx="96"
            cy="96"
            r="88"
            fill="none"
            stroke="currentColor"
            strokeWidth="4"
            className="text-white/5"
          />
          <circle
            cx="96"
            cy="96"
            r="88"
            fill="none"
            stroke={`hsl(${hue}, 70%, 50%)`}
            strokeWidth="8"
            strokeDasharray="552.92"
            strokeDashoffset={552.92 - (552.92 * percentage) / 100}
            strokeLinecap="round"
            className="transition-all duration-1000 ease-linear drop-shadow-[0_0_8px_rgba(0,0,0,0.5)]"
          />
        </svg>

        <div className="flex flex-col items-center z-10">
          <div className="text-4xl font-black text-foreground tracking-tighter flex items-tabular-nums">
            {minutes < 10 ? `0${minutes}` : minutes}
            <span className={`animate-pulse ${isUrgent ? 'text-danger' : 'text-primary'}`}>:</span>
            {secs < 10 ? `0${secs}` : secs}
          </div>
          <div className={`text-[10px] font-black uppercase tracking-[0.2em] mt-1
            ${isUrgent ? 'text-danger animate-bounce' : 'text-text-muted'}`}>
            {isUrgent ? 'Temporal Criticality' : 'Sync Remaining'}
          </div>
        </div>

        {isUrgent && (
          <div className="absolute -top-2 left-1/2 -translate-x-1/2 bg-danger text-white p-2 rounded-full crimson-glow animate-pulse">
            <AlertCircle size={16} />
          </div>
        )}
      </div>
      
      <div className="flex items-center gap-2 px-4 py-2 bg-surface rounded-2xl border border-white/5 mt-4">
        <Clock size={14} className={isUrgent ? 'text-danger' : 'text-primary'} />
        <span className="text-[10px] font-black uppercase tracking-widest text-text-muted">
          Dynamic Temporal Analysis: <span className="text-foreground">ACTIVE</span>
        </span>
      </div>
    </div>
  );
}
