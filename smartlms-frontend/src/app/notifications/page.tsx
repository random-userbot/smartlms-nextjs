'use client';

import React, { useState, useEffect } from 'react';
import { 
  Bell, 
  CheckCircle2, 
  Clock, 
  Trash2, 
  Megaphone, 
  BookOpen, 
  Award,
  AlertCircle
} from 'lucide-react';
import { notificationsAPI } from '@/lib/api';
import Sidebar from '@/components/Sidebar';

const TYPE_CONFIG: Record<string, any> = {
  announcement: { icon: Megaphone, color: 'text-blue-400', bg: 'bg-blue-400/10' },
  assignment: { icon: BookOpen, color: 'text-purple-400', bg: 'bg-purple-400/10' },
  grade: { icon: Award, color: 'text-green-400', bg: 'bg-green-400/10' },
  alert: { icon: AlertCircle, color: 'text-red-400', bg: 'bg-red-400/10' },
  default: { icon: Bell, color: 'text-primary', bg: 'bg-primary/10' },
};

export default function NotificationsPage() {
  const [notifications, setNotifications] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadNotifications();
  }, []);

  const loadNotifications = async () => {
    try {
      const res = await notificationsAPI.list();
      setNotifications(res.data);
    } catch (err) {
      console.error('Failed to load notifications', err);
    } finally {
      setLoading(false);
    }
  };

  const markRead = async (id: string) => {
    try {
      await notificationsAPI.markAsRead(id);
      setNotifications(prev => prev.map(n => n.id === id ? { ...n, is_read: true } : n));
    } catch (err) {
      console.error('Failed to mark as read', err);
    }
  };

  const markAllRead = async () => {
    try {
      await notificationsAPI.markAllRead();
      setNotifications(prev => prev.map(n => ({ ...n, is_read: true })));
    } catch (err) {
      console.error('Failed to mark all as read', err);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-screen bg-background">
        <Sidebar />
        <main className="flex-1 ml-64 p-8 flex items-center justify-center">
          <div className="w-12 h-12 border-4 border-primary/20 border-t-primary rounded-full animate-spin" />
        </main>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-background text-white selection:bg-primary/30">
      <Sidebar />
      
      <main className="flex-1 ml-64 p-8 md:p-12">
        <div className="max-w-4xl mx-auto">
          <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 mb-12">
            <div>
              <h1 className="text-4xl font-black tracking-tight mb-3">Notifications</h1>
              <p className="text-text-muted font-medium text-lg">Stay updated with course announcements and activity.</p>
            </div>
            <button 
              onClick={markAllRead}
              className="flex items-center gap-2 px-6 py-3 bg-white/5 hover:bg-white/10 rounded-2xl font-bold transition-all border border-white/5 text-sm"
            >
              <CheckCircle2 size={18} className="text-primary" /> Mark all as read
            </button>
          </div>

          {notifications.length === 0 ? (
            <div className="p-20 text-center glass-premium rounded-[2.5rem] border border-white/5">
              <div className="w-20 h-20 bg-white/5 rounded-3xl flex items-center justify-center mx-auto mb-6 border border-white/5 text-text-muted">
                <Bell size={40} />
              </div>
              <h3 className="text-2xl font-black text-white tracking-tight">All caught up!</h3>
              <p className="text-text-muted mt-2 font-medium">No new notifications at the moment.</p>
            </div>
          ) : (
            <div className="space-y-4">
              {notifications.map((notification) => {
                const config = TYPE_CONFIG[notification.type] || TYPE_CONFIG.default;
                const Icon = config.icon;
                
                return (
                  <div 
                    key={notification.id}
                    className={`group p-6 rounded-[2rem] transition-all border flex gap-6 items-start ${notification.is_read ? 'bg-surface/30 border-white/5 opacity-80' : 'bg-surface border-primary/20 shadow-lg shadow-primary/5'}`}
                  >
                    <div className={`w-14 h-14 rounded-2xl shrink-0 flex items-center justify-center ${config.bg} ${config.color} border border-current/10`}>
                      <Icon size={24} />
                    </div>
                    
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-4 mb-1">
                        <h4 className={`text-lg font-black tracking-tight ${notification.is_read ? 'text-white/70' : 'text-white'}`}>
                          {notification.title}
                        </h4>
                        <span className="text-[10px] font-black uppercase tracking-widest text-text-muted flex items-center gap-1.5 whitespace-nowrap">
                          <Clock size={12} /> {new Date(notification.created_at).toLocaleDateString()}
                        </span>
                      </div>
                      <p className="text-text-muted leading-relaxed font-medium">
                        {notification.message}
                      </p>
                      
                      {!notification.is_read && (
                        <button 
                          onClick={() => markRead(notification.id)}
                          className="mt-4 text-[10px] font-black uppercase tracking-widest text-primary hover:text-white transition-colors"
                        >
                          Mark as read
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
