'use client';

import React from 'react';
import { 
  Bot, 
  Activity, 
  Zap, 
  Shield, 
  Cpu, 
  Users, 
  ArrowRight,
  Sparkles,
  Sun,
  Moon
} from 'lucide-react';
import Link from 'next/link';
import { useTheme } from '@/context/ThemeContext';
import { motion, AnimatePresence } from 'framer-motion';

export default function LandingPage() {
  const { theme, toggleTheme } = useTheme();

  return (
    <div className="min-h-screen bg-background text-foreground selection:bg-primary/30 transition-colors duration-500">
      
      {/* Navigation */}
      <nav className="fixed top-0 w-full z-50 bg-background/50 backdrop-blur-xl border-b border-white/5">
        <div className="max-w-7xl mx-auto px-8 h-20 flex items-center justify-between">
          <div className="flex items-center gap-3">
             <div className="w-10 h-10 rounded-xl bg-primary flex items-center justify-center text-white crimson-glow">
                <Bot size={22} />
             </div>
             <span className="text-xl font-black tracking-tighter uppercase">SmartLMS</span>
          </div>
          <div className="hidden md:flex items-center gap-10">
             <Link href="#features" className="text-[10px] font-black uppercase tracking-widest text-text-muted hover:text-white transition-colors">Intelligence Grid</Link>
             <Link href="#aika" className="text-[10px] font-black uppercase tracking-widest text-text-muted hover:text-white transition-colors">Aika Sensei</Link>
             <Link href="#analytics" className="text-[10px] font-black uppercase tracking-widest text-text-muted hover:text-white transition-colors">V5 Analytics</Link>
          </div>
          <div className="flex items-center gap-6">
             <button 
               onClick={toggleTheme}
               className="p-3 hover:bg-surface-alt rounded-2xl border border-border text-text-muted hover:text-primary transition-all active:scale-95"
             >
               {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
             </button>
             <Link href="/login" className="text-[10px] font-black uppercase tracking-widest text-text-muted hover:text-foreground transition-colors">Login</Link>
             <Link href="/register" className="btn-primary py-3 px-8 text-[10px] font-black uppercase tracking-widest">Register</Link>
          </div>
        </div>
      </nav>

      {/* Hero Section: Cognitive Resonance */}
      <section className="relative min-h-screen flex items-center justify-center pt-20 overflow-hidden">
        
        <div className="max-w-7xl mx-auto px-8 relative z-10 text-center space-y-12">
          
          <div className="inline-flex items-center gap-3 px-6 py-2 rounded-full bg-primary/10 border border-primary/20 text-[10px] font-black text-primary uppercase tracking-[0.4em] animate-fade-in">
             <Sparkles size={14} /> Cognitive Hub Is Now Live
          </div>

          <h1 className="text-8xl md:text-[10rem] font-display font-black tracking-tighter leading-[0.8] animate-slide-up">
            Master the <span className="text-primary shimmer">Grid.</span>
          </h1>

          <p className="text-xl md:text-2xl font-bold text-text-muted max-w-3xl mx-auto leading-relaxed animate-fade-in [animation-delay:0.5s]">
            Precision learning powered by <span className="text-foreground">Cognitive Resonance</span>. Synchronize your focus with real-time AI analytics and the Aika Sensei.
          </p>

          <div className="flex flex-col md:flex-row items-center justify-center gap-8 animate-fade-in [animation-delay:0.8s]">
             <Link href="/register" className="btn-primary py-6 px-16 text-xs font-black uppercase tracking-widest flex items-center gap-3 group">
                Sign Up Now <ArrowRight size={18} className="group-hover:translate-x-1 transition-transform" />
             </Link>
             <Link href="/login" className="border border-border bg-surface-alt backdrop-blur-md py-6 px-16 rounded-2xl text-xs font-black uppercase tracking-widest hover:border-primary/40 transition-all">
                Sign In
             </Link>
          </div>

          {/* Floating Stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-12 pt-20 border-t border-border/20 mt-20 animate-fade-in [animation-delay:1.2s]">
             <div className="text-center group">
                <div className="text-4xl font-black text-foreground group-hover:text-primary transition-colors">99.8%</div>
                <div className="text-[8px] font-black text-text-muted uppercase tracking-[0.3em] mt-2 group-hover:text-primary transition-colors">Precision Hub</div>
             </div>
             <div className="text-center group">
                <div className="text-4xl font-black text-foreground group-hover:text-primary transition-colors">12.5k</div>
                <div className="text-[8px] font-black text-text-muted uppercase tracking-[0.3em] mt-2 group-hover:text-primary transition-colors">Active Nodes</div>
             </div>
             <div className="text-center group">
                <div className="text-4xl font-black text-foreground group-hover:text-primary transition-colors">Aika</div>
                <div className="text-[8px] font-black text-text-muted uppercase tracking-[0.3em] mt-2 group-hover:text-primary transition-colors">Sensei Presence</div>
             </div>
             <div className="text-center group">
                <div className="text-4xl font-black text-foreground group-hover:text-primary transition-colors">v5.0</div>
                <div className="text-[8px] font-black text-text-muted uppercase tracking-[0.3em] mt-2 group-hover:text-primary transition-colors">Analytics Protocol</div>
             </div>
          </div>
        </div>

      </section>

      {/* Feature Section: The Grid */}
      <section id="features" className="py-32 px-8 max-w-7xl mx-auto space-y-24">
         <div className="text-center space-y-6">
            <h2 className="text-5xl font-display font-black tracking-tighter">The Intelligence Grid.</h2>
            <p className="text-lg text-text-muted max-w-2xl mx-auto font-medium">A multi-layered ecosystem designed for elite knowledge acquisition and teacher-student synchronization.</p>
         </div>

         <div className="grid grid-cols-1 md:grid-cols-3 gap-12">
            {[
              { icon: <Activity className="text-primary" size={32} />, title: 'Cognitive Pulse', text: 'Real-time focus monitoring via webcam tracking and ICAP engagement classification.' },
              { icon: <Zap className="text-primary" size={32} />, title: 'Latency-Free Sync', text: 'Proprietary streaming protocols ensure your AI Sensei responds instantly to your learning needs.' },
              { icon: <Shield className="text-primary" size={32} />, title: 'Integrity Protocol', text: 'Advanced proctoring ensures assessment validity without compromising user experience.' }
            ].map((f, i) => (
              <div key={i} className="glass-card p-12 space-y-6 hover:border-primary/30 transition-all group">
                 <div className="crimson-glow-lg w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center border border-primary/20 group-hover:scale-110 transition-transform">
                   {f.icon}
                 </div>
                  <h3 className="text-2xl font-black text-foreground">{f.title}</h3>
                  <p className="text-sm text-text-muted leading-relaxed font-bold">{f.text}</p>
              </div>
            ))}
         </div>
      </section>

      {/* Footer */}
      <footer className="py-20 border-t border-border">
        <div className="max-w-7xl mx-auto px-8 flex flex-col md:flex-row justify-between items-center gap-12">
           <div className="flex items-center gap-3 opacity-80 group">
             <div className="w-8 h-8 rounded-lg bg-surface-alt border border-border flex items-center justify-center text-primary group-hover:scale-110 transition-transform">
                <Bot size={18} />
             </div>
             <span className="text-lg font-black tracking-tighter uppercase text-foreground">SmartLMS</span>
           </div>
           <div className="text-center md:text-right">
              <p className="text-[10px] font-black text-text-muted uppercase tracking-widest leading-relaxed">
                © 2026 SmartLMS Intelligence Systems.<br />
                Cognitive Resonance Protocol v5.24.1
              </p>
           </div>
        </div>
      </footer>

    </div>
  );
}
