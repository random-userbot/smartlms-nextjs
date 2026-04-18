'use client';

import React, { useState, useEffect } from 'react';
import { BookOpen, Plus, Users, Play, X, Upload, ArrowUpRight, Trash2 } from 'lucide-react';
import Link from 'next/link';
import { coursesAPI, api } from '@/lib/api';
import { useAuth } from '@/context/AuthContext';
import Sidebar from '@/components/Sidebar';
import { uploadFile } from '@/lib/cloudinary';

export default function TeacherCoursesPage() {
  const { user } = useAuth();
  const [courses, setCourses] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showCookieModal, setShowCookieModal] = useState(false);
  const [youtubeCookie, setYoutubeCookie] = useState('');
  const [savingCookie, setSavingCookie] = useState(false);
  const [cookieStatus, setCookieStatus] = useState<'idle' | 'success' | 'error'>('idle');
  const [newCourse, setNewCourse] = useState({ 
    title: '', 
    description: '', 
    category: 'Technology', 
    thumbnail_url: '',
    playlist_url: '',
    sync_playlist: false
  });
  const [thumbnailFile, setThumbnailFile] = useState<File | null>(null);
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    loadCourses();
  }, []);

  const loadCourses = async () => {
    try {
      const res = await coursesAPI.list();
      setCourses(Array.isArray(res.data) ? res.data : []);
    } catch (err) {
      console.error('Failed to load courses', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSaveCookie = async () => {
    if (!youtubeCookie.trim()) return;
    setSavingCookie(true);
    setCookieStatus('idle');
    try {
      const response = await api.post('/api/admin/youtube/cookies', { 
        cookie_data: youtubeCookie 
      });
      
      setCookieStatus('success');
      setTimeout(() => {
        setCookieStatus('idle');
        setShowCookieModal(false);
        setYoutubeCookie('');
      }, 1500);
    } catch (error: any) {
      console.error(error?.response?.data || error);
      setCookieStatus('error');
    } finally {
      setSavingCookie(false);
    }
  };

  const handleCreateCourse = async () => {
    if (!newCourse.title || creating) return;
    setCreating(true);
    try {
      let thumbnailUrl = '';
      if (thumbnailFile) {
        thumbnailUrl = await uploadFile(thumbnailFile);
      }
      
      await coursesAPI.create({ 
        ...newCourse, 
        thumbnail_url: thumbnailUrl,
        playlist_url: newCourse.sync_playlist ? newCourse.playlist_url : undefined
      });
      setShowCreateModal(false);
      setNewCourse({ title: '', description: '', category: 'Technology', thumbnail_url: '', playlist_url: '', sync_playlist: false });
      setThumbnailFile(null);
      loadCourses();
    } catch (err) {
      console.error('Failed to create course', err);
    } finally {
      setCreating(false);
    }
  };
  
  const handleDeleteCourse = async (id: string) => {
    if (!confirm('This action will permanently IRRADIATE all pedagogical trances, student syncs, and cognitive records for this module. This cannot be undone. Proceed?')) return;
    try {
      await coursesAPI.delete(id);
      loadCourses();
    } catch (err) {
      console.error('Failed to purge module', err);
      alert('Failed to purge module.');
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
    <div className="flex min-h-screen bg-background text-foreground">
      <Sidebar />
      
      <main className="flex-1 ml-64 p-8 md:p-12">
        <div className="max-w-7xl mx-auto">
          {/* Header */}
          <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 mb-12">
            <div>
              <div className="text-[10px] uppercase tracking-[0.3em] font-black text-primary mb-2">Curriculum Engineer Console</div>
              <h1 className="text-5xl font-black tracking-tight">Course Management</h1>
              <p className="text-text-muted font-medium mt-4">Create, publish, and optimize your educational modules.</p>
            </div>
            <div className="flex items-center gap-4">
              <button 
                onClick={() => setShowCookieModal(true)}
                className="flex items-center gap-3 px-6 py-4 bg-orange-500/10 text-orange-400 border border-orange-500/20 rounded-2xl font-black transition-all hover:bg-orange-500/20 active:scale-95 shadow-lg text-sm"
              >
                <Play size={18} /> Fix YouTube Bot Sync
              </button>
              <button 
                onClick={() => setShowCreateModal(true)}
                className="flex items-center gap-3 px-8 py-4 bg-primary text-white rounded-2xl font-black transition-all crimson-glow hover:scale-[1.02] active:scale-95 shadow-lg"
              >
                <Plus size={20} /> Create New Module
              </button>
            </div>
          </div>

          {/* Filters & Stats */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12">
            <div className="glass-card p-6 border border-white/5 flex items-center gap-6">
              <div className="w-14 h-14 rounded-2xl bg-primary/10 flex items-center justify-center text-primary border border-primary/20">
                <BookOpen size={24} />
              </div>
              <div>
                <div className="text-3xl font-black text-foreground">{courses.length}</div>
                <div className="text-[10px] font-black text-text-muted uppercase tracking-widest">Active Modules</div>
              </div>
            </div>
            <div className="glass-card p-6 border border-white/5 flex items-center gap-6">
              <div className="w-14 h-14 rounded-2xl bg-success/10 flex items-center justify-center text-success border border-success/20">
                <Users size={24} />
              </div>
              <div>
                <div className="text-3xl font-black text-foreground">{courses.reduce((acc, c) => acc + (c.student_count || 0), 0)}</div>
                <div className="text-[10px] font-black text-text-muted uppercase tracking-widest">Total Students</div>
              </div>
            </div>
            <div className="glass-card p-6 border border-white/5 flex items-center gap-6">
              <div className="w-14 h-14 rounded-2xl bg-info/10 flex items-center justify-center text-info border border-info/20">
                <Play size={24} />
              </div>
              <div>
                <div className="text-3xl font-black text-foreground">{courses.reduce((acc, c) => acc + (c.lecture_count || 0), 0)}</div>
                <div className="text-[10px] font-black text-text-muted uppercase tracking-widest">Total Lectures</div>
              </div>
            </div>
          </div>

          {/* Courses Grid */}
          {courses.length === 0 ? (
            <div className="p-24 text-center glass-premium rounded-[3rem] border border-border bg-surface-alt">
              <BookOpen size={80} className="mx-auto mb-8 opacity-10 text-primary" />
              <h3 className="text-3xl font-black mb-4 tracking-tight text-foreground">Zero sequences deployed.</h3>
              <p className="text-text-muted text-lg font-medium mb-10">Initiate your pedagogical impact by creating your first module today.</p>
              <button 
                onClick={() => setShowCreateModal(true)}
                className="px-8 py-4 bg-primary/10 hover:bg-primary/20 border border-primary/20 rounded-2xl font-bold transition-all text-primary"
              >
                Launch Module Creator &rarr;
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
              {courses.map((course) => (
                <div key={course.id} className="group flex flex-col bg-surface border border-white/5 rounded-[2.5rem] overflow-hidden hover:border-primary/40 hover:shadow-2xl hover:shadow-primary/5 transition-all duration-500">
                  <div className="h-48 bg-surface-alt relative overflow-hidden flex items-center justify-center">
                    {course.thumbnail_url ? (
                      <img src={course.thumbnail_url} alt={course.title} className="w-full h-full object-cover opacity-60 group-hover:opacity-100 group-hover:scale-110 transition-all duration-700" />
                    ) : (
                      <div className="text-primary/20"><BookOpen size={64} /></div>
                    )}
                    <div className="absolute inset-0 bg-gradient-to-t from-surface to-transparent opacity-60"></div>
                    <div className="absolute top-6 right-6 px-3 py-1 bg-black/40 backdrop-blur-md rounded-full text-[10px] font-black uppercase tracking-widest text-white border border-white/10">
                      {course.category}
                    </div>
                  </div>
                  
                  <div className="p-8 flex-1 flex flex-col">
                    <div className="flex items-center justify-between gap-4 mb-2">
                       <h3 className="text-2xl font-black line-clamp-1 group-hover:text-primary transition-colors text-foreground">{course.title}</h3>
                       <button 
                         onClick={(e) => {
                           e.preventDefault();
                           e.stopPropagation();
                           handleDeleteCourse(course.id);
                         }}
                         className="p-2 text-text-muted hover:text-danger hover:bg-danger/10 rounded-xl transition-all opacity-0 group-hover:opacity-100"
                       >
                         <Trash2 size={18} />
                       </button>
                    </div>
                    <p className="text-sm text-text-muted line-clamp-2 leading-relaxed mb-8 font-medium">
                      {course.description || 'No description provided for this module.'}
                    </p>
                    
                    <div className="grid grid-cols-2 gap-4 mb-4">
                      <div className="flex items-center gap-2.5 text-xs font-bold text-text-muted uppercase tracking-widest">
                        <Users size={16} className="text-primary" /> {course.student_count || 0} Students
                      </div>
                      <div className="flex items-center gap-2.5 text-xs font-bold text-text-muted uppercase tracking-widest">
                        <Play size={16} className="text-primary" /> {course.lecture_count || 0} Lectures
                      </div>
                    </div>

                    <button 
                      onClick={() => setShowCookieModal(true)} 
                      className="mb-8 text-[10px] w-max font-black uppercase tracking-widest text-orange-400 bg-orange-500/10 border border-orange-500/20 px-3 py-1.5 rounded-lg hover:bg-orange-500/20 transition-all flex items-center gap-2"
                    >
                      <Play size={12}/> Fix YouTube Sync
                    </button>
                    
                    <div className="mt-auto pt-6 border-t border-border flex items-center justify-between">
                      <Link 
                        href={`/teacher/courses/${course.id}`}
                        className="text-xs font-black uppercase tracking-widest text-primary hover:text-primary-glow transition-colors flex items-center gap-2"
                      >
                        Manage Module <ArrowUpRight size={14} />
                      </Link>
                      <div className={`px-4 py-1.5 rounded-full text-[10px] font-black uppercase tracking-widest border ${course.is_published ? 'bg-success/10 text-success border-success/20' : 'bg-warning/10 text-warning border-warning/20'}`}>
                        {course.is_published ? 'Published' : 'Draft'}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>

      {/* YouTube Cookie Modal */}
      {showCookieModal && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-xl z-[150] flex items-center justify-center p-4">
          <div className="bg-surface border border-white/10 w-full max-w-2xl rounded-[3rem] overflow-hidden shadow-2xl animate-in fade-in zoom-in slide-in-from-bottom-8 duration-500 max-h-[90vh] overflow-y-auto">
            <div className="p-10 border-b border-border flex items-center justify-between bg-orange-500/5">
              <div className="flex items-center gap-4">
                <div className="w-14 h-14 rounded-2xl bg-orange-500/10 flex items-center justify-center text-orange-400 border border-orange-500/20">
                  <Play size={24} className="animate-pulse" />
                </div>
                <div>
                  <h2 className="text-3xl font-black text-foreground uppercase tracking-tight">YouTube Bot Protection</h2>
                  <p className="text-[11px] font-bold text-orange-400/80 uppercase tracking-widest mt-1.5">Manual Fargate Bypass</p>
                </div>
              </div>
              <button 
                onClick={() => setShowCookieModal(false)}
                className="w-12 h-12 flex items-center justify-center rounded-2xl hover:bg-white/5 transition-all text-text-muted hover:text-white border border-transparent hover:border-white/10"
              >
                <X size={20} />
              </button>
            </div>
            
            <div className="p-10 text-sm space-y-6 text-foreground/80 leading-relaxed font-medium">
              <p>YouTube actively blocks our LMS cloud IPs (AWS Fargate) to prevent bot scraping. To fix this, you must authorize a &quot;burner&quot; YouTube session.</p>
              
              <div className="bg-surface-alt rounded-3xl p-6 border border-white/10">
                <h3 className="text-sm font-black text-white mb-4 uppercase tracking-widest flex items-center gap-2">
                  <span className="w-6 h-6 rounded-full bg-primary/20 text-primary flex items-center justify-center text-[10px]">1</span>
                  Create a Burner Session
                </h3>
                <ol className="list-decimal pl-5 space-y-2 marker:text-primary font-bold text-[13px]">
                  <li>Open Google Chrome Incognito mode.</li>
                  <li>Go to YouTube and log into a <b>burner/dummy Google account</b>.</li>
                  <li>Install a Chrome Extension like <a href="https://chrome.google.com/webstore/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpocidlghpihk" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline"><code>Get cookies.txt LOCALLY</code></a>.</li>
                  <li>Click the extension while on YouTube and export the <code>Netscape</code> formatted cookies.</li>
                </ol>
              </div>

              <div className="bg-surface-alt rounded-3xl p-6 border border-white/10">
                <h3 className="text-sm font-black text-white mb-4 uppercase tracking-widest flex items-center gap-2">
                  <span className="w-6 h-6 rounded-full bg-primary/20 text-primary flex items-center justify-center text-[10px]">2</span>
                  Format & Apply in Production
                </h3>
                 <p className="mb-4">Paste the exported JSON text array or Netscape string below to dynamically update the backend:</p>
                
                 <textarea
                  value={youtubeCookie}
                  onChange={(e) => setYoutubeCookie(e.target.value)}
                  placeholder='Paste JSON or Netscape string here...'
                  className="w-full h-32 bg-black/40 border border-white/5 rounded-xl font-mono text-[10px] text-green-400 p-4 focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none transition-all placeholder:text-gray-600 resize-none whitespace-pre"
                />

                <p className="mt-4 text-[11px] uppercase tracking-widest font-black text-orange-400">Warning: Do not use your personal YouTube account. It will get banned for scraping.</p>
              </div>
            </div>

            <div className="p-8 border-t border-border bg-surface-alt flex justify-end gap-3">
              <button 
                onClick={() => setShowCookieModal(false)}
                className="px-8 py-4 rounded-2xl bg-white/5 hover:bg-white/10 transition-all font-black text-xs uppercase tracking-widest text-text-muted hover:text-white"
              >
                Cancel
              </button>
              <button 
                onClick={handleSaveCookie}
                disabled={!youtubeCookie.trim() || savingCookie}
                className="px-8 py-4 rounded-2xl bg-primary text-white font-black text-xs uppercase tracking-widest disabled:opacity-40 disabled:scale-100 hover:scale-[1.02] active:scale-95 transition-all shadow-lg crimson-glow"
              >
                {savingCookie ? 'Checking...' : cookieStatus === 'success' ? 'Success ✓' : cookieStatus === 'error' ? 'Invalid Format' : 'Inject Cookie'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Create Course Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-xl z-[100] flex items-center justify-center p-4">
          <div className="bg-surface border border-white/10 w-full max-w-2xl rounded-[3rem] overflow-hidden shadow-2xl animate-in fade-in zoom-in slide-in-from-bottom-8 duration-500">
            <div className="p-10 border-b border-border flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="w-14 h-14 rounded-2xl bg-primary/10 flex items-center justify-center text-primary border border-primary/20">
                  <BookOpen size={28} />
                </div>
                <div>
                  <h2 className="text-3xl font-black tracking-tight text-foreground">Initiate Module</h2>
                  <p className="text-[10px] font-black text-primary uppercase tracking-[0.2em] mt-1">Configuring new curricular sequence</p>
                </div>
              </div>
              <button 
                onClick={() => setShowCreateModal(false)}
                className="p-3 hover:bg-surface-alt rounded-2xl border border-border text-text-muted hover:text-foreground transition-all"
              >
                <X size={24} />
              </button>
            </div>
            
            <div className="p-10 space-y-8 overflow-y-auto max-h-[60vh]">
              <div className="space-y-4">
                <label className="text-[10px] font-black uppercase tracking-[0.2em] text-text-muted ml-1">Module Identity</label>
                <input
                  type="text"
                  value={newCourse.title}
                  onChange={e => setNewCourse({ ...newCourse, title: e.target.value })}
                  placeholder="e.g. Advanced Quantum Computing"
                  className="w-full px-8 py-5 bg-white/5 border border-white/10 rounded-3xl focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none transition-all placeholder:text-text-muted font-bold text-lg"
                />
              </div>

              <div className="grid grid-cols-2 gap-6">
                <div className="space-y-4">
                  <label className="text-[10px] font-black uppercase tracking-[0.2em] text-text-muted ml-1">Category Domain</label>
                  <select 
                    value={newCourse.category}
                    onChange={e => setNewCourse({ ...newCourse, category: e.target.value })}
                    className="w-full px-6 py-5 bg-white/5 border border-white/10 rounded-3xl focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none transition-all font-bold"
                  >
                    <option>Technology</option>
                    <option>Design</option>
                    <option>Business</option>
                    <option>Science</option>
                  </select>
                </div>
                <div className="space-y-4">
                  <label className="text-[10px] font-black uppercase tracking-[0.2em] text-text-muted ml-1">Thumbnail</label>
                  <div className="relative">
                    <input type="file" id="thumb" className="hidden" onChange={e => e.target.files && setThumbnailFile(e.target.files[0])} />
                    <label htmlFor="thumb" className="flex items-center gap-3 w-full px-6 py-5 bg-white/5 border border-white/10 rounded-3xl cursor-pointer hover:bg-white/10 transition-all font-bold text-sm">
                      <Upload size={18} className="text-primary" /> {thumbnailFile ? thumbnailFile.name : 'Choose Image'}
                    </label>
                  </div>
                </div>
              </div>

              {/* YouTube Playlist Sync */}
              <div className="space-y-4 p-8 bg-primary/5 border border-primary/20 rounded-[2.5rem]">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <Play size={20} className="text-primary" />
                    <div>
                      <h4 className="text-sm font-black uppercase tracking-widest">YouTube Playlist Sync</h4>
                      <p className="text-[10px] text-text-muted font-bold mt-0.5">Bulk-deploy all videos as lectures</p>
                    </div>
                  </div>
                  <button 
                    onClick={() => setNewCourse({ ...newCourse, sync_playlist: !newCourse.sync_playlist })}
                    className={`w-14 h-8 rounded-full transition-all relative ${newCourse.sync_playlist ? 'bg-primary' : 'bg-surface-alt border border-border'}`}
                  >
                    <div className={`absolute top-1 w-6 h-6 rounded-full bg-white transition-all ${newCourse.sync_playlist ? 'left-7' : 'left-1'}`} />
                  </button>
                </div>

                {newCourse.sync_playlist && (
                  <div className="pt-4 animate-in fade-in slide-in-from-top-2 duration-300 space-y-3">
                    <input
                      type="text"
                      value={newCourse.playlist_url}
                      onChange={e => setNewCourse({ ...newCourse, playlist_url: e.target.value })}
                      placeholder="https://www.youtube.com/playlist?list=..."
                      className="w-full px-6 py-4 bg-black/20 border border-white/10 rounded-2xl focus:border-primary outline-none transition-all font-bold text-sm"
                    />
                    <button 
                      type="button"
                      onClick={() => setShowCookieModal(true)}
                      className="w-full py-3 px-4 rounded-xl bg-orange-500/10 border border-orange-500/20 text-orange-400 font-bold text-[10px] uppercase tracking-widest hover:bg-orange-500/20 transition-all text-left flex justify-between items-center"
                    >
                      <span>Fix Bot Protection (Auth Required)</span>
                      <ArrowUpRight size={14} />
                    </button>
                  </div>
                )}
              </div>

              <div className="space-y-4">
                <label className="text-[10px] font-black uppercase tracking-[0.2em] text-text-muted ml-1">Module Thesis</label>
                <textarea
                  value={newCourse.description}
                  onChange={e => setNewCourse({ ...newCourse, description: e.target.value })}
                  placeholder="Summarize the learning outcomes and curricular depth..."
                  className="w-full px-8 py-5 bg-white/5 border border-white/10 rounded-3xl focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none transition-all h-40 resize-none placeholder:text-text-muted font-medium"
                />
              </div>
            </div>

            <div className="p-10 border-t border-white/5">
              <button 
                onClick={handleCreateCourse}
                disabled={!newCourse.title || creating}
                className="w-full py-6 bg-primary text-white font-black rounded-3xl transition-all crimson-glow disabled:opacity-40 disabled:scale-100 hover:scale-[1.02] active:scale-95 shadow-lg text-lg"
              >
                {creating ? 'Syncing with Global Database...' : 'Finalize Module Creation'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

