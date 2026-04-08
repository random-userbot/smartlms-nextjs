'use client';

import React, { useState, useEffect } from 'react';
import { Timer, CheckCircle2, XCircle, AlertCircle, Sparkles, Send } from 'lucide-react';
import { quizzesAPI } from '@/lib/api';
import { useActivity } from '@/context/ActivityTracker';

interface QuizPhaseProps {
  lectureId: string;
  onComplete: (score: any) => void;
}

export default function QuizPhase({ lectureId, onComplete }: QuizPhaseProps) {
  const [quiz, setQuiz] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [answers, setAnswers] = useState<Record<number, number>>({});
  const [submitted, setSubmitted] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [timeLeft, setTimeLeft] = useState(300); // 5 mins
  const { trackEvent } = useActivity();

  useEffect(() => {
    setLoading(true);
    quizzesAPI.getByLecture(lectureId).then(res => {
      let qData = null;
      if (Array.isArray(res.data) && res.data.length > 0) {
        qData = res.data[0];
      } else if (res.data && !Array.isArray(res.data)) {
        qData = res.data;
      }
      setQuiz(qData);
    }).catch(err => {
      console.error("Failed to load quiz for lecture:", err);
    }).finally(() => {
      setLoading(false);
    });
  }, [lectureId]);

  useEffect(() => {
    if (submitted || !quiz) return;
    if (timeLeft <= 0) {
      handleSubmit();
      return;
    }
    const timer = setInterval(() => setTimeLeft(t => t - 1), 1000);
    return () => clearInterval(timer);
  }, [timeLeft, quiz, submitted]);

  const handleSubmit = async () => {
    setSubmitted(true);
    try {
      const res = await quizzesAPI.submitAttempt({
        quiz_id: quiz.id,
        answers: Object.entries(answers).map(([idx, opt]) => ({
          question_index: parseInt(idx),
          selected_option_index: opt
        })),
        time_spent_seconds: 300 - timeLeft
      });
      setResult(res.data);
      
      // Auto-transition after 5 seconds to Feedback phase
      setTimeout(() => onComplete(res.data), 5000);
    } catch (err) {
      console.error('Quiz submission failed:', err);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-64 space-y-4">
        <Sparkles className="text-primary animate-pulse" size={48} />
        <p className="text-sm font-black text-white/40 uppercase tracking-widest">Generating Cognitive Checkpoints...</p>
      </div>
    );
  }

  if (!quiz) {
    return (
      <div className="glass-card p-12 flex flex-col items-center gap-6 text-center">
         <AlertCircle className="text-primary" size={48} />
         <h3 className="text-2xl font-black text-white">No Validation Required</h3>
         <p className="text-text-muted max-w-md">Our neural hub hasn't mapped a quiz for this specific lecture module yet. You're clear to proceed.</p>
         <button onClick={() => onComplete({ score: 0, max_score: 0 })} className="btn-primary px-8 py-3">Continue Path</button>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-12 animate-fade-in p-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-4xl font-black text-white tracking-tighter mb-2">Cognitive Validation</h2>
          <p className="text-text-muted font-medium">Synchronizing learned nodes with neural checkpoints.</p>
        </div>
        <div className="bg-primary/20 border border-primary/20 px-6 py-3 rounded-2xl flex items-center gap-3 font-black text-primary crimson-glow">
          <Timer size={24} /> {Math.floor(timeLeft / 60)}:{(timeLeft % 60).toString().padStart(2, '0')}
        </div>
      </div>

      {/* Questions */}
      <div className="space-y-8">
        {quiz.questions.map((q: any, qIdx: number) => (
          <div key={qIdx} className="glass-card p-10 space-y-6 relative overflow-hidden group">
            {result && (
              <div className="absolute top-4 right-4">
                {result.feedback[qIdx]?.is_correct ? 
                  <CheckCircle2 className="text-success" size={32} /> : 
                  <XCircle className="text-danger" size={32} />
                }
              </div>
            )}
            
            <h3 className="text-xl font-bold text-white leading-relaxed">
              <span className="text-primary font-black mr-4">{qIdx + 1}.</span>
              {q.question_text}
            </h3>

            <div className="grid gap-4">
              {q.options.map((opt: string, oIdx: number) => {
                const isSelected = answers[qIdx] === oIdx;
                const isCorrect = result?.feedback[qIdx]?.is_correct;
                const wasCorrect = q.correct_answer_index === oIdx;

                return (
                  <button
                    key={oIdx}
                    disabled={submitted}
                    onClick={() => setAnswers({ ...answers, [qIdx]: oIdx })}
                    className={`w-full text-left p-6 rounded-2xl border transition-all flex items-center gap-4 group/btn ${
                      isSelected 
                      ? 'bg-primary/10 border-primary shadow-lg' 
                      : 'bg-white/5 border-white/5 hover:border-white/20'
                    } ${result && wasCorrect ? 'bg-success/10 border-success/40' : ''}`}
                  >
                    <div className={`w-8 h-8 rounded-lg flex items-center justify-center font-black transition-all ${
                      isSelected ? 'bg-primary text-white scale-110' : 'bg-surface text-text-muted group-hover/btn:text-white'
                    }`}>
                      {String.fromCharCode(65 + oIdx)}
                    </div>
                    <span className={`font-medium ${isSelected ? 'text-white' : 'text-text-muted hover:text-white'}`}>
                      {opt}
                    </span>
                  </button>
                );
              })}
            </div>

            {result && !result.feedback[qIdx]?.is_correct && (
              <div className="p-6 bg-primary/5 rounded-2xl border border-primary/10 flex gap-4 animate-fade-in">
                <AlertCircle className="text-primary shrink-0" size={20} />
                <p className="text-sm text-white/80 leading-relaxed italic">
                  <span className="font-black text-primary uppercase text-[10px] block mb-1">Aika Insight</span>
                  {result.feedback[qIdx]?.explanation || "The underlying concept involves neural plasticity and cross-functional synchronization."}
                </p>
              </div>
            )}
          </div>
        ))}
      </div>

      <button
        onClick={handleSubmit}
        disabled={submitted || Object.keys(answers).length < quiz.questions.length}
        className="w-full btn-primary py-6 text-xl flex items-center justify-center gap-4 disabled:opacity-50 disabled:scale-100"
      >
        {submitted ? <Sparkles className="animate-spin" /> : <Send />}
        {submitted ? 'Processing Feedback...' : 'Validate Progress'}
      </button>

      {result && (
        <div className="fixed inset-0 z-[200] flex items-center justify-center bg-background/80 backdrop-blur-xl animate-fade-in">
          <div className="text-center space-y-8 p-12 glass-card max-w-xl crimson-glow">
            <div className="w-32 h-32 bg-primary/20 rounded-full flex items-center justify-center mx-auto text-6xl font-black text-primary shimmer">
              {result.percentage.toFixed(0)}%
            </div>
            <div>
              <h2 className="text-4xl font-black text-white mb-2">Sync Complete</h2>
              <p className="text-text-muted font-bold">Awarded {result.score} XP Points</p>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="p-4 bg-white/5 rounded-2xl border border-white/5">
                <div className="text-2xl font-black text-white">{result.correct_count}</div>
                <div className="text-[10px] font-black text-text-muted uppercase">Correct</div>
              </div>
               <div className="p-4 bg-white/5 rounded-2xl border border-white/5">
                <div className="text-2xl font-black text-white">{300 - timeLeft}s</div>
                <div className="text-[10px] font-black text-text-muted uppercase">Latency</div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
