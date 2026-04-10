'use client';

import React, { useState, useEffect, useRef } from 'react';
import { 
  MessageSquare, 
  Send, 
  ChevronLeft, 
  Search, 
  User, 
  Clock, 
  CheckCheck, 
  Check, 
  Plus, 
  X, 
  UserPlus,
  BookOpen,
  Sparkles,
  Trash2
} from 'lucide-react';
import { messagesAPI, coursesAPI } from '@/lib/api';
import { useAuth } from '@/context/AuthContext';
import Sidebar from '@/components/Sidebar';

const CATEGORY_COLORS: Record<string, any> = {
  advice: { bg: 'bg-blue-500/10', text: 'text-blue-400', border: 'border-blue-500/20', icon: BookOpen },
  encouragement: { bg: 'bg-green-500/10', text: 'text-green-400', border: 'border-green-500/20', icon: Sparkles },
  warning: { bg: 'bg-yellow-500/10', text: 'text-yellow-400', border: 'border-yellow-500/20', icon: MessageSquare },
  general: { bg: 'bg-white/5', text: 'text-text-muted', border: 'border-white/10', icon: MessageSquare },
};

import NavigationHeader from '@/components/NavigationHeader';

export default function MessagesPage() {
  const { user } = useAuth();
  const [conversations, setConversations] = useState<any[]>([]);
  const [selectedUser, setSelectedUser] = useState<any>(null);
  const [messages, setMessages] = useState<any[]>([]);
  const [newMessage, setNewMessage] = useState('');
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [showNewMessageModal, setShowNewMessageModal] = useState(false);
  const [availableStudents, setAvailableStudents] = useState<any[]>([]);
  const [studentSearchQuery, setStudentSearchQuery] = useState('');
  const [loadingStudents, setLoadingStudents] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    loadConversations();
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const loadConversations = async () => {
    try {
      const res = await messagesAPI.getConversations();
      setConversations(Array.isArray(res.data) ? res.data : []);
    } catch (err) {
      console.error('Failed to load conversations', err);
    } finally {
      setLoading(false);
    }
  };

  const selectConversation = async (otherUserId: string) => {
    try {
      const res = await messagesAPI.getMessagesWithUser(otherUserId);
      setMessages(res.data.messages);
      setSelectedUser(res.data.other_user);
      loadConversations(); // Refresh list to update unread counts
    } catch (err) {
      console.error('Failed to load messages', err);
    }
  };

  const handleSend = async () => {
    if (!newMessage.trim() || !selectedUser || sending) return;
    setSending(true);
    try {
      await messagesAPI.sendMessage({
        receiver_id: selectedUser.id,
        content: newMessage.trim(),
      });
      setNewMessage('');
      selectConversation(selectedUser.id);
    } catch (err) {
      console.error('Failed to send message', err);
    } finally {
      setSending(false);
    }
  };

  const loadAvailableStudents = async () => {
    setLoadingStudents(true);
    try {
      const coursesRes = await coursesAPI.getMyCourses();
      const courseIds = (coursesRes.data || []).map((c: any) => c.id);
      
      const studentsPromises = courseIds.map((id: string) => 
        coursesAPI.getStudents(id).catch(() => ({ data: [] }))
      );
      
      const studentsResults = await Promise.all(studentsPromises);
      const allStudents = studentsResults.flatMap(r => r.data || []);
      
      // Unique by student_id
      const uniqueStudentsMap = new Map();
      allStudents.forEach((s: any) => {
        if (!uniqueStudentsMap.has(s.student_id)) {
          uniqueStudentsMap.set(s.student_id, {
            id: s.student_id,
            full_name: s.full_name,
            email: s.email
          });
        }
      });
      
      setAvailableStudents(Array.from(uniqueStudentsMap.values()));
    } catch (err) {
      console.error('Failed to load students', err);
    } finally {
      setLoadingStudents(false);
    }
  };

  useEffect(() => {
    if (showNewMessageModal) {
      loadAvailableStudents();
    }
  }, [showNewMessageModal]);

  const handleDeleteConversation = async () => {
    if (!selectedUser || !confirm('Are you sure you want to delete this neural link? All cognitive data and message history will be purged.')) return;
    try {
      await messagesAPI.deleteConversation(selectedUser.id);
      setSelectedUser(null);
      loadConversations();
    } catch (err) {
      console.error('Failed to delete conversation', err);
    }
  };

  const handleDeleteMessage = async (messageId: string) => {
    if (!confirm('Purge this message fragment?')) return;
    try {
      await messagesAPI.deleteMessage(messageId);
      if (selectedUser) {
        selectConversation(selectedUser.id);
      }
    } catch (err) {
      console.error('Failed to delete message', err);
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
    <div className="flex h-screen bg-background text-foreground selection:bg-primary/30 overflow-hidden font-sans">
      <Sidebar />
      
      <main className="flex-1 ml-64 flex h-screen overflow-hidden animate-fade-in relative">
        {/* Conversations List */}
        <div className={`${selectedUser ? 'hidden md:flex' : 'flex'} flex-col w-full md:w-80 lg:w-96 border-r border-border bg-surface-alt/10`}>
          <div className="p-8 border-b border-border">
            <NavigationHeader 
              title="Messages"
              subtitle="Neural Links"
            />
            
            <div className="relative group -mt-4">
              <Search size={18} className="absolute left-4 top-1/2 -translate-y-1/2 text-text-muted group-focus-within:text-primary transition-colors" />
              <input
                type="text"
                placeholder="Search link..."
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                className="w-full pl-12 pr-4 py-3 bg-surface border border-border rounded-2xl focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none transition-all placeholder:text-text-muted text-foreground"
              />
            </div>
            <button
              onClick={() => setShowNewMessageModal(true)}
              className="w-full mt-4 flex items-center justify-center gap-2 py-3 bg-primary text-white hover:bg-primary-hover rounded-2xl font-black text-xs uppercase tracking-widest transition-all shadow-lg shadow-primary/20"
            >
              <Plus size={18} /> New Message
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-2 space-y-1">
            {(Array.isArray(conversations) ? conversations : []).filter(c => c.other_user_name?.toLowerCase().includes(searchQuery.toLowerCase())).map(conv => (
              <button
                key={conv.other_user_id}
                onClick={() => selectConversation(conv.other_user_id)}
                className={`w-full p-4 rounded-2xl transition-all flex items-start gap-3 hover:bg-surface-alt ${selectedUser?.id === conv.other_user_id ? 'bg-surface-alt border border-border shadow-sm' : 'border border-transparent'}`}
              >
                <div className="w-12 h-12 rounded-xl bg-surface-alt flex items-center justify-center font-black text-primary border border-primary/10 shrink-0">
                  {conv.other_user_name.charAt(0)}
                </div>
                <div className="flex-1 min-w-0 text-left">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-bold truncate">{conv.other_user_name}</span>
                    <span className="text-[10px] text-text-muted font-bold uppercase tracking-widest">
                      {new Date(conv.last_message_at).toLocaleDateString()}
                    </span>
                  </div>
                  <p className={`text-sm truncate mt-0.5 ${conv.unread_count > 0 ? 'text-foreground font-black' : 'text-text-muted'}`}>
                    {conv.last_message}
                  </p>
                </div>
                {conv.unread_count > 0 && (
                  <div className="w-5 h-5 bg-primary rounded-full flex items-center justify-center text-[10px] font-black shrink-0">
                    {conv.unread_count}
                  </div>
                )}
              </button>
            ))}
          </div>
        </div>

        {/* Chat Thread */}
        <div className={`${selectedUser ? 'flex' : 'hidden md:flex'} flex-1 flex-col bg-surface/50`}>
          {selectedUser ? (
            <>
              {/* Thread Header */}
              <div className="p-6 border-b border-white/5 flex items-center gap-4 bg-background/50 backdrop-blur-xl">
                <button 
                  onClick={() => setSelectedUser(null)} 
                  className="md:hidden p-2 hover:bg-white/5 rounded-xl border border-white/5"
                >
                  <ChevronLeft size={20} />
                </button>
                <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center text-primary font-black border border-primary/20">
                  {selectedUser.full_name?.charAt(0)}
                </div>
                <div className="flex-1">
                  <h2 className="font-bold text-lg">{selectedUser.full_name}</h2>
                  <span className="text-[10px] font-bold text-primary uppercase tracking-widest">{selectedUser.role}</span>
                </div>
                <button 
                  onClick={handleDeleteConversation}
                  className="p-2 text-text-muted hover:text-danger hover:bg-danger/10 rounded-xl border border-transparent hover:border-danger/20 transition-all"
                  title="Delete Conversation"
                >
                  <Trash2 size={18} />
                </button>
              </div>

              {/* Messages Flow */}
              <div className="flex-1 overflow-y-auto p-6 space-y-6">
                {(Array.isArray(messages) ? messages : []).map((msg, i) => {
                  const isMine = msg.sender_id === user?.id;
                  return (
                    <div key={msg.id} className={`flex flex-col group/msg ${isMine ? 'items-end' : 'items-start'}`}>
                      <div className="flex items-center gap-2 max-w-[80%]">
                        {isMine && (
                          <button 
                            onClick={() => handleDeleteMessage(msg.id)}
                            className="p-1.5 text-text-muted hover:text-danger opacity-0 group-hover/msg:opacity-100 transition-all hover:bg-danger/10 rounded-lg shrink-0"
                          >
                            <Trash2 size={12} />
                          </button>
                        )}
                        <div className={`px-5 py-3 rounded-2xl ${isMine ? 'bg-primary text-white rounded-tr-sm crimson-glow' : 'bg-surface-alt border border-white/5 rounded-tl-sm'}`}>
                          <p className="text-sm leading-relaxed">{msg.content}</p>
                        </div>
                        {!isMine && (
                          <button 
                            onClick={() => handleDeleteMessage(msg.id)}
                            className="p-1.5 text-text-muted hover:text-danger opacity-0 group-hover/msg:opacity-100 transition-all hover:bg-danger/10 rounded-lg shrink-0"
                          >
                            <Trash2 size={12} />
                          </button>
                        )}
                      </div>
                      <div className="flex items-center gap-1.5 mt-2 text-[10px] font-bold text-text-muted uppercase tracking-widest">
                        <Clock size={10} />
                        {new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        {isMine && (msg.is_read ? <CheckCheck size={12} className="text-primary" /> : <Check size={12} />)}
                      </div>
                    </div>
                  );
                })}
                <div ref={messagesEndRef} />
              </div>

              {/* Message Input */}
              <div className="p-6 border-t border-white/5 bg-background/50">
                <div className="flex items-center gap-3 max-w-4xl mx-auto">
                  <input
                    type="text"
                    value={newMessage}
                    onChange={e => setNewMessage(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && handleSend()}
                    placeholder="Type a message..."
                    className="flex-1 px-6 py-4 bg-surface border border-border rounded-2xl focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none transition-all placeholder:text-text-muted text-foreground"
                  />
                  <button
                    onClick={handleSend}
                    disabled={!newMessage.trim() || sending}
                    className="p-4 bg-primary text-white rounded-2xl hover:scale-105 active:scale-95 disabled:opacity-50 transition-all crimson-glow shadow-lg"
                  >
                    <Send size={20} />
                  </button>
                </div>
              </div>
            </>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center text-text-muted p-12">
              <div className="w-20 h-20 rounded-3xl bg-surface-alt flex items-center justify-center mb-6 border border-border">
                <MessageSquare size={40} />
              </div>
              <h3 className="text-2xl font-black text-foreground tracking-tight">Select a conversation</h3>
              <p className="text-sm mt-2 max-w-xs text-center leading-relaxed font-medium">Choose a chat from the sidebar or start a new one to communicate.</p>
            </div>
          )}
        </div>
      </main>

      {/* New Message Modal */}
      {showNewMessageModal && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-md z-[100] flex items-center justify-center p-4">
          <div className="bg-surface border border-white/10 w-full max-w-md rounded-[2.5rem] overflow-hidden shadow-2xl animate-in fade-in zoom-in slide-in-from-bottom-4 duration-300">
            <div className="p-8 border-b border-white/5 flex items-center justify-between bg-surface-alt/50">
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 rounded-2xl bg-primary/10 flex items-center justify-center text-primary border border-primary/20">
                  <UserPlus size={24} />
                </div>
                <div>
                  <h2 className="text-xl font-black tracking-tight">New Synthesis</h2>
                  <p className="text-[10px] font-bold text-text-muted uppercase tracking-widest mt-0.5">Initialize secure neural link</p>
                </div>
              </div>
              <button 
                onClick={() => setShowNewMessageModal(false)}
                className="p-3 hover:bg-white/5 rounded-2xl border border-white/5 text-text-muted hover:text-white transition-all"
              >
                <X size={20} />
              </button>
            </div>
            
            <div className="p-8 space-y-6">
              <div className="relative group">
                <Search size={18} className="absolute left-5 top-1/2 -translate-y-1/2 text-text-muted group-focus-within:text-primary transition-colors" />
                <input
                  type="text"
                  placeholder="Search student directory..."
                  value={studentSearchQuery}
                  onChange={e => setStudentSearchQuery(e.target.value)}
                  className="w-full pl-14 pr-6 py-4 bg-background border border-border rounded-2xl focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none transition-all placeholder:text-text-muted text-foreground font-medium"
                />
              </div>

              <div className="max-h-64 overflow-y-auto space-y-2 pr-2 scrollbar-thin scrollbar-thumb-white/10">
                {loadingStudents ? (
                  <div className="py-12 flex flex-col items-center gap-4 text-text-muted">
                    <div className="w-8 h-8 border-2 border-primary/20 border-t-primary rounded-full animate-spin" />
                    <span className="text-[10px] font-bold uppercase tracking-widest">Scanning Directory...</span>
                  </div>
                ) : availableStudents.filter(s => 
                    s.full_name?.toLowerCase().includes(studentSearchQuery.toLowerCase()) || 
                    s.email?.toLowerCase().includes(studentSearchQuery.toLowerCase())
                  ).length > 0 ? (
                  availableStudents.filter(s => 
                    s.full_name?.toLowerCase().includes(studentSearchQuery.toLowerCase()) || 
                    s.email?.toLowerCase().includes(studentSearchQuery.toLowerCase())
                  ).map(student => (
                    <button
                      key={student.id}
                      onClick={() => {
                        selectConversation(student.id);
                        setShowNewMessageModal(false);
                      }}
                      className="w-full flex items-center gap-4 p-4 rounded-3xl hover:bg-white/5 border border-transparent hover:border-white/5 transition-all group"
                    >
                      <div className="w-10 h-10 rounded-xl bg-surface-alt flex items-center justify-center text-primary font-black border border-primary/10 group-hover:border-primary/30 transition-colors uppercase">
                        {student.full_name?.charAt(0)}
                      </div>
                      <div className="text-left flex-1 min-w-0">
                        <div className="font-bold text-sm truncate">{student.full_name}</div>
                        <div className="text-[10px] font-bold text-text-muted truncate uppercase tracking-widest">{student.email}</div>
                      </div>
                      <Plus size={16} className="text-text-muted opacity-0 group-hover:opacity-100 transition-opacity" />
                    </button>
                  ))
                ) : (
                  <div className="py-12 text-center text-text-muted">
                    <div className="w-12 h-12 bg-white/5 rounded-2xl flex items-center justify-center mx-auto mb-4 border border-white/5">
                      <Search size={24} />
                    </div>
                    <p className="text-xs font-bold uppercase tracking-widest">No candidates found</p>
                    <p className="text-[10px] mt-1 opacity-50">Refine search parameters</p>
                  </div>
                )}
              </div>
            </div>
            
            <div className="p-8 bg-surface-alt/30 border-t border-white/5">
              <p className="text-[10px] font-bold text-text-muted uppercase tracking-[0.15em] text-center mb-0">
                Encrypted Peer-to-Peer Communication Protocol Active
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
