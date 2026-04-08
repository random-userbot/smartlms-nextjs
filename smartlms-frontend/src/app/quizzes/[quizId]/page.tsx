'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { quizzesAPI } from '@/lib/api';
import { 
  Clock, 
  AlertTriangle, 
  CheckCircle, 
  Send, 
  ShieldAlert,
  Bot,
  Sparkles,
  Loader2,
  Video
} from 'lucide-react';
import Sidebar from '@/components/Sidebar';
import AutoEngagementCapture from '@/components/AutoEngagementCapture';
import PremiumTimer from '@/components/quiz/PremiumTimer';
import { useActivity } from '@/context/ActivityTracker';

export default function QuizPage() {
  const params = useParams();
  const router = useRouter();
  const quizId = params.quizId as string;

  const [quiz, setQuiz] = useState<any>(null);
  const [answers, setAnswers] = useState<any>({});
  const [violations, setViolations] = useState<any[]>([]);
  const [timeLeft, setTimeLeft] = useState<number | null>(null);
  const [submitted, setSubmitted] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [camEnabled, setCamEnabled] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [sessionActive, setSessionActive] = useState(false);
  
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  // Persistence Key
  const STORAGE_KEY = `quiz_timer_${quizId}`;

  useEffect(() => {
    if (quizId) {
      quizzesAPI.get(quizId).then(res => {
        setQuiz(res.data);
        if (res.data.webcam_required) {
          setCamEnabled(true);
        }
        
        // Timer Logic: Check persistence
        const storedEnd = localStorage.getItem(STORAGE_KEY);
        const limit = res.data.time_limit || 600;
        
        if (storedEnd) {
          const remaining = Math.floor((parseInt(storedEnd) - Date.now()) / 1000);
          if (remaining <= 0) {
            setTimeLeft(0);
            handleSubmit();
          } else {
            setTimeLeft(remaining);
          }
        } else {
          const endTime = Date.now() + (limit * 1000);
          localStorage.setItem(STORAGE_KEY, endTime.toString());
          setTimeLeft(limit);
        }
      }).finally(() => setLoading(false));
    }
  }, [quizId]);

  const handleSubmit = useCallback(async () => {
    if (submitted) return;
    setSubmitted(true);
    localStorage.removeItem(STORAGE_KEY);
    
    try {
      const res = await quizzesAPI.submitAttempt({
        quiz_id: quizId,
        answers,
        violations
      });
      setResult(res.data);
    } catch (err) {
      console.error(err);
      setSubmitted(false);
    }
  }, [quizId, answers, violations, submitted]);

  useEffect(() => {
    if (submitted || !quiz || timeLeft === null) return;
    
    timerRef.current = setInterval(() => {
      setTimeLeft(prev => {
        if (prev === null) return null;
        
        // 5-Minute Audio Alert (Neural Sync Signal)
        if (prev === 300) {
          playNeuralBeep();
        }

        if (prev <= 1) {
          clearInterval(timerRef.current!);
          handleSubmit();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [quiz, submitted, timeLeft, handleSubmit]);

  const playNeuralBeep = () => {
    try {
      const audioCtx = new (window.AudioContext || (window as any).webkitAudioContext)();
      const oscillator = audioCtx.createOscillator();
      const gainNode = audioCtx.createGain();

      oscillator.type = 'sine';
      oscillator.frequency.setValueAtTime(880, audioCtx.currentTime); // A5 note
      gainNode.gain.setValueAtTime(0.1, audioCtx.currentTime);
      gainNode.gain.exponentialRampToValueAtTime(0.0001, audioCtx.currentTime + 0.5);

      oscillator.connect(gainNode);
      gainNode.connect(audioCtx.destination);

      oscillator.start();
      oscillator.stop(audioCtx.currentTime + 0.5);
    } catch (e) {
      console.warn("Audio Context blocked by browser policy. Interaction required.");
    }
  };

  const addViolation = useCallback((v: any) => {
    setViolations(prev => {
      // Throttle same-type violations (e.g. face not found) to every 5 seconds
      const last = prev.filter(p => p.type === v.type).reverse()[0];
      if (last && (v.timestamp - last.timestamp) < 5000) return prev;
      return [...prev, v];
    });
  }, []);

  const enterFullscreen = async () => {
    try {
      if (!document.fullscreenElement) {
        await document.documentElement.requestFullscreen();
        setIsFullscreen(true);
        setSessionActive(true);
      } else {
        setSessionActive(true);
      }
    } catch (err) {
      console.error('Fullscreen request denied', err);
      setSessionActive(true); // Allow session anyway but flag it
    }
  };

  // Proctoring: Event Restrictions
  useEffect(() => {
    if (!sessionActive || submitted) return;

    const preventDefault = (e: Event) => {
      e.preventDefault();
      addViolation({ type: 'integrity_block', details: `Unauthorized execution of ${e.type}`, timestamp: Date.now() });
    };

    const handleVisibility = () => {
      if (document.hidden) {
        addViolation({ type: 'tab_switch', timestamp: Date.now() });
      }
    };

    const handleBlur = () => {
      addViolation({ type: 'focus_loss', timestamp: Date.now(), details: 'Window focus lost' });
    };

    const handleFullscreenChange = () => {
      if (!document.fullscreenElement && sessionActive && !submitted) {
        addViolation({ type: 'fullscreen_exit', timestamp: Date.now(), details: 'Manual escape from secure view' });
        setIsFullscreen(false);
      }
    };

    // Restrictions
    document.addEventListener('copy', preventDefault);
    document.addEventListener('paste', preventDefault);
    document.addEventListener('cut', preventDefault);
    document.addEventListener('contextmenu', preventDefault);
    document.addEventListener('visibilitychange', handleVisibility);
    window.addEventListener('blur', handleBlur);
    document.addEventListener('fullscreenchange', handleFullscreenChange);

    return () => {
      document.removeEventListener('copy', preventDefault);
      document.removeEventListener('paste', preventDefault);
      document.removeEventListener('cut', preventDefault);
      document.removeEventListener('contextmenu', preventDefault);
      document.removeEventListener('visibilitychange', handleVisibility);
      window.removeEventListener('blur', handleBlur);
      document.removeEventListener('fullscreenchange', handleFullscreenChange);
    };
  }, [sessionActive, submitted, addViolation]);

  if (loading || timeLeft === null) return null;

  if (result) {
    return (
      <div className="flex h-screen bg-background items-center justify-center p-12">
        <div className="max-w-2xl w-full glass-card p-16 text-center space-y-10 crimson-glow-lg animate-fade-in">
          <div className="w-24 h-24 rounded-full bg-success/20 text-success border border-success/30 flex items-center justify-center mx-auto shadow-lg">
            <CheckCircle size={48} />
          </div>
          <div>
            <h2 className="text-5xl font-black text-white tracking-tighter">Assessment Captured.</h2>
            <p className="text-text-muted font-bold mt-4">Your cognitive synchronization score has been recorded.</p>
          </div>
          <div className="flex justify-center gap-12 border-y border-white/5 py-10">
            <div className="text-center">
              <div className="text-5xl font-black text-primary">{result.percentage?.toFixed(0)}%</div>
              <div className="text-[10px] font-black text-text-muted uppercase tracking-widest mt-2">Proficiency</div>
            </div>
            <div className="text-center border-l border-white/5 pl-12">
              <div className="text-5xl font-black text-white">{result.score}/{result.max_score}</div>
              <div className="text-[10px] font-black text-text-muted uppercase tracking-widest mt-2">Points Earned</div>
            </div>
          </div>
          <button 
            onClick={() => router.push('/dashboard')}
            className="btn-primary w-full py-5 text-sm font-black uppercase tracking-widest"
          >
            Return to Command Center
          </button>
        </div>
      </div>
    );
  }

  if (!sessionActive) {
    return (
      <div className="flex min-h-screen bg-background items-center justify-center p-12 overflow-hidden">
        <div className="max-w-xl w-full glass-card p-12 text-center space-y-8 animate-in zoom-in-95 duration-500">
           <div className="w-20 h-20 rounded-[2rem] bg-primary/20 text-primary border border-primary/40 flex items-center justify-center mx-auto crimson-glow">
              <ShieldAlert size={40} />
           </div>
           <div className="space-y-4">
              <h2 className="text-4xl font-black text-white tracking-tighter">Secure Link Required</h2>
              <p className="text-sm font-medium text-text-muted leading-relaxed italic">
                This verification module is protected by Active Proctoring. To proceed, please initiate a secure full-screen session. 
                Unauthorized window switching or clipboard usage will be logged as an integrity violation.
              </p>
           </div>
           <button 
             onClick={enterFullscreen}
             className="w-full py-6 bg-primary text-white rounded-3xl font-black text-xs uppercase tracking-widest hover:scale-[1.02] active:scale-95 transition-all shadow-2xl crimson-glow"
           >
              Initiate Secure Session
           </button>
           <button onClick={() => router.back()} className="text-[10px] font-black text-text-muted uppercase tracking-widest hover:text-white">
              Abort Assessment
           </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <main className="flex-1 ml-64 p-12 space-y-12 animate-fade-in relative">
        
        {/* Exam Header */}
        <header className="sticky top-0 z-50 bg-background/80 backdrop-blur-xl border-b border-border -mx-12 px-12 py-8 flex justify-between items-center">
          <div>
            <div className="text-[10px] font-black text-primary uppercase tracking-[0.4em] mb-1">Knowledge Verification</div>
            <h1 className="text-3xl font-black text-white tracking-tighter">{quiz?.title}</h1>
          </div>
          <div className="flex items-center gap-6">
            {/* Live Timer */}
            <div className={`flex items-center gap-3 px-6 py-3 rounded-2xl border transition-all duration-500 ${
              timeLeft < 300 ? 'bg-primary/20 border-primary animate-pulse' : 'bg-surface-alt border-border'
            }`}>
              <Clock size={16} className={timeLeft < 300 ? 'text-primary' : 'text-text-muted'} />
              <span className={`text-xl font-black tabular-nums tracking-tighter ${timeLeft < 300 ? 'text-white' : 'text-foreground'}`}>
                {Math.floor(timeLeft / 60)}:{(timeLeft % 60).toString().padStart(2, '0')}
              </span>
            </div>

            {quiz?.webcam_required ? (
              <div className="flex items-center gap-2 px-6 py-3 bg-primary/10 border border-primary/20 rounded-2xl text-[10px] font-black uppercase tracking-[0.2em] text-primary">
                <ShieldAlert size={14} /> Proctoring Enforced
              </div>
            ) : (
              <button 
                onClick={() => setCamEnabled(!camEnabled)}
                className={`flex items-center gap-2 px-5 py-3 rounded-2xl border text-[10px] font-black uppercase tracking-widest transition-all
                  ${camEnabled ? 'bg-primary text-white border-primary shadow-xl shadow-primary/30' : 'bg-surface border-border text-text-muted hover:text-white'}`}
              >
                <Video size={14} /> {camEnabled ? 'Neural Eye Active' : 'Enable Neural Eye'}
              </button>
            )}
          </div>
        </header>

        <div className="grid grid-cols-12 gap-12">
          
          {/* Questions (Bento 8) */}
          <div className="col-span-12 lg:col-span-8 space-y-10">
            {quiz?.questions.map((q: any, i: number) => (
              <div key={i} className="glass-card p-10 space-y-8 group hover:border-primary/20 transition-all">
                <div className="flex items-center gap-4">
                  <span className="w-10 h-10 rounded-xl bg-surface-alt border border-border flex items-center justify-center text-xs font-black text-primary">
                    {i + 1}
                  </span>
                  <div className="text-[10px] font-black text-text-muted uppercase tracking-[0.2em]">{q.type.replace('_', ' ')}</div>
                </div>
                <h3 className="text-2xl font-bold text-white leading-relaxed">{q.question}</h3>
                
                <div className="grid grid-cols-1 gap-4">
                  {q.type === 'short_answer' || q.type === 'fill_blank' ? (
                    <textarea 
                      className="w-full bg-surface border border-border rounded-2xl p-6 font-bold text-white outline-none focus:border-primary/40 h-32 resize-none transition-all"
                      placeholder="Articulate your cognitive resonance..."
                      value={answers[i] || ''}
                      onChange={(e) => setAnswers({ ...answers, [i]: e.target.value })}
                    />
                  ) : (
                    (q.options && q.options.length > 0 ? q.options : ['True', 'False']).map((opt: string, j: number) => {
                      const isSelected = answers[i] === opt;
                      return (
                        <button
                          key={j}
                          onClick={() => setAnswers({ ...answers, [i]: opt })}
                          className={`text-left p-6 rounded-2xl border transition-all text-sm font-medium flex items-center gap-4 group/opt ${
                            isSelected 
                            ? 'border-primary bg-primary/10 text-white crimson-glow' 
                            : 'border-border bg-surface text-text-muted hover:border-primary/20 hover:text-white'
                          }`}
                        >
                          <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center ${isSelected ? 'border-primary bg-primary' : 'border-border group-hover/opt:border-primary/40'}`}>
                            {isSelected && <div className="w-2 h-2 bg-white rounded-full"></div>}
                          </div>
                          {opt}
                        </button>
                      );
                    })
                  )}
                </div>
              </div>
            ))}

            <button 
              onClick={handleSubmit}
              disabled={submitted}
              className="w-full btn-primary py-6 text-lg font-black uppercase tracking-widest flex items-center justify-center gap-3"
            >
              {submitted ? <Loader2 className="animate-spin" /> : <><Send size={20} /> Finalize Assessment</>}
            </button>
          </div>

          {/* Sidebar Info (Bento 4) */}
          <div className="col-span-12 lg:col-span-4 space-y-8">
            
            {/* Proctoring Card */}
            <div className={`glass-card p-8 border-t-4 transition-all ${violations.length > 0 ? 'border-t-primary bg-primary/5' : 'border-t-success bg-success/5'}`}>
               <div className="flex items-center gap-3 mb-4">
                 <ShieldAlert size={20} className={violations.length > 0 ? 'text-primary' : 'text-success'} />
                 <h4 className="text-sm font-black text-white uppercase tracking-widest">Integrity Pulse</h4>
               </div>
               <p className="text-xs text-text-muted leading-relaxed font-medium">
                 {violations.length > 0 
                   ? `${violations.length} session violation(s) detected. Your integrity score is fluctuating.` 
                   : 'Handshake stable. No integrity violations detected in current session.'}
               </p>
               {violations.length > 0 && (
                 <div className="mt-4 space-y-2">
                   {Array.from(new Set(violations.map(v => v.type))).map(type => (
                     <div key={type} className="px-3 py-1 bg-primary/10 border border-primary/20 rounded-lg text-[8px] font-black uppercase text-primary inline-block mr-2">
                       {type.replace('_', ' ')}
                     </div>
                   ))}
                 </div>
               )}
            </div>

            {/* Aika Motivator */}
            <div className="glass-card p-10 bg-surface/50 border-border space-y-6 relative overflow-hidden">
               <Bot className="absolute -right-4 -top-4 text-primary/10" size={120} />
               <div className="flex items-center gap-3 relative z-10">
                 <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center text-white crimson-glow">
                   <Sparkles size={16} />
                 </div>
                 <h4 className="text-xs font-black text-white uppercase tracking-widest">Sensei Insight</h4>
               </div>
               <p className="text-sm italic text-white/80 leading-relaxed font-medium relative z-10">
                 "Analyze the core intent of question {Object.keys(answers).length + 1}. The pattern suggests a multi-dimensional response is required."
               </p>
            </div>

            {/* Progress Map */}
            <div className="glass-card p-8">
               <h4 className="text-xs font-black text-text-muted uppercase tracking-widest mb-6">Assessment Grid</h4>
               <div className="grid grid-cols-5 gap-3">
                 {quiz?.questions.map((_: any, i: number) => (
                   <div 
                    key={i} 
                    className={`aspect-square rounded-lg border flex items-center justify-center text-[10px] font-black transition-all ${
                      answers[i] ? 'bg-primary border-primary text-white shadow-lg' : 'bg-surface border-border text-text-muted'
                    }`}
                   >
                     {i + 1}
                   </div>
                 ))}
               </div>
            </div>

          </div>

        </div>

        {/* Proctoring Hub (PiP) */}
        {!submitted && (
           <AutoEngagementCapture 
             lectureId={quizId}
             playing={camEnabled}
             mode="proctoring"
             onViolation={addViolation}
           />
        )}

      </main>
    </div>
  );
}
