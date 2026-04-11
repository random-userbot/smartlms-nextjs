'use client';

import React, { useState } from 'react';
import { Star, MessageSquare, Send, Sparkles, LayoutDashboard } from 'lucide-react';
import { feedbackAPI } from '@/lib/api';
import { useActivity } from '@/context/ActivityTracker';

interface FeedbackPhaseProps {
  lectureId: string;
  courseId: string;
  onComplete: () => void;
}

export default function FeedbackPhase({ lectureId, courseId, onComplete }: FeedbackPhaseProps) {
  const [ratings, setRatings] = useState<Record<string, number>>({
    clarity: 0,
    quality: 0,
    difficulty: 0,
    pacing: 0
  });
  const [comments, setComments] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const { trackEvent } = useActivity();

  const handleRating = (key: string, val: number) => {
    setRatings({ ...ratings, [key]: val });
  };

  const handleSubmit = async () => {
    setAnalyzing(true);
    trackEvent('feedback_submitted', { lecture_id: lectureId });

    try {
      const subRatings = [ratings.clarity, ratings.quality, ratings.difficulty, ratings.pacing].filter(v => v > 0);
      const overall = subRatings.length > 0 ? Math.round(subRatings.reduce((a,b) => a+b, 0) / subRatings.length) : 5;

      await feedbackAPI.submit({
        lecture_id: lectureId,
        course_id: courseId,
        overall_rating: overall,
        teaching_clarity: ratings.clarity,
        content_quality: ratings.quality,
        difficulty_level: ratings.difficulty,
        text: comments
      });
      
      setAnalyzing(false);
      setSubmitted(true);
      
      // Complete after delay
      setTimeout(onComplete, 3000);
    } catch (err) {
      console.error('Feedback submission failed:', err);
      setAnalyzing(false);
    }
  };

  if (submitted) {
    return (
      <div className="flex flex-col items-center justify-center h-full space-y-8 animate-fade-in text-center p-12">
        <div className="w-24 h-24 bg-success/20 rounded-full flex items-center justify-center text-success text-4xl font-black crimson-glow shimmer">
          <Star fill="currentColor" size={48} />
        </div>
        <div>
          <h2 className="text-4xl font-black text-white mb-2 tracking-tighter">Insights Synchronized</h2>
          <p className="text-text-muted font-bold">Your feedback has been integrated into the course evolution matrix.</p>
        </div>
        <div className="flex gap-4">
           <div className="px-6 py-2 bg-success/10 text-success border border-success/20 rounded-full text-[10px] font-black uppercase tracking-widest">
             +50 Reputation Points
           </div>
           <div className="px-6 py-2 bg-primary/10 text-primary border border-primary/20 rounded-full text-[10px] font-black uppercase tracking-widest">
             Level 2 Scholar
           </div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto space-y-12 animate-fade-in p-12">
      <div className="text-center space-y-4">
        <h2 className="text-5xl font-black text-white tracking-tighter">Feedback Protocol</h2>
        <p className="text-xl font-medium text-text-muted">Analyze your experience to refine future cognitive modules.</p>
      </div>

      <div className="space-y-8">
        {[
          { id: 'clarity', label: 'Instructional Clarity', desc: 'How understandable was the expert instructor?' },
          { id: 'quality', label: 'Content Depth', desc: 'Did the materials meet academic synchronization depth?' },
          { id: 'difficulty', label: 'Cognitive Load', desc: 'Complexity relative to your current node level.' },
          { id: 'pacing', label: 'Temporal Pacing', desc: 'Synchronization speed with your learning capacity.' }
        ].map((item) => (
          <div key={item.id} className="glass-card p-8 flex items-center justify-between group hover:border-primary/20 transition-all">
            <div className="space-y-1">
               <h3 className="text-lg font-black text-white">{item.label}</h3>
               <p className="text-xs font-semibold text-text-muted">{item.desc}</p>
            </div>
            <div className="flex gap-2">
              {[1, 2, 3, 4, 5].map((star) => (
                <button
                  key={star}
                  onClick={() => handleRating(item.id, star)}
                  className={`w-10 h-10 rounded-xl flex items-center justify-center transition-all ${
                    ratings[item.id] >= star 
                    ? 'bg-primary text-white crimson-glow scale-110' 
                    : 'bg-white/5 text-text-muted hover:bg-white/10'
                  }`}
                >
                  <Star size={18} fill={ratings[item.id] >= star ? 'currentColor' : 'none'} />
                </button>
              ))}
            </div>
          </div>
        ))}

        <div className="glass-card p-10 space-y-6">
           <div className="flex items-center gap-3">
             <MessageSquare size={24} className="text-primary" />
             <h3 className="text-xl font-black text-white tracking-tight">Qualitative Insights</h3>
           </div>
           <textarea 
            className="w-full h-32 bg-background/50 border border-white/5 rounded-2xl p-6 text-white text-sm font-medium focus:outline-none focus:border-primary/40 focus:bg-background transition-all"
            placeholder="Synthesize your overall impressions..."
            value={comments}
            onChange={(e) => setComments(e.target.value)}
           />
        </div>

        <button
          onClick={handleSubmit}
          disabled={analyzing || Object.values(ratings).some(v => v === 0)}
          className="w-full btn-primary py-6 text-xl flex items-center justify-center gap-4 disabled:opacity-50"
        >
          {analyzing ? <Sparkles className="animate-spin" /> : <Send size={24} />}
          {analyzing ? 'Synthesizing Data...' : 'Finalize Module Feedback'}
        </button>
      </div>
    </div>
  );
}
