'use client';

import React, { useState } from 'react';
import { MessageSquare, X, Send, User } from 'lucide-react';
import { messagesAPI } from '@/lib/api';

interface CommunicationFabProps {
  recipientId?: string;
  recipientName?: string;
}

export default function CommunicationFab({ recipientId, recipientName }: CommunicationFabProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!recipientId || !message.trim()) return;

    setLoading(true);
    try {
      await messagesAPI.sendMessage({
        receiver_id: recipientId,
        content: message.trim()
      });
      setSent(true);
      setMessage('');
      setTimeout(() => {
        setSent(false);
        setIsOpen(false);
      }, 2000);
    } catch (error) {
      console.error('Failed to send message:', error);
    } finally {
      setLoading(false);
    }
  };

  if (!recipientId) return null; // Only show if we have a recipient (e.g. on student detail or selected student)

  return (
    <div className="fixed bottom-8 right-8 z-[100] animate-bounce-in">
      {isOpen ? (
        <div className="bg-surface border border-border rounded-3xl shadow-2xl w-80 overflow-hidden crimson-glow animate-slide-up">
          <div className="p-6 bg-primary text-white flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 bg-white/20 rounded-lg flex items-center justify-center">
                <User size={16} />
              </div>
              <div>
                <div className="text-xs font-black uppercase tracking-widest opacity-80">Message To</div>
                <div className="text-sm font-bold truncate max-w-[150px]">{recipientName || 'Student'}</div>
              </div>
            </div>
            <button 
              onClick={() => setIsOpen(false)}
              className="p-2 hover:bg-white/10 rounded-xl transition-colors"
            >
              <X size={20} />
            </button>
          </div>

          <form onSubmit={handleSend} className="p-6 space-y-4 font-bold">
            {sent ? (
              <div className="py-8 text-center space-y-2">
                <div className="w-12 h-12 bg-success/20 text-success rounded-full flex items-center justify-center mx-auto animate-pulse">
                  <Send size={24} />
                </div>
                <div className="text-sm text-foreground">Message Sent!</div>
              </div>
            ) : (
              <>
                <textarea
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  placeholder="Type your message here..."
                  className="w-full h-32 bg-surface-alt border border-border rounded-2xl p-4 text-sm focus:border-primary outline-none transition-all resize-none"
                  disabled={loading}
                />
                <button
                  type="submit"
                  disabled={loading || !message.trim()}
                  className="w-full py-4 bg-primary text-white rounded-2xl flex items-center justify-center gap-3 hover:crimson-glow disabled:opacity-50 transition-all font-black text-xs uppercase tracking-widest"
                >
                  {loading ? (
                    <div className="w-4 h-4 border-2 border-white/20 border-t-white rounded-full animate-spin"></div>
                  ) : (
                    <>
                      Send Message
                      <Send size={16} />
                    </>
                  )}
                </button>
              </>
            )}
          </form>
        </div>
      ) : (
        <button
          onClick={() => setIsOpen(true)}
          className="w-16 h-16 bg-primary text-white rounded-full flex items-center justify-center shadow-xl hover:scale-110 active:scale-95 transition-all crimson-glow relative group"
        >
          <MessageSquare size={28} />
          <div className="absolute right-full mr-4 px-4 py-2 bg-foreground text-background rounded-xl text-[10px] font-black uppercase tracking-widest opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none">
            Message {recipientName || 'Student'}
          </div>
        </button>
      )}
    </div>
  );
}
