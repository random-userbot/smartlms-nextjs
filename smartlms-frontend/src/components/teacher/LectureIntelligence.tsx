'use client';

import React, { useState, useEffect } from 'react';
import { analyticsAPI } from '@/lib/api';
import { 
  AlertCircle, 
  Lightbulb, 
  Target, 
  ChevronRight, 
  BarChart3, 
  BrainCircuit,
  Clock,
  MessageSquare,
  FileText
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceArea, ReferenceLine } from 'recharts';
import TranscriptPanel from '../lecture/TranscriptPanel';

interface FrictionZone {
  start: number;
  end: number;
  avg_engagement: number;
}

interface TopicAnalysis {
  timestamp: string;
  topic: string;
  friction_reason: string;
}

interface IntelligenceData {
  lecture_id: string;
  lecture_title: string;
  total_students: number;
  transcript: string;
  friction_zones: FrictionZone[];
  topic_analysis: TopicAnalysis[];
  recommendations: string[];
  overall_sentiment: string;
}

export default function LectureIntelligence({ lectureId }: { lectureId: string }) {
  const [data, setData] = useState<IntelligenceData | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedTopic, setSelectedTopic] = useState<number | null>(null);

  useEffect(() => {
    if (!lectureId) return;
    setLoading(true);
    analyticsAPI.getLectureIntelligence(lectureId)
      .then(res => setData(res.data))
      .catch(err => console.error("Intelligence fetch failed", err))
      .finally(() => setLoading(false));
  }, [lectureId]);

  if (loading) {
    return (
      <div className="w-full h-96 flex flex-col items-center justify-center space-y-4 bg-surface/20 rounded-[2.5rem] border border-white/5">
        <div className="w-10 h-10 border-4 border-primary/20 border-t-primary rounded-full animate-spin" />
        <div className="text-[10px] font-black text-text-muted uppercase tracking-[0.4em] animate-pulse">Running Cognitive Audit...</div>
      </div>
    );
  }

  if (!data || data.friction_zones.length === 0) {
    return (
      <div className="w-full p-12 text-center bg-surface/20 rounded-[2.5rem] border border-white/5 space-y-4">
        <div className="w-16 h-16 bg-white/5 rounded-3xl flex items-center justify-center mx-auto">
          <Target size={32} className="text-white/20" />
        </div>
        <div className="space-y-1">
          <h3 className="text-lg font-black text-foreground">Optimal Cognitive Sync</h3>
          <p className="text-xs text-text-muted max-w-xs mx-auto">No significant struggle zones detected for this lecture yet. Students are moving through content as expected.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-10 animate-fade-in">
      {/* Header Summary */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
         <div className="glass-card p-8 border-primary/20 bg-primary/5">
            <div className="flex items-center gap-3 mb-4">
               <div className="p-2 bg-primary/20 rounded-xl"><BrainCircuit className="text-primary" size={20} /></div>
               <span className="text-[10px] font-black text-text-muted uppercase tracking-widest">Mind Drift Analysis</span>
            </div>
            <div className="text-4xl font-black text-foreground">{data.friction_zones.length}</div>
            <div className="text-[10px] font-bold text-text-muted uppercase tracking-tight mt-1">Struggle Points Identified</div>
         </div>
         
         <div className="col-span-2 glass-card p-8 flex items-center justify-between group overflow-hidden">
            <div className="space-y-4 z-10">
               <div>
                  <span className="text-[10px] font-black text-text-muted uppercase tracking-widest">Primary Pedagogical Gap</span>
                  <div className="text-xl font-black text-foreground mt-1 group-hover:text-primary transition-colors">
                     {data.topic_analysis[0]?.topic || "General Engagement Drop"}
                  </div>
               </div>
               <p className="text-xs text-text-muted italic max-w-md">
                 "{data.topic_analysis[0]?.friction_reason || "Frequent context switching detected."}"
               </p>
            </div>
            <div className="absolute right-0 top-0 p-12 opacity-5 pointer-events-none group-hover:opacity-10 transition-opacity">
               <Target size={120} className="text-white" />
            </div>
         </div>
      </div>

      {/* Friction Timeline */}
      <div className="space-y-6">
        <div className="flex items-center justify-between">
           <h3 className="text-2xl font-black text-foreground tracking-tight flex items-center gap-3">
              <BarChart3 className="text-primary" /> Struggle Timeline
           </h3>
           <div className="flex items-center gap-6">
              <button 
                 onClick={() => setSelectedTopic(null)}
                 className={`text-[10px] font-black uppercase tracking-widest transition-all ${selectedTopic === null ? 'text-primary' : 'text-text-muted hover:text-white'}`}
              >
                 Analysis View
              </button>
              <button 
                 onClick={() => setSelectedTopic(-1)} // Use -1 as tag for transcript view
                 className={`text-[10px] font-black uppercase tracking-widest transition-all ${selectedTopic === -1 ? 'text-primary' : 'text-text-muted hover:text-white'}`}
              >
                 Script View
              </button>
           </div>
        </div>
        
        <div className="h-[300px] glass-card p-8">
           <ResponsiveContainer width="100%" height="100%">
              <LineChart data={[{t: 0, s: 70}, {t: 100, s: 80}]}> {/* Dummy data just for scale */}
                 <XAxis dataKey="t" hide />
                 <YAxis domain={[0, 100]} hide />
                 {data.friction_zones.map((zone, i) => (
                    <ReferenceArea 
                       key={i}
                       x1={zone.start} 
                       x2={zone.end} 
                       fill="rgba(204, 51, 68, 0.4)" 
                       stroke="rgba(204, 51, 68, 0.6)"
                       strokeWidth={1}
                       label={{ 
                          value: `Zone ${i+1}`, 
                          position: 'top', 
                          fill: '#CC3344', 
                          fontSize: 8, 
                          fontWeight: 'black'
                       }}
                    />
                 ))}
                 <Tooltip />
              </LineChart>
           </ResponsiveContainer>
        </div>
      </div>

      {/* Drill-down Topics & Recommendations */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
         {/* LEFT COLUMN: Topics or Transcript */}
         <div className="space-y-6">
            <h4 className="text-[10px] font-black text-primary uppercase tracking-[0.3em]">
               {selectedTopic === -1 ? "Pedagogical Script" : "Topic Drill-down"}
            </h4>
            
            <div className="h-[500px] overflow-hidden">
               {selectedTopic === -1 ? (
                  <div className="h-full glass-card overflow-hidden">
                     <TranscriptPanel transcript={data.transcript} />
                  </div>
               ) : (
                  <div className="space-y-4 max-h-full overflow-y-auto pr-2 no-scrollbar">
                     {data.topic_analysis.map((topic, i) => (
                        <button 
                           key={i}
                           onClick={() => setSelectedTopic(i)}
                           className={`w-full text-left p-6 rounded-3xl border-2 transition-all group flex items-start gap-4
                              ${selectedTopic === i ? 'bg-primary/10 border-primary text-primary' : 'bg-surface border-border text-foreground hover:border-primary/40'}`}
                        >
                           <div className={`p-3 rounded-2xl border-2 shrink-0 ${selectedTopic === i ? 'bg-primary text-white border-transparent' : 'bg-white/5 border-border group-hover:border-primary/40'}`}>
                              <MessageSquare size={18} />
                           </div>
                           <div className="space-y-1">
                              <div className="flex items-center gap-3">
                                 <span className="text-xs font-black uppercase tracking-widest opacity-60 flex items-center gap-1">
                                    <Clock size={10} /> {topic.timestamp}s
                                 </span>
                                 {selectedTopic === i && <motion.span layoutId="active" className="text-[8px] font-black uppercase bg-primary text-white px-2 py-0.5 rounded-full">Viewing Details</motion.span>}
                              </div>
                              <h5 className="text-lg font-black leading-tight">{topic.topic}</h5>
                              {selectedTopic === i && (
                                 <motion.p 
                                   initial={{ opacity: 0, height: 0 }}
                                   animate={{ opacity: 1, height: 'auto' }}
                                   className="text-xs font-medium text-text-muted mt-2 leading-relaxed italic"
                                 >
                                   {topic.friction_reason}
                                 </motion.p>
                              )}
                           </div>
                        </button>
                     ))}
                  </div>
               )}
            </div>
         </div>

         {/* RIGHT COLUMN: AI Advice */}
         <div className="space-y-6">
            <h4 className="text-[10px] font-black text-success uppercase tracking-[0.3em]">Pedagogical Recommendations</h4>
            <div className="glass-card overflow-hidden">
               <div className="bg-success/20 p-8 border-b border-success/20 flex items-center justify-between">
                  <div className="flex items-center gap-4">
                     <div className="p-3 bg-success text-white rounded-2xl"><Lightbulb size={24} /></div>
                     <div>
                        <div className="text-[10px] font-black text-success uppercase tracking-widest">Aika Strategic Insights</div>
                        <div className="text-xl font-black text-foreground">Teaching Optimization</div>
                     </div>
                  </div>
               </div>
               <div className="p-8 space-y-6">
                  {data.recommendations.map((rec, i) => (
                     <div key={i} className="flex gap-4 group">
                        <div className="mt-1 w-6 h-6 rounded-full bg-white/5 border border-border flex items-center justify-center text-[10px] font-black group-hover:bg-success group-hover:text-white transition-all">
                           {i + 1}
                        </div>
                        <p className="text-sm font-medium text-text-muted leading-relaxed flex-1 italic">
                           {rec}
                        </p>
                     </div>
                  ))}
                  
                  <button className="w-full mt-6 py-4 rounded-2xl border-2 border-dashed border-success/40 text-success text-[10px] font-black uppercase tracking-widest hover:bg-success/5 transition-all">
                     View Complete Pedagogical Report
                  </button>
               </div>
            </div>
         </div>
      </div>
    </div>
  );
}
