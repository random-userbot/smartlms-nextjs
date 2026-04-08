'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/context/AuthContext';
import { 
  Bot, 
  Mail, 
  Lock, 
  User,
  ArrowRight,
  Loader2,
  AlertCircle,
  GraduationCap,
  ShieldCheck,
  ChevronLeft,
  Eye,
  EyeOff
} from 'lucide-react';
import Link from 'next/link';

export default function RegisterPage() {
  const router = useRouter();
  const { register } = useAuth();
  
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState<'student' | 'teacher'>('student');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [showPassword, setShowPassword] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await register({ 
        full_name: name, 
        username: email, 
        email, 
        password, 
        role 
      });
      router.push('/dashboard');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Protocol failure. Connection rejected.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background/20 flex items-center justify-center p-6 relative overflow-hidden">
      {/* Back Button */}
      <Link 
        href="/" 
        className="absolute top-8 left-8 flex items-center gap-2 text-[10px] font-black text-text-muted uppercase tracking-[0.3em] hover:text-primary transition-colors z-50 group"
      >
        <div className="w-8 h-8 rounded-lg border border-border flex items-center justify-center group-hover:border-primary/50 transition-all">
          <ChevronLeft size={14} />
        </div>
        Back to Grid
      </Link>

      <div className="max-w-md w-full glass-card p-12 space-y-8 crimson-glow-lg animate-fade-in relative z-10">
        
        {/* Brand */}
        <div className="flex flex-col items-center text-center gap-4">
          <div className="w-16 h-16 rounded-2xl bg-primary flex items-center justify-center text-white crimson-glow shimmer">
            <Bot size={32} />
          </div>
          <div>
            <h1 className="text-3xl font-black text-foreground tracking-tighter">SmartLMS</h1>
            <p className="text-[10px] font-black text-primary uppercase tracking-[0.4em] mt-1">Cognitive Synchronization</p>
          </div>
        </div>

        {error && (
          <div className="flex items-center gap-3 p-4 bg-primary/10 border border-primary/20 rounded-2xl text-xs font-bold text-white leading-relaxed">
            <AlertCircle size={14} className="text-primary shrink-0" /> {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="space-y-2">
            <label className="text-[10px] font-black text-text-muted uppercase tracking-widest px-1">Domain Handle (Full Name)</label>
            <div className="relative group">
               <User className="absolute left-4 top-1/2 -translate-y-1/2 text-text-muted transition-colors group-focus-within:text-primary" size={18} />
               <input 
                type="text" 
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                placeholder="Revanth S."
                className="w-full bg-surface border border-border rounded-2xl pl-12 pr-6 py-4 text-sm font-medium text-white focus:outline-none focus:border-primary/40 transition-all"
               />
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-[10px] font-black text-text-muted uppercase tracking-widest px-1">Neural Address (Email)</label>
            <div className="relative group">
               <Mail className="absolute left-4 top-1/2 -translate-y-1/2 text-text-muted transition-colors group-focus-within:text-primary" size={18} />
               <input 
                type="email" 
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                placeholder="revan@smartlms.ai"
                className="w-full bg-surface border border-border rounded-2xl pl-12 pr-6 py-4 text-sm font-medium text-white focus:outline-none focus:border-primary/40 transition-all"
               />
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-[10px] font-black text-text-muted uppercase tracking-widest px-1">Neural Link Key (Password)</label>
            <div className="relative group">
               <Lock className="absolute left-4 top-1/2 -translate-y-1/2 text-text-muted transition-colors group-focus-within:text-primary" size={18} />
               <input 
                type={showPassword ? 'text' : 'password'} 
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                placeholder="••••••••"
                className="w-full bg-surface border border-border rounded-2xl pl-12 pr-14 py-4 text-sm font-medium text-white focus:outline-none focus:border-primary/40 transition-all"
               />
               <button 
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-4 top-1/2 -translate-y-1/2 text-text-muted hover:text-primary transition-colors"
               >
                {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
               </button>
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-[10px] font-black text-text-muted uppercase tracking-widest px-1">Neural Class (Role)</label>
            <div className="grid grid-cols-2 gap-4">
              <button 
                type="button" 
                onClick={() => setRole('student')}
                className={`flex items-center justify-center gap-2 p-3.5 rounded-2xl border transition-all text-[10px] font-black uppercase tracking-widest ${role === 'student' ? 'border-primary bg-primary/10 text-white' : 'border-border bg-surface text-text-muted'}`}
              >
                <GraduationCap size={16} /> Student
              </button>
              <button 
                type="button" 
                onClick={() => setRole('teacher')}
                className={`flex items-center justify-center gap-2 p-3.5 rounded-2xl border transition-all text-[10px] font-black uppercase tracking-widest ${role === 'teacher' ? 'border-primary bg-primary/10 text-white' : 'border-border bg-surface text-text-muted'}`}
              >
                <ShieldCheck size={16} /> Instructor
              </button>
            </div>
          </div>

          <button 
            type="submit" 
            disabled={loading}
            className="w-full btn-primary flex items-center justify-center gap-3 py-5 text-sm font-black uppercase tracking-widest group"
          >
            {loading ? <Loader2 className="animate-spin" size={20} /> : (
              <>
                Initiate Grid Protocol 
                <ArrowRight size={18} className="group-hover:translate-x-1 transition-transform" />
              </>
            )}
          </button>
        </form>

        <div className="text-center pt-8 border-t border-white/5">
          <p className="text-[10px] font-black text-text-muted uppercase tracking-widest">
            Already Linked? <Link href="/login" className="text-primary hover:text-white transition-colors ml-2">Authenticate &rarr;</Link>
          </p>
        </div>

      </div>
    </div>
  );
}
