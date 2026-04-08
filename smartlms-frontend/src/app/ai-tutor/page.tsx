'use client';

import React, { useState, useEffect, useRef } from 'react';
import { tutorAPI } from '@/lib/api';
import { 
  Bot, 
  Send, 
  Plus, 
  MessageSquare, 
  Search, 
  Trash2, 
  User, 
  ChevronRight,
  Sparkles,
  Loader2,
  Mic,
  MicOff,
  Volume2,
  VolumeX,
  FilePlus,
  Trash
} from 'lucide-react';
import Sidebar from '@/components/Sidebar';
import NavigationHeader from '@/components/NavigationHeader';

export default function AikaPage() {
  const [sessions, setSessions] = useState<any[]>([]);
  const [activeSession, setActiveSession] = useState<string | null>(null);
  const [messages, setMessages] = useState<any[]>([]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [mode, setMode] = useState<string>('general');
  const [model, setModel] = useState<string>('groq-llama-3');
  const [attachments, setAttachments] = useState<any[]>([]);
  const [isListening, setIsListening] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const recognitionRef = useRef<any>(null);

  useEffect(() => {
    loadSessions();
    if (typeof window !== 'undefined' && ('SpeechRecognition' in window || 'webkitSpeechRecognition' in window)) {
      const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
      recognitionRef.current = new SpeechRecognition();
      recognitionRef.current.continuous = false;
      recognitionRef.current.interimResults = false;

      recognitionRef.current.onresult = (event: any) => {
        const transcript = event.results[0][0].transcript;
        setInput(prev => prev + (prev ? ' ' : '') + transcript);
        setIsListening(false);
      };

      recognitionRef.current.onerror = () => setIsListening(false);
      recognitionRef.current.onend = () => setIsListening(false);
    }
  }, []);

  useEffect(() => {
    if (activeSession) {
      loadMessages(activeSession);
    } else {
      setMessages([{
        role: 'assistant',
        content: "I am Aika, your cognitive sensei. How shall we refine your knowledge today?"
      }]);
    }
  }, [activeSession]);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const loadSessions = async () => {
    try {
      const res = await tutorAPI.getSessions();
      setSessions(res.data || []);
    } catch (err) {
      console.error(err);
    }
  };

  const loadMessages = async (id: string) => {
    try {
      const res = await tutorAPI.getSessionMessages(id);
      setMessages(res.data || []);
      const session = sessions.find(s => s.id === id);
      if (session?.mode) setMode(session.mode);
    } catch (err) {
      console.error(err);
    }
  };

  const handleSend = async () => {
    if (!input.trim() || isTyping) return;

    let sessionId = activeSession;
    const userMsg = { role: 'user', content: input };
    const history = [...messages, userMsg];
    
    setMessages(history);
    setInput('');
    setIsTyping(true);

    try {
      const res = await tutorAPI.chat({
        messages: history,
        mode,
        session_id: sessionId || undefined,
        attachments: attachments.length > 0 ? attachments : undefined
      });

      // Simple non-streaming handling for this refinement
      const aiMsg = { role: 'assistant', content: res };
      setMessages(prev => [...prev, aiMsg]);
      setAttachments([]);
      
      if (!sessionId) {
        loadSessions();
      }
    } catch (err) {
      console.error(err);
    } finally {
      setIsTyping(false);
    }
  };

  const handleDeleteSession = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (confirm("Permanently archive this dialogue?")) {
      try {
        await tutorAPI.deleteSession(id);
        setSessions(prev => prev.filter(s => s.id !== id));
        if (activeSession === id) {
          setActiveSession(null);
          setMessages([]);
        }
      } catch (err) {
        console.error(err);
      }
    }
  };

  const handleDeleteMessage = async (messageId: string) => {
     try {
       await tutorAPI.deleteMessage(messageId);
       setMessages(prev => prev.filter(m => m.id !== messageId));
     } catch (err) {
       console.error("Failed to delete message:", err);
     }
  };

  const clearChat = () => {
    if (confirm("Clear current session context?")) {
      setMessages([{
        role: 'assistant',
        content: "Context cleared. How shall we refine your knowledge today?"
      }]);
    }
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    Array.from(files).forEach(file => {
      const reader = new FileReader();
      reader.onload = (event) => {
        setAttachments(prev => [...prev, {
          name: file.name,
          type: file.type,
          data: event.target?.result
        }]);
      };
      if (file.type.startsWith('image/') || file.type === 'application/pdf') {
        reader.readAsDataURL(file);
      } else {
        reader.readAsText(file);
      }
    });

    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const toggleListening = () => {
    if (isListening) {
      recognitionRef.current?.stop();
      setIsListening(false);
    } else {
      try {
        recognitionRef.current?.start();
        setIsListening(true);
      } catch (e) {
        console.error("Speech recognition error:", e);
      }
    }
  };

  const speak = (text: string) => {
    if (typeof window === 'undefined') return;
    window.speechSynthesis.cancel();
    if (isSpeaking) {
      setIsSpeaking(false);
      return;
    }

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
    utterance.onerror = () => setIsSpeaking(false);
    
    window.speechSynthesis.speak(utterance);
  };

  return (
    <div className="flex h-screen bg-background overflow-hidden">
      <Sidebar />
      
      <main className="flex-1 ml-64 flex flex-col relative">
        <NavigationHeader title="Aika Neural Hub" showBack={true} />
        
        <div className="flex flex-1 overflow-hidden">
          {/* Aika AI Sidebar */}
          <aside className="w-80 border-r border-border flex flex-col bg-surface/30 backdrop-blur-3xl">
            <div className="p-6 border-b border-border">
              <button 
                onClick={() => setActiveSession(null)}
                className="w-full btn-primary flex items-center justify-center gap-2 py-4 rounded-2xl group transition-all"
              >
                <Plus size={18} className="group-hover:rotate-90 transition-transform" /> 
                <span className="font-black uppercase tracking-widest text-[10px]">New Neural Link</span>
              </button>
            </div>
            
            <div className="flex-1 overflow-y-auto p-4 space-y-2 no-scrollbar">
              <div className="text-[10px] uppercase tracking-[0.3em] font-black text-text-muted px-4 mb-4">Past Sessions</div>
              {sessions.map((s) => (
                <div key={s.id} className="relative group/session px-2">
                  <button
                    onClick={() => setActiveSession(s.id)}
                    className={`w-full flex items-center gap-3 p-4 rounded-2xl transition-all text-left group ${
                      activeSession === s.id ? 'bg-primary/10 border border-primary/20 scale-105' : 'hover:bg-white/5 border border-transparent'
                    }`}
                  >
                    <MessageSquare size={16} className={activeSession === s.id ? 'text-primary' : 'text-text-muted'} />
                    <div className="flex-1 overflow-hidden">
                      <div className={`text-xs font-bold truncate ${activeSession === s.id ? 'text-white' : 'text-text-muted group-hover:text-white'}`}>
                        {s.title}
                      </div>
                      <div className="text-[8px] font-black text-text-muted/40 uppercase tracking-widest mt-1">
                        {new Date(s.updated_at).toLocaleDateString()} • {s.mode || 'general'}
                      </div>
                    </div>
                  </button>
                  <button 
                    onClick={(e) => handleDeleteSession(s.id, e)}
                    className="absolute right-4 top-1/2 -translate-y-1/2 p-2 text-text-muted hover:text-red-400 opacity-0 group-hover/session:opacity-100 transition-all"
                  >
                    <Trash size={14} />
                  </button>
                </div>
              ))}
            </div>
          </aside>

          {/* Chat Display */}
          <div className="flex-1 flex flex-col relative bg-[url('/noise.png')] bg-repeat">
            <header className="p-8 flex items-center justify-between border-b border-white/5 bg-background/50 backdrop-blur-md z-20">
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 rounded-2xl bg-primary flex items-center justify-center text-white crimson-glow">
                  <Bot size={24} />
                </div>
                <div>
                  <h2 className="text-xl font-black text-white flex items-center gap-2">
                    Aika Sensei <Sparkles className="text-primary animate-pulse" size={16} />
                  </h2>
                  <div className="flex items-center gap-2 text-[10px] font-black text-text-muted uppercase tracking-widest">
                     <div className="w-1.5 h-1.5 rounded-full bg-success animate-ping"></div> Neural Sync Active
                  </div>
                </div>
              </div>

               <div className="flex items-center gap-3">
                  <select 
                    value={model} 
                    onChange={(e) => setModel(e.target.value)}
                    className="bg-surface/50 border border-white/10 rounded-xl px-4 py-2 text-[10px] font-black text-white/60 focus:outline-none appearance-none cursor-pointer hover:border-primary/50 transition-colors"
                  >
                     <option value="groq-llama-3">Llama-3-70b Professional</option>
                     <option value="gemini-1.5-pro">Gemini 1.5 Pro</option>
                     <option value="gpt-4o">GPT-4o Reasoning</option>
                  </select>
                  <button 
                    onClick={clearChat}
                    className="p-3 bg-white/5 border border-white/10 rounded-xl text-white/40 hover:text-red-400 transition-all group"
                    title="Purge Context"
                  >
                    <Trash2 size={18} className="group-hover:scale-110 transition-transform" />
                  </button>
               </div>
            </header>

            <div className="flex-1 overflow-y-auto pt-12 pb-48 px-8 lg:px-32 no-scrollbar">
              <div className="max-w-3xl mx-auto space-y-10">
                {messages.map((msg, i) => (
                  <div key={i} className={`flex gap-6 animate-fade-in ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
                    <div className={`w-10 h-10 rounded-2xl flex items-center justify-center flex-shrink-0 transition-transform hover:scale-110 ${
                      msg.role === 'user' ? 'bg-white/10 text-white border border-white/5' : 'bg-primary text-white crimson-glow'
                    }`}>
                      {msg.role === 'user' ? <User size={20} /> : <Bot size={20} />}
                    </div>
                    <div className={`flex flex-col gap-2 max-w-[85%] ${msg.role === 'user' ? 'items-end' : ''}`}>
                       <div className="text-[10px] font-black text-text-muted uppercase tracking-widest mb-1 opacity-50">
                         {msg.role === 'user' ? 'Disciple' : 'Sensei'}
                       </div>
                        <div className={`p-7 rounded-[2.5rem] text-[15px] font-medium leading-[1.8] relative group/msg shadow-xl ${
                          msg.role === 'user' 
                          ? 'bg-primary/5 text-white border border-primary/20 rounded-tr-none' 
                          : 'bg-surface border border-white/5 rounded-tl-none text-white/90'
                        }`}>
                          {msg.content}
                          {msg.role === 'assistant' && (
                            <button 
                              onClick={() => speak(msg.content)}
                              className="absolute -right-14 top-1/2 -translate-y-1/2 p-3 bg-background border border-white/10 rounded-2xl text-white/40 hover:text-primary opacity-0 group-hover/msg:opacity-100 transition-all hover:scale-110"
                            >
                              {isSpeaking ? <VolumeX size={16} className="animate-pulse" /> : <Volume2 size={16} />}
                            </button>
                          )}
                        </div>
                    </div>
                  </div>
                ))}
                {isTyping && (
                  <div className="flex gap-6 animate-pulse">
                    <div className="w-10 h-10 rounded-2xl bg-primary flex items-center justify-center text-white crimson-glow">
                      <Bot size={20} />
                    </div>
                    <div className="flex flex-col gap-4">
                       <div className="h-4 bg-white/5 w-64 rounded-full" />
                       <div className="h-4 bg-white/5 w-48 rounded-full" />
                    </div>
                  </div>
                )}
                <div ref={scrollRef} />
              </div>
            </div>

            <div className="absolute bottom-0 left-0 right-0 p-10 bg-gradient-to-t from-background via-background/90 to-transparent pointer-events-none">
              <div className="max-w-4xl mx-auto relative group pointer-events-auto">
                <div className="absolute -inset-1 bg-gradient-to-r from-primary/50 to-accent/50 rounded-[3rem] opacity-30 blur-2xl group-focus-within:opacity-60 transition-opacity"></div>
                
                <div className="relative bg-surface/80 backdrop-blur-3xl p-3 rounded-[3rem] border border-white/10 flex flex-col gap-4 shadow-[0_32px_64px_-16px_rgba(0,0,0,0.5)]">
                  {attachments.length > 0 && (
                    <div className="flex gap-3 px-6 pt-2">
                       {attachments.map((at, idx) => (
                         <div key={idx} className="relative group/at animate-scale-in">
                            <div className="px-4 py-2 bg-primary/10 border border-primary/30 rounded-xl text-[10px] font-black text-white/70 flex items-center gap-3">
                               <FilePlus size={14} className="text-primary" /> {at.name}
                            </div>
                            <button 
                              onClick={() => setAttachments(prev => prev.filter((_, i) => i !== idx))}
                              className="absolute -top-2 -right-2 w-5 h-5 bg-red-500 rounded-full flex items-center justify-center text-[10px] text-white shadow-lg"
                            >
                               <Trash2 size={12} />
                            </button>
                         </div>
                       ))}
                    </div>
                  )}

                  <div className="flex items-center gap-3">
                    <input 
                      type="file" 
                      ref={fileInputRef} 
                      onChange={handleFileUpload} 
                      multiple
                      className="hidden" 
                    />
                    <button 
                      onClick={() => fileInputRef.current?.click()}
                      className="w-14 h-14 rounded-full flex items-center justify-center text-white/30 hover:text-white hover:bg-white/5 transition-all ml-2"
                    >
                       <Plus size={28} />
                    </button>

                    <div className="flex gap-1.5 border-r border-white/5 pr-4 mr-2 hidden lg:flex">
                      {['general', 'speaking', 'listening', 'conversing'].map(m => (
                        <button 
                          key={m} 
                          onClick={() => setMode(m)}
                          className={`px-3 py-2 rounded-xl border text-[8px] font-black tracking-widest transition-all uppercase
                            ${mode === m ? 'bg-primary border-primary text-white crimson-glow' : 'bg-white/5 border-white/10 text-white/20 hover:border-white/40'}`}
                        >
                          {m}
                        </button>
                      ))}
                    </div>

                    <input 
                      type="text" 
                      value={input}
                      onChange={(e) => setInput(e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                      placeholder="Consult the neural sensei..."
                      className="flex-1 bg-transparent px-2 py-4 text-white placeholder-text-muted/30 focus:outline-none font-bold text-lg"
                    />

                    <button 
                      onClick={toggleListening}
                      className={`w-14 h-14 rounded-full flex items-center justify-center transition-all ${
                        isListening ? 'bg-red-500/20 text-red-500 border border-red-500/50 pulse-glow' : 'text-white/30 hover:text-white hover:bg-white/5'
                      }`}
                    >
                       {isListening ? <MicOff size={24} /> : <Mic size={24} />}
                    </button>

                    <button 
                      onClick={handleSend}
                      disabled={!input.trim() || isTyping}
                      className="w-16 h-16 rounded-[2rem] bg-primary flex items-center justify-center text-white crimson-glow hover:scale-105 active:scale-95 transition-all disabled:opacity-50 shadow-2xl"
                    >
                      {isTyping ? <Loader2 className="animate-spin" /> : <Send size={24} />}
                    </button>
                  </div>
                </div>
                <div className="text-center mt-6 text-[9px] font-black text-text-muted/20 uppercase tracking-[0.5em] animate-pulse">
                  Cognitive Link Synchronized
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
