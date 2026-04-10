'use client';

import React, { useState, useEffect, useRef } from 'react';
import { useParams, useRouter } from 'next/navigation';
import YouTube, { YouTubeProps } from 'react-youtube';
import { lecturesAPI, engagementAPI, tutorAPI, quizzesAPI } from '@/lib/api';
import Sidebar from '@/components/Sidebar';
import { 
  Play, 
  Pause, 
  Settings, 
  Maximize2, 
  Minimize2, 
  Volume2, 
  VolumeX, 
  Activity, 
  Bot, 
  Sparkles, 
  ChevronLeft, 
  CheckCircle2, 
  ArrowRight, 
  Brain, 
  Zap, 
  Info, 
  Target, 
  Video, 
  FolderOpen, 
  MessageCircle, 
  Volume2 as VolumeIcon, 
  Plus as PlusIcon, 
  FilePlus, 
  Mic, 
  MicOff, 
  Trash2,
  Send
} from 'lucide-react';
import EngagementWaveform from '@/components/EngagementWaveform';
import AutoEngagementCapture from '@/components/AutoEngagementCapture';
import QuizPhase from '@/components/lecture/QuizPhase';
import FeedbackPhase from '@/components/lecture/FeedbackPhase';
import SessionSummary from '@/components/lecture/SessionSummary';
import MaterialsTab from '@/components/lecture/MaterialsTab';
import NavigationHeader from '@/components/NavigationHeader';
import EngagementHeatmap from '@/components/EngagementHeatmap';
import { useActivity } from '@/context/ActivityTracker';
import { useAuth } from '@/context/AuthContext';

type LecturePhase = 'lecture' | 'quiz' | 'feedback' | 'summary';

export default function LecturePage() {
  const params = useParams();
  const router = useRouter();
  const lectureId = params.lectureId as string;
  const { trackEvent } = useActivity();
  const { user } = useAuth();
  
  const [lecture, setLecture] = useState<any>(null);
  const [phase, setPhase] = useState<LecturePhase>('lecture');
  const [playing, setPlaying] = useState(false);
  const [engagementScore, setEngagementScore] = useState<any>(null);
  const [engagementHistory, setEngagementHistory] = useState<any[]>([]);
  const [fullHistory, setFullHistory] = useState<any[]>([]);
  const [camEnabled, setCamEnabled] = useState(true);
  const [loading, setLoading] = useState(true);
  const [sessionResults, setSessionResults] = useState<any>(null);
  const fullWaveformRef = useRef<any[]>([]);
  const sessionId = useRef(Math.random().toString(36).substring(7));
  const [messages, setMessages] = useState<any[]>([
    { role: 'assistant', content: "I'm monitoring your cognitive resonance. How can I assist with your current synchronization?" }
  ]);
  const [chatInput, setChatInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [activeTab, setActiveTab] = useState<'chat' | 'materials'>('chat');
  const [tutorMode, setTutorMode] = useState<string>('general');
  const [showAlert, setShowAlert] = useState(false);
  const [attachments, setAttachments] = useState<any[]>([]);

  const [liveWatchers, setLiveWatchers] = useState(0);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [volume, setVolume] = useState(0.7);
  const [isListening, setIsListening] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  
  const playerRef = useRef<HTMLDivElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const recognitionRef = useRef<any>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const handleFsChange = () => setIsFullscreen(!!document.fullscreenElement);
    document.addEventListener('fullscreenchange', handleFsChange);
    
    if (typeof window !== 'undefined' && ('SpeechRecognition' in window || 'webkitSpeechRecognition' in window)) {
      const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
      recognitionRef.current = new SpeechRecognition();
      recognitionRef.current.continuous = false;
      recognitionRef.current.onresult = (event: any) => {
        const transcript = event.results[0][0].transcript;
        setChatInput(prev => prev + (prev ? ' ' : '') + transcript);
        setIsListening(false);
      };
      recognitionRef.current.onerror = () => setIsListening(false);
      recognitionRef.current.onend = () => setIsListening(false);
    }

    return () => {
      document.removeEventListener('fullscreenchange', handleFsChange);
      if (recognitionRef.current) recognitionRef.current.stop();
    };
  }, []);

  useEffect(() => {
    if (lectureId) {
      trackEvent('lecture_started', { lecture_id: lectureId });
      lecturesAPI.get(lectureId).then(res => {
        setLecture(res.data);
      }).finally(() => setLoading(false));

      const poll = setInterval(() => {
        engagementAPI.getLiveWatchers(lectureId).then(res => {
          setLiveWatchers(res.data.count || 0);
        }).catch(() => {});
      }, 5000);

      // Fetch initial history if available
      engagementAPI.getHistory(lectureId).then(res => {
        const historyData = Array.isArray(res.data) ? res.data : [];
        const history = historyData.map((h: any) => ({ engagement: h.overall_score }));
        setEngagementHistory(history.slice(-20)); // Keep last 20 for UI
      }).catch(() => {});

      return () => clearInterval(poll);
    }
  }, [lectureId]);

  // Session-End Persistence Hook
  const handleFinishLesson = async () => {
    setLoading(true);
    trackEvent('lecture_finished', { lecture_id: lectureId });
    
    // 1. Mark session as permanent and finalize datasets
    try {
      await engagementAPI.finalizeSession({
        session_id: sessionId.current,
        lecture_id: lectureId,
        waveform: fullWaveformRef.current
      });
    } catch (err) {
      console.error("Failed to finalize session:", err);
    }

    // 2. Determine next phase (Quiz or Feedback)
    try {
      // Use quizzesAPI instead of lecturesAPI for quiz logic
      const quizRes = await quizzesAPI.getByLecture(lectureId);
      const quizzes = quizRes.data;

      if (quizzes && quizzes.length > 0) {
        // Check if already attempted
        const attemptsRes = await quizzesAPI.getAttempts(quizzes[0].id);
        if (attemptsRes.data && attemptsRes.data.length > 0) {
          setPhase('feedback');
        } else {
          setPhase('quiz');
        }
      } else {
        setPhase('feedback');
      }
    } catch (err) {
      setPhase('feedback');
    } finally {
      setLoading(false);
    }
  };

  const toggleFullscreen = () => {
    if (!document.fullscreenElement) {
      playerRef.current?.requestFullscreen().catch(err => {
        console.error(`Error: ${err.message}`);
      });
    } else {
      document.exitFullscreen();
    }
  };

  const speakMessage = (text: string) => {
    if (typeof window === 'undefined') return;
    window.speechSynthesis.cancel();
    if (isSpeaking) { setIsSpeaking(false); return; }

    const utterance = new SpeechSynthesisUtterance(text);
    const voices = window.speechSynthesis.getVoices();
    const maleVoice = voices.find(v => 
      (v.name.toLowerCase().includes('google uk english male') || 
       v.name.toLowerCase().includes('microsoft david') || 
       v.name.toLowerCase().includes('guy') || 
       v.name.toLowerCase().includes('david')) && 
      v.lang.startsWith('en')
    ) || voices.find(v => v.lang.startsWith('en'));

    if (maleVoice) utterance.voice = maleVoice;
    utterance.pitch = 0.9;
    utterance.rate = 1.0;
    utterance.onstart = () => setIsSpeaking(true);
    utterance.onend = () => setIsSpeaking(false);
    window.speechSynthesis.speak(utterance);
  };

  const handleVolumeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const v = parseFloat(e.target.value);
    setVolume(v);
    if (videoRef.current) {
      videoRef.current.volume = v;
      videoRef.current.muted = v === 0;
    }
  };

  useEffect(() => {
    if (videoRef.current) {
      if (playing) videoRef.current.play().catch(() => {});
      else videoRef.current.pause();
    }
  }, [playing]);

  const handleScoreUpdate = (score: any) => {
    setEngagementScore(score);
    
    // Add to UI history (sliding window)
    setEngagementHistory(prev => {
      const newHistory = [...prev, { engagement: score.overall_score }];
      return newHistory.slice(-20);
    });

    // 3. Persist to session-long forensic ledger (State for Heatmap)
    const newPoint = {
      timestamp: Date.now(),
      engagement: score.overall_score,
      confusion: score.confusion,
      boredom: score.boredom,
      frustration: score.frustration
    };
    
    setFullHistory(prev => [...prev.slice(-300), newPoint]); // Keep last 300 pts (~50 mins of watch time)
    fullWaveformRef.current.push(newPoint);
  };

  const handleChat = async () => {
    if (!chatInput.trim() && attachments.length === 0) return;
    const userMsg = { role: 'user', content: chatInput, id: Date.now().toString() };
    const history = [...messages, userMsg];
    setMessages(history);
    setChatInput('');
    setIsTyping(true);

    try {
      const res = await tutorAPI.chat({
        messages: history.map(m => ({ role: m.role, content: m.content })),
        lecture_id: lectureId,
        mode: tutorMode,
        attachments: attachments.length > 0 ? attachments : undefined
      });
      setMessages(prev => [...prev, { role: 'assistant', content: res, id: (Date.now() + 1).toString() }]);
      setAttachments([]);
      trackEvent('ai_tutor_interaction', { lecture_id: lectureId, mode: tutorMode });
    } catch (err) {
      console.error(err);
      setMessages(prev => [...prev, { role: 'assistant', content: "Neural sync failure. Check your connection." }]);
    } finally {
      setIsTyping(false);
    }
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    Array.from(files).forEach(file => {
      const reader = new FileReader();
      reader.onload = (event) => {
        setAttachments(prev => [...prev, { name: file.name, type: file.type, data: event.target?.result }]);
      };
      reader.readAsDataURL(file);
    });
  };

  const deleteMessage = async (id: string) => {
    try { await tutorAPI.deleteMessage(id); } catch(e) {}
    setMessages(prev => prev.filter(m => m.id !== id));
  };

  if (loading) return null;

  const extractYoutubeId = (url: string) => {
    if (!url) return null;
    const regExp = /^.*(youtu.be\/|v\/|u\/\w\/|embed\/|watch\?v=|\&v=)([^#\&\?]*).*/;
    const match = url.match(regExp);
    return (match && match[2].length === 11) ? match[2] : null;
  };

  return (
    <div className="flex h-screen bg-background overflow-hidden relative">
      <Sidebar />
      
      <main className="flex-1 ml-64 flex flex-col min-w-0 relative">
        
        <div className="flex-1 flex overflow-hidden">
          {/* Immersive Video Section */}
          <div className="flex-1 flex flex-col overflow-y-auto p-8 lg:p-12 space-y-12 no-scrollbar">
            
            <header className="flex items-center justify-between">
              <div className="flex flex-col">
                <div className={`text-[10px] font-black uppercase tracking-[0.3em] mb-2 flex items-center gap-2 ${phase === 'lecture' ? 'text-primary' : 'text-success'}`}>
                  <Activity size={12} /> {phase === 'lecture' ? 'Class is Active' : 'Status: ' + phase}
                </div>
                <div className="flex items-center gap-4">
                  <button 
                    onClick={() => router.back()}
                    className="w-10 h-10 rounded-xl bg-surface border border-border flex items-center justify-center text-text-muted hover:text-primary transition-all lg:hidden"
                  >
                    <ChevronLeft size={20} />
                  </button>
                  <h1 className="text-4xl lg:text-5xl font-black text-foreground tracking-tighter leading-none">{lecture?.title}</h1>
                </div>
              </div>

              <div className="flex items-center gap-6">
                 <div className="flex items-center gap-4 bg-surface p-3 rounded-2xl border border-white/5 shadow-xl">
                    {['lecture', 'quiz', 'feedback', 'summary'].map((p, i) => (
                      <div key={p} className="flex items-center gap-4">
                         <div className={`w-8 h-8 rounded-lg flex items-center justify-center transition-all ${phase === p ? 'bg-primary text-white crimson-glow' : 'bg-white/5 text-text-muted'}`}>
                           {i + 1}
                         </div>
                         {i < 3 && <div className="w-8 h-[2px] bg-white/10 rounded-full" />}
                      </div>
                    ))}
                 </div>
                 <button 
                  onClick={handleFinishLesson}
                  className="px-8 py-3 bg-success hover:bg-success/80 text-white text-[10px] font-black uppercase tracking-[0.2em] rounded-2xl transition-all shadow-lg crimson-glow flex items-center gap-2"
                 >
                   <CheckCircle2 size={16} /> Finish Lesson
                 </button>
               </div>
            </header>

            <div className="flex-1">
              {phase === 'lecture' && (
                <div className="grid grid-cols-12 gap-8 h-full animate-fade-in">
                  <div className="col-span-12 lg:col-span-8 flex flex-col space-y-8 h-full min-h-0">
                    <div ref={playerRef} className={`aspect-video bg-surface relative overflow-hidden group transition-all shadow-2xl ${isFullscreen ? 'rounded-0' : 'rounded-[2.5rem] border border-border'}`}>
                       {!playing ? (
                         <div className="absolute inset-0 flex items-center justify-center z-50 bg-black/40 backdrop-blur-sm">
                           <button onClick={() => setPlaying(true)} className="group relative">
                             <div className="absolute -inset-8 bg-primary/20 blur-3xl rounded-full animate-pulse group-hover:bg-primary/40" />
                             <Play className="text-primary relative crimson-glow group-hover:scale-125 transition-transform" size={80} fill="currentColor" />
                           </button>
                         </div>
                       ) : lecture?.youtube_url ? (
                          <YouTube
                            videoId={extractYoutubeId(lecture.youtube_url) || ''}
                            className="w-full h-full"
                            iframeClassName="w-full h-full border-none"
                            opts={{
                              playerVars: {
                                autoplay: 1,
                                controls: 1,
                                modestbranding: 1,
                                rel: 0,
                              },
                            }}
                            onPlay={() => setPlaying(true)}
                            onPause={() => setPlaying(false)}
                            onEnd={() => setPlaying(false)}
                            onStateChange={(event) => {
                              // 1 is Playing, 2 is Paused
                              if (event.data === 1) setPlaying(true);
                              if (event.data === 2) setPlaying(false);
                            }}
                          />
                       ) : (
                         <video ref={videoRef} src={lecture?.video_url} autoPlay className="w-full h-full object-contain bg-black" />
                       )}
                       
                       <div className="absolute top-8 left-8 flex items-center gap-4 z-20 pointer-events-none">
                           <div className="px-4 py-2 bg-black/60 backdrop-blur-xl rounded-2xl border border-white/10 flex items-center gap-3">
                              <div className="w-2 h-2 rounded-full bg-primary animate-ping" />
                              <span className="text-[10px] font-black text-white uppercase tracking-widest">Watching Video</span>
                           </div>
                           <div className="px-4 py-2 bg-black/60 backdrop-blur-xl rounded-2xl border border-white/10 flex items-center gap-3">
                              <Brain size={14} className="text-primary" />
                              <span className="text-[10px] font-black text-white uppercase tracking-widest">Mode: {engagementScore?.icap_classification || 'Loading...'}</span>
                           </div>
                       </div>

                       <div className={`absolute bottom-10 left-10 right-10 flex items-center justify-between transition-all z-30 ${isFullscreen ? 'opacity-100 translate-y-0' : 'opacity-0 group-hover:opacity-100 translate-y-4 group-hover:translate-y-0'}`}>
                         <div className="flex items-center gap-4">
                           <button onClick={() => setPlaying(!playing)} className="w-12 h-12 rounded-2xl bg-black/60 text-white flex items-center justify-center border border-white/10">
                             {playing ? <Pause size={24} /> : <Play size={24} />}
                           </button>
                           <div className="p-3 bg-black/60 backdrop-blur-2xl rounded-2xl border border-white/10 flex items-center gap-4">
                              <Volume2 className="text-white/40" size={18} />
                              <input type="range" min="0" max="1" step="0.01" value={volume} onChange={handleVolumeChange} className="w-24 accent-primary" />
                           </div>
                         </div>
                         <div className="flex gap-4">
                           <button onClick={toggleFullscreen} className="w-12 h-12 rounded-2xl bg-black/60 text-white flex items-center justify-center border border-white/10">
                              {isFullscreen ? <Minimize2 size={24} /> : <Maximize2 size={24} />}
                           </button>
                         </div>
                       </div>

                       <AutoEngagementCapture lectureId={lectureId} onScoreUpdate={handleScoreUpdate} playing={playing && camEnabled} />
                    </div>

                    <div className="bg-surface/30 rounded-[2.5rem] border border-white/5 p-8 overflow-hidden flex flex-col h-96 transition-all">
                       <div className="flex items-center justify-between mb-6">
                          <div className="flex items-center gap-3">
                             <div className="w-2 h-8 bg-primary rounded-full" />
                             <h3 className="text-xl font-black text-foreground uppercase tracking-tighter italic">Focus Level Graph</h3>
                          </div>
                          <div className="px-4 py-2 bg-white/5 rounded-xl border border-white/5 text-[10px] font-black text-primary uppercase tracking-widest">
                             Live Activity Sync
                          </div>
                       </div>
                        <div className="flex-1 flex flex-col gap-4">
                           <div className="h-24">
                              <EngagementWaveform data={engagementHistory} />
                           </div>
                           {/* Global Heatmap (Timeline Snapshot) */}
                           <div className="mt-2 pt-6 border-t border-white/5 h-32">
                              <EngagementHeatmap data={fullHistory} />
                           </div>
                        </div>
                    </div>
                  </div>

                  <div className="col-span-12 lg:col-span-4 flex flex-col space-y-8 h-full min-h-0">
                    <div className="flex flex-col glass-card border-white/5 h-[calc(100vh-450px)] min-h-[300px]">
                      <div className="p-8 border-b border-white/5 flex items-center justify-between">
                         <div className="flex items-center gap-4">
                            <div className="w-12 h-12 rounded-2xl bg-primary flex items-center justify-center text-white crimson-glow"><Bot size={24} /></div>
                            <div><h3 className="text-lg font-black text-foreground uppercase tracking-widest">Aika Hub</h3></div>
                         </div>
                         <button onClick={() => setMessages([{role: 'assistant', content: 'Context purged.'}])} className="text-white/20 hover:text-red-400"><Trash2 size={20} /></button>
                      </div>

                      <div className="flex-1 overflow-y-auto p-8 space-y-6 no-scrollbar">
                         {messages.map((m, i) => (
                           <div key={i} className={`flex flex-col gap-2 ${m.role === 'user' ? 'items-end' : ''}`}>
                              <div className={`p-5 rounded-[2rem] text-sm font-bold border ${m.role === 'user' ? 'bg-primary/5 border-primary/20 text-white rounded-tr-none' : 'bg-surface border-border text-white/90 rounded-tl-none'}`}>
                                {m.content}
                              </div>
                           </div>
                         ))}
                         {isTyping && <div className="animate-pulse flex gap-2"><div className="w-2 h-2 bg-primary rounded-full animate-bounce" /></div>}
                      </div>

                      <div className="p-8 bg-surface/50 border-t border-white/5 space-y-4">
                         <div className="flex gap-3 px-4 flex-wrap">
                            {attachments.map((at, idx) => (
                              <div key={idx} className="px-3 py-1 bg-primary/20 border border-primary/40 rounded-lg text-[9px] font-black text-white flex items-center gap-2">
                                 {at.name} <button onClick={() => setAttachments(prev => prev.filter((_, i) => i !== idx))}><Trash2 size={10} /></button>
                              </div>
                            ))}
                         </div>
                          <div className="flex gap-3">
                             <input type="file" ref={fileInputRef} onChange={handleFileUpload} multiple className="hidden" />
                             <button onClick={() => fileInputRef.current?.click()} className="w-12 h-12 rounded-2xl bg-white/5 flex items-center justify-center text-white/40 hover:text-white"><PlusIcon size={24} /></button>
                             <input type="text" value={chatInput} onChange={e => setChatInput(e.target.value)} onKeyDown={e => e.key === 'Enter' && handleChat()} className="flex-1 bg-background/50 border border-white/10 rounded-2xl px-6 text-sm py-3 text-white" placeholder="Ask a question..." />
                             <button onClick={handleChat} className="w-12 h-12 bg-primary rounded-2xl flex items-center justify-center text-white crimson-glow"><Send size={20} /></button>
                          </div>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-6">
                       <div className="glass-card p-8 border-white/5">
                          <div className="text-[10px] font-black text-text-muted uppercase tracking-widest mb-2 flex items-center gap-2">
                             <Zap size={10} className="text-primary" /> Focus Score
                          </div>
                          <div className="text-4xl font-black text-foreground italic">{(engagementScore?.engagement ?? 0).toFixed(1)}%</div>
                          <div className="h-1.5 w-full bg-white/5 rounded-full mt-4 overflow-hidden">
                             <div className="h-full bg-primary crimson-glow transition-all duration-1000" style={{ width: `${engagementScore?.engagement ?? 0}%` }} />
                          </div>
                       </div>
                       <div className="glass-card p-8 border-white/5">
                          <div className="text-[10px] font-black text-text-muted uppercase tracking-widest mb-2 flex items-center gap-2">
                             <Brain size={10} className="text-blue-400" /> Study Effort
                          </div>
                          <div className="text-4xl font-black text-foreground italic">{(engagementScore?.confusion ?? 0).toFixed(1)}%</div>
                          <div className="h-1.5 w-full bg-white/5 rounded-full mt-4 overflow-hidden">
                             <div className="h-full bg-blue-400 shadow-[0_0_8px_rgba(96,165,250,0.5)] transition-all duration-1000" style={{ width: `${engagementScore?.confusion ?? 0}%` }} />
                          </div>
                       </div>
                    </div>
                  </div>
                </div>
              )}
              
              {phase === 'quiz' && <QuizPhase lectureId={lectureId} onComplete={(res) => {setSessionResults(res); setPhase('feedback');}} />}
              {phase === 'feedback' && <FeedbackPhase lectureId={lectureId} onComplete={() => setPhase('summary')} />}
              {phase === 'summary' && <SessionSummary data={sessionResults} lectureId={lectureId} />}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
