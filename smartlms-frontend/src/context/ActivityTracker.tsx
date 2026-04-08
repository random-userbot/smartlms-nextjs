'use client';

import React, { createContext, useContext, useEffect, useRef, ReactNode } from 'react';
import { usePathname } from 'next/navigation';
import { activityAPI } from '@/lib/api';
import { v4 as uuidv4 } from 'uuid';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface ActivityEvent {
  action: string;
  details?: Record<string, any>;
  timestamp: string;
  page: string;
}

interface ActivityContextType {
  trackEvent: (action: string, details?: Record<string, any>) => void;
  sessionId: string;
}

const ActivityContext = createContext<ActivityContextType | undefined>(undefined);

export function ActivityProvider({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const sessionId = useRef(uuidv4()).current;
  const eventBuffer = useRef<ActivityEvent[]>([]);
  const lastActive = useRef(Date.now());
  const isIdle = useRef(false);

  const trackEvent = (action: string, details?: Record<string, any>) => {
    const event: ActivityEvent = {
      action,
      details,
      timestamp: new Date().toISOString(),
      page: pathname,
    };
    eventBuffer.current.push(event);

    if (eventBuffer.current.length >= 30) {
      flushEvents();
    }
  };

  const flushEvents = async () => {
    if (eventBuffer.current.length === 0) return;
    const events = [...eventBuffer.current];
    eventBuffer.current = [];
    
    try {
      const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;
      if (!token) return; // Skip flush if unauthenticated
      
      await activityAPI.submitBatch({
        session_id: sessionId,
        events,
        session_duration: Math.floor((Date.now() - lastActive.current) / 1000),
      });
    } catch (error) {
      console.error('Failed to flush activity events:', error);
      // Re-add on failure (simple retry)
      eventBuffer.current = [...events, ...eventBuffer.current];
    }
  };

  useEffect(() => {
    // Initial page view
    trackEvent('page_view', { path: pathname });

    // Visibility (Anti-cheating)
    const handleVisibilityChange = () => {
      trackEvent(document.hidden ? 'tab_hidden' : 'tab_visible', {
        timestamp: Date.now(),
      });
    };

    // Idle Detection
    const handleUserActivity = () => {
      if (isIdle.current) {
        trackEvent('idle_end');
        isIdle.current = false;
      }
      lastActive.current = Date.now();
    };

    const idleInterval = setInterval(() => {
      const now = Date.now();
      if (now - lastActive.current > 60000 && !isIdle.current) { // 1 min idle
        trackEvent('idle_start');
        isIdle.current = true;
      }
    }, 10000);

    // Periodic Batch Flush
    const flushInterval = setInterval(flushEvents, 30000);

    document.addEventListener('visibilitychange', handleVisibilityChange);
    document.addEventListener('mousemove', handleUserActivity);
    document.addEventListener('keydown', handleUserActivity);

    const handleBeforeUnload = () => {
      const data = JSON.stringify({
        session_id: sessionId,
        duration: Math.floor((Date.now() - lastActive.current) / 1000),
        events: eventBuffer.current,
        page_views: [pathname],
      });
      navigator.sendBeacon(`${API_BASE_URL}/api/activity/session-end`, data);
    };

    window.addEventListener('beforeunload', handleBeforeUnload);

    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      document.removeEventListener('mousemove', handleUserActivity);
      document.removeEventListener('keydown', handleUserActivity);
      window.removeEventListener('beforeunload', handleBeforeUnload);
      clearInterval(idleInterval);
      clearInterval(flushInterval);
    };
  }, [pathname]);

  return (
    <ActivityContext.Provider value={{ trackEvent, sessionId }}>
      {children}
    </ActivityContext.Provider>
  );
}

export function useActivity() {
  const context = useContext(ActivityContext);
  if (context === undefined) {
    throw new Error('useActivity must be used within an ActivityProvider');
  }
  return context;
}
