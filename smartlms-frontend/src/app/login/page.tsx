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
import { GoogleLogin } from '@react-oauth/google';

export default function LoginPage() {
  const router = useRouter();
  const { login, googleLogin } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [showPassword, setShowPassword] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await login({ username: email, password });
      router.push('/dashboard');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Login failed. Verify credentials.');
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleSuccess = async (response: any) => {
    if (loading) return; // Prevent multiple clicks
    setLoading(true);
    setError(null);
    try {
      await googleLogin(response.credential, undefined, 'login');
      router.push('/dashboard');
    } catch (err: any) {
      if (err.response?.status === 404) {
        setError('Account not found. Please register to continue.');
        // Don't set loading false so button stays disabled
        setTimeout(() => router.push('/register'), 2000);
        return;
      } else {
        setError(err.response?.data?.detail || 'Google Authentication failed.');
        setLoading(false);
      }
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

      <div className="max-w-md w-full glass-card p-12 space-y-10 crimson-glow-lg animate-fade-in relative z-10">
        
        {/* Brand */}
        <div className="flex flex-col items-center text-center gap-4">
          <div className="w-16 h-16 rounded-2xl bg-primary flex items-center justify-center text-white crimson-glow shimmer">
            <Bot size={32} />
          </div>
          <div>
            <h1 className="text-3xl font-black text-foreground tracking-tighter">SmartLMS</h1>
            <p className="text-[10px] font-black text-primary uppercase tracking-[0.4em] mt-1">Learning Management</p>
          </div>
        </div>

        {error && (
          <div className="flex items-center gap-3 p-4 bg-primary/10 border border-primary/20 rounded-2xl text-xs font-bold text-foreground leading-relaxed">
            <AlertCircle size={14} className="text-primary shrink-0" /> {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="space-y-2">
            <label className="text-[10px] font-black text-text-muted uppercase tracking-widest px-1">Email</label>
            <div className="relative group">
               <Mail className="absolute left-4 top-1/2 -translate-y-1/2 text-text-muted transition-colors group-focus-within:text-primary" size={18} />
                <input 
                 type="email" 
                 value={email}
                 onChange={(e) => setEmail(e.target.value)}
                 required
                 placeholder="revan@smartlms.ai"
                 className="w-full bg-surface border border-border rounded-2xl pl-12 pr-6 py-4 text-sm font-bold text-foreground focus:outline-none focus:border-primary/40 transition-all"
                />
            </div>
          </div>

          <div className="space-y-2">
            <div className="flex justify-between items-center px-1">
              <label className="text-[10px] font-black text-text-muted uppercase tracking-widest">Password</label>
              <Link href="#" className="text-[10px] font-black text-primary uppercase tracking-widest hover:text-white transition-colors">Forgot?</Link>
            </div>
            <div className="relative group">
               <Lock className="absolute left-4 top-1/2 -translate-y-1/2 text-text-muted transition-colors group-focus-within:text-primary" size={18} />
                <input 
                 type={showPassword ? 'text' : 'password'} 
                 value={password}
                 onChange={(e) => setPassword(e.target.value)}
                 required
                 placeholder="••••••••"
                 className="w-full bg-surface border border-border rounded-2xl pl-12 pr-14 py-4 text-sm font-bold text-foreground focus:outline-none focus:border-primary/40 transition-all"
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

          <button 
            type="submit" 
            disabled={loading}
            className="w-full btn-primary flex items-center justify-center gap-3 py-5 text-sm font-black uppercase tracking-widest group"
          >
            {loading ? <Loader2 className="animate-spin" size={20} /> : (
              <>
                Login
                <ArrowRight size={18} className="group-hover:translate-x-1 transition-transform" />
              </>
            )}
          </button>
        </form>

        <div className="relative py-4">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-border/50"></div>
          </div>
          <div className="relative flex justify-center text-[8px] uppercase font-black tracking-[0.4em] text-text-muted">
            <span className="bg-[#0a0a0b] px-4">Or Login With</span>
          </div>
        </div>

        <div className="flex justify-center">
          <GoogleLogin
            onSuccess={handleGoogleSuccess}
            onError={() => setError('Google login failed.')}
            useOneTap
            theme="filled_black"
            shape="pill"
            width="100%"
          />
        </div>

        <div className="text-center pt-10 border-t border-white/5">
          <p className="text-[10px] font-black text-text-muted uppercase tracking-widest">
            New User? <Link href="/register" className="text-primary hover:text-white transition-colors ml-2">Register &rarr;</Link>
          </p>
        </div>

      </div>
    </div>
  );
}
