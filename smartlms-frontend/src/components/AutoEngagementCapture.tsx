'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Camera, X, Maximize2, Minimize2, Video, VideoOff, Info } from 'lucide-react';
import EngagementCamera from './EngagementCamera';
import { engagementAPI } from '@/lib/api';
import { useActivity } from '@/context/ActivityTracker';

interface AutoEngagementCaptureProps {
  lectureId: string;
  onScoreUpdate?: (score: any) => void;
  onViolation?: (violation: { type: string; timestamp: number }) => void;
  playing: boolean;
  mode?: 'learning' | 'proctoring';
}

export default function AutoEngagementCapture({ 
  lectureId, 
  onScoreUpdate, 
  onViolation,
  playing,
  mode = 'learning'
}: AutoEngagementCaptureProps) {
  const [engagementScore, setEngagementScore] = useState<any>(null);
  const [camEnabled, setCamEnabled] = useState(true);
  const [enabled, setEnabled] = useState(true);
  const [minimized, setMinimized] = useState(false);
  const [status, setStatus] = useState<'idle' | 'initializing' | 'active' | 'denied'>('idle');
  const [alert, setAlert] = useState<string | null>(null);
  const [tabSwitches, setTabSwitches] = useState(0);
  const [lastActivity, setLastActivity] = useState(Date.now());
  const [isPolling, setIsPolling] = useState(false);
  const { sessionId, trackEvent } = useActivity();
  const featureBuffer = useRef<any[]>([]);
  const pollingInterval = useRef<NodeJS.Timeout | null>(null);
  const isInitializing = useRef(false);

  useEffect(() => {
    const handleVisibility = () => {
      if (document.hidden) {
        setTabSwitches(prev => prev + 1);
        trackEvent('tab_hidden', { lecture_id: lectureId });
      } else {
        trackEvent('tab_visible', { lecture_id: lectureId });
      }
    };
    document.addEventListener('visibilitychange', handleVisibility);
    return () => {
      document.removeEventListener('visibilitychange', handleVisibility);
      if (pollingInterval.current) clearInterval(pollingInterval.current);
    };
  }, [lectureId]);

  useEffect(() => {
    // Auto-enable camera when video plays - with stability guard
    if (playing && !enabled && !isInitializing.current) {
      isInitializing.current = true;
      setEnabled(true);
      setStatus('initializing');
      
      // Reset initialization guard after a cooldown
      setTimeout(() => {
        isInitializing.current = false;
      }, 2000);
    }
  }, [playing, enabled]);

  const handleFeaturesDetected = useCallback((features: any) => {
    // Strict Sync: Only process if playing
    if (!playing) {
      if (status !== 'idle' && status !== 'denied') setStatus('idle');
      return;
    }

    if (!features.face_detected) {
      if (status === 'active' && onViolation && mode === 'proctoring') {
         onViolation({ type: 'face_not_found', timestamp: Date.now() });
      }
      // Don't revert to initializing, stay in active but with 'no face' state if we've already started
      if (status === 'initializing') {
        // Still waiting for first real detection
      } else {
        setStatus('active'); // Keep active status but with face_detected: false logic
      }
      trackEvent('user_face_lost', { lecture_id: lectureId, timestamp: Date.now() });
      return;
    }
    
    setLastActivity(Date.now()); // Update activity timestamp
    
    // Check for multiple faces if the model supports it
    if (features.num_faces > 1 && onViolation && mode === 'proctoring') {
       onViolation({ type: 'multiple_faces', timestamp: Date.now() });
       trackEvent('integrity_violation', { type: 'multiple_faces', lecture_id: lectureId });
    }
    
    if (status !== 'active') {
      console.log("Neural Sync: Active signal received from MediaPipe.");
      setStatus('active');
    }
    
    // Add additional behavioral context
    const idleSeconds = Math.floor((Date.now() - lastActivity) / 1000);
    const enrichedFeatures = {
      ...features,
      session_id: sessionId,
      lecture_id: lectureId,
      tab_visible: !document.hidden,
      idle_duration: idleSeconds,
      timestamp: Date.now(),
    };

    featureBuffer.current.push(enrichedFeatures);

    // Submit batch every 150 frames (~5-7 seconds) to reduce network overhead
    if (featureBuffer.current.length >= 150) {
      submitBatch();
    }
  }, [playing, status, onViolation, mode, lectureId, sessionId, lastActivity, trackEvent]);

  const submitBatch = async () => {
    const batch = [...featureBuffer.current];
    featureBuffer.current = [];

    try {
      const res = await engagementAPI.submit({
        session_id: sessionId,
        lecture_id: lectureId,
        features: batch,
        watch_duration: 15, 
        tab_switches: tabSwitches,
        idle_time: Math.floor((Date.now() - lastActivity) / 1000),
      });
      
      // Reset local tab switch counter
      setTabSwitches(0);

      // Check if job is async
      // Check if job is async or completed
      const jobInfo = res.data.model_breakdown;
      if (jobInfo && jobInfo.status === 'queued' && jobInfo.job_id) {
        startPolling(jobInfo.job_id);
      } else if (res.data.overall_score !== undefined) {
        // Immediate sync success!
        handleScoreUpdate(res.data);
      } else {
        // Fallback to score update with whatever was returned
        handleScoreUpdate(res.data);
      }
    } catch (error: any) {
      console.error('Failed to submit engagement batch:', error);
      if (error.code === 'ERR_NETWORK' || !error.response) {
        featureBuffer.current = [...batch, ...featureBuffer.current].slice(-50);
      }
    }
  };

  const startPolling = (jobId: string) => {
    if (pollingInterval.current) clearInterval(pollingInterval.current);
    setIsPolling(true);
    
    let attempts = 0;
    pollingInterval.current = setInterval(async () => {
      try {
        attempts++;
        const res = await engagementAPI.getJobStatus(jobId);
        
        if (res.data.status === 'completed' && res.data.result) {
          handleScoreUpdate(res.data.result);
          stopPolling();
        } else if (res.data.status === 'failed' || attempts > 15) {
          console.warn("Engagement Sync: Job failed or timed out.");
          stopPolling();
        }
      } catch (err) {
        console.error("Polling error:", err);
        stopPolling();
      }
    }, 2000); // Poll every 2 seconds
  };

  const stopPolling = () => {
    if (pollingInterval.current) clearInterval(pollingInterval.current);
    pollingInterval.current = null;
    setIsPolling(false);
  };

  const handleScoreUpdate = (data: any) => {
    if (onScoreUpdate) {
      onScoreUpdate(data);
    }

    // Check for alerts (ignore if scores are effectively empty/default)
    if (data.overall_score > 0 && data.overall_score < 40) {
      setAlert("Focus pulse is low. Consider a deep breath or a short break.");
      setTimeout(() => setAlert(null), 5000);
    } else if (data.confusion > 60) {
      setAlert("Concept resonance detected as complex. Ask AIka for a simpler breakdown.");
      setTimeout(() => setAlert(null), 5000);
    }

    trackEvent('engagement_sync_completed', { 
      score: data.overall_score,
      icap: data.icap_classification
    });
  };

  if (!enabled) return (
     <div className="absolute bottom-8 right-8 z-[100]">
       <button 
        onClick={() => setEnabled(true)}
        className="w-12 h-12 bg-surface border border-border rounded-full flex items-center justify-center text-primary crimson-glow hover:scale-110 transition-all"
       >
         <Video size={20} />
       </button>
     </div>
  );

  return (
    <div className={`fixed bottom-8 right-8 z-[100] transition-all duration-700 ease-out glass-card p-6 border-blue-500/20 shadow-2xl
      ${minimized ? 'w-16 h-16 rounded-full' : 'w-80 h-72 rounded-[2.5rem]'}`}
      style={{ 
        transform: minimized ? 'scale(0.9)' : 'scale(1)',
        opacity: enabled ? 1 : 0 
      }}
    >
      {/* Header / Controls */}
      <div className="flex items-center justify-between mb-3">
        {!minimized && (
          <div className="flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${status === 'active' ? 'bg-blue-400 animate-pulse shadow-[0_0_8px_rgba(96,165,250,0.8)]' : 'bg-slate-600'}`} />
            <span className="text-[10px] font-black text-white uppercase tracking-widest flex items-center gap-2">
              {status === 'active' ? 'Neural Sync Active' : 'Initializing...'}
              <span className="px-1.5 py-0.5 bg-blue-500/20 border border-blue-500/40 rounded text-[7px] text-blue-300">PiP</span>
            </span>
          </div>
        )}
        <div className="flex items-center gap-2 ml-auto">
          <button onClick={() => setMinimized(!minimized)} className="text-white/40 hover:text-white transition-colors">
            {minimized ? <Maximize2 size={14} /> : <Minimize2 size={14} />}
          </button>
          <button onClick={() => setEnabled(false)} className="text-white/40 hover:text-danger transition-colors">
            <X size={14} />
          </button>
        </div>
      </div>

      {/* Main Feature View */}
      {!minimized ? (
        <div className="relative flex-1 h-40 rounded-2xl overflow-hidden border border-white/5">
          <EngagementCamera 
            enabled={enabled} 
            playing={playing}
            onFeaturesDetected={handleFeaturesDetected} 
          />
          
          {/* Overlay Stats */}
          <div className="absolute top-3 left-3 flex flex-col gap-1.5">
             <div className="px-2 py-0.5 bg-black/60 backdrop-blur-md rounded text-[8px] font-black text-primary flex items-center gap-1 uppercase">
               <Camera size={8} /> Gaze Active
             </div>
             {onScoreUpdate && (
               <div className={`px-2 py-0.5 backdrop-blur-md rounded text-[8px] font-black text-white flex items-center gap-1 uppercase ${isPolling ? 'bg-amber-500/40 animate-pulse' : 'bg-blue-500/40'}`}>
                 {isPolling ? 'Neural Sync: Processing' : 'Neural Sync: Stable'}
               </div>
             )}
          </div>

          {alert && (
            <div className="absolute inset-0 bg-primary/40 backdrop-blur-sm flex items-center justify-center p-4 text-center animate-fade-in">
               <div className="text-[10px] font-black text-white uppercase tracking-tighter leading-tight drop-shadow-lg">
                 Alert: {alert}
               </div>
            </div>
          )}
        </div>
      ) : (
        <div className="flex items-center justify-center h-full">
           <Video className="text-primary animate-pulse" size={24} />
        </div>
      )}

      {alert && (
        <div className="absolute -top-16 left-0 right-0 bg-danger/90 backdrop-blur-xl border border-danger/30 text-white text-[10px] p-3 rounded-2xl animate-in slide-in-from-bottom-2 flex items-center gap-2 shadow-2xl">
          <Info size={14} className="text-white shrink-0" />
          <span className="font-bold tracking-tight">{alert}</span>
        </div>
      )}

      {!minimized && (
        <p className="mt-3 text-[8px] font-medium text-white/40 leading-tight italic">
          AIka Sensei is analyzing your cognitive resonance with the current lecture module.
        </p>
      )}
    </div>
  );
}
