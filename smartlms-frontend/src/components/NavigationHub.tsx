'use client';

import React, { useState, useEffect } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { 
  ArrowLeft, 
  ArrowRight, 
  LayoutDashboard, 
  ChevronUp, 
  MessageCircle,
  Sparkles,
  Command
} from 'lucide-react';

export default function NavigationHub() {
  const router = useRouter();
  const pathname = usePathname();
  const [expanded, setExpanded] = useState(false);
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    // Show after initial mount for animation
    const timer = setTimeout(() => setIsVisible(true), 1000);
    return () => clearTimeout(timer);
  }, []);

  if (!isVisible) return null;

  return (
    <div className="fixed bottom-32 right-8 z-[90] flex flex-col items-end gap-3 pointer-events-none">
      
      {/* Floating Matrix */}
      <div className={`flex flex-col gap-2 transition-all duration-500 origin-bottom 
        ${expanded ? 'scale-100 opacity-100 translate-y-0' : 'scale-75 opacity-0 translate-y-12 pointer-events-none'}`}>
        
        <button 
          onClick={() => { router.push('/dashboard'); setExpanded(false); }}
          className="w-12 h-12 bg-surface backdrop-blur-xl border border-white/5 rounded-2xl flex items-center justify-center text-primary shadow-2xl hover:bg-primary hover:text-white transition-all pointer-events-auto group"
        >
          <LayoutDashboard size={20} />
          <span className="absolute right-full mr-3 px-3 py-1 bg-black/60 backdrop-blur-xl rounded-lg text-[10px] font-black text-white uppercase tracking-widest opacity-0 group-hover:opacity-100 transition-opacity">
            Terminal
          </span>
        </button>

        <div className="flex gap-2">
          <button 
            onClick={() => { router.back(); setExpanded(false); }}
            className="w-12 h-12 bg-surface/80 backdrop-blur-xl border border-white/5 rounded-2xl flex items-center justify-center text-text-muted hover:text-primary transition-all pointer-events-auto"
          >
            <ArrowLeft size={18} />
          </button>
          <button 
            onClick={() => { router.forward(); setExpanded(false); }}
            className="w-12 h-12 bg-surface/80 backdrop-blur-xl border border-white/5 rounded-2xl flex items-center justify-center text-text-muted hover:text-primary transition-all pointer-events-auto"
          >
            <ArrowRight size={18} />
          </button>
        </div>
      </div>

      {/* Toggle Button */}
      <button 
        onClick={() => setExpanded(!expanded)}
        className={`w-14 h-14 rounded-[2rem] flex items-center justify-center transition-all duration-500 shadow-2xl pointer-events-auto
          ${expanded ? 'bg-primary text-white crimson-glow rotate-180' : 'bg-surface border border-white/10 text-primary hover:border-primary/40'}`}
      >
        {expanded ? <ChevronUp size={24} /> : <Command size={24} className="animate-pulse" />}
      </button>

    </div>
  );
}
