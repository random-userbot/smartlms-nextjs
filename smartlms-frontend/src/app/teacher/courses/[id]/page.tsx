'use client';

import React, { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { 
  ArrowLeft, 
  Plus, 
  Play, 
  Trash2, 
  MonitorPlay, 
  Upload, 
  Settings, 
  ChevronRight,
  FileText,
  Clock,
  Sparkles,
  Bot,
  X,
  Zap,
  Activity,
  Users,
  Filter,
  Search,
  Eye,
  MessageSquare,
  ArrowUpRight,
  ChevronDown,
  LayoutGrid,
  List as ListIcon
} from 'lucide-react';
import { coursesAPI, lecturesAPI, quizzesAPI, analyticsAPI, teacherAPI, messagesAPI } from '@/lib/api';
import Sidebar from '@/components/Sidebar';
import CommunicationFab from '@/components/CommunicationFab';

export default function TeacherCourseDetailPage() {
  const { id: courseId } = useParams() as { id: string };
  const router = useRouter();
  const [course, setCourse] = useState<any>(null);
  const [lectures, setLectures] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAddModal, setShowAddModal] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);

  const [newLecture, setNewLecture] = useState({
    title: '',
    description: '',
    youtube_url: '',
    type: 'youtube' as 'youtube' | 'upload'
  });
  const [videoFile, setVideoFile] = useState<File | null>(null);
  
  const [activeTab, setActiveTab] = useState<'curriculum' | 'students' | 'resources' | 'settings'>('curriculum');
  const [students, setStudents] = useState<any[]>([]);
  const [materials, setMaterials] = useState<any[]>([]);
  const [lectureEngagement, setLectureEngagement] = useState<Record<string, any>>({});
  
  // Drill-down & Modal State
  const [selectedLectureId, setSelectedLectureId] = useState<string | null>(null);
  const [studentFilter, setStudentFilter] = useState<'all' | 'watchers'>('all');
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [searchQuery, setSearchQuery] = useState('');

  // New Modals
  const [showSyncModal, setShowSyncModal] = useState(false);
  const [showResourceModal, setShowResourceModal] = useState(false);
  const [showEnrollModal, setShowEnrollModal] = useState(false);
  
  const [syncUrl, setSyncUrl] = useState('');
  const [resourceForm, setResourceForm] = useState({ title: '', path: '', type: 'pdf' });
  const [resourceFile, setResourceFile] = useState<File | null>(null);
  const [enrollEmail, setEnrollEmail] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);

  useEffect(() => {
    loadData();
  }, [courseId]);

  const loadData = async () => {
    try {
      const [cRes, lRes, sRes, mRes, eRes] = await Promise.all([
        coursesAPI.get(courseId),
        lecturesAPI.getByCourse(courseId),
        coursesAPI.getStudents(courseId),
        lecturesAPI.getCourseMaterials(courseId),
        analyticsAPI.getLecturesEngagement(courseId)
      ]);
      setCourse(cRes.data || null);
      setLectures(lRes.data || []);
      setStudents(sRes.data || []);
      setMaterials(mRes.data || []);
      setLectureEngagement(eRes.data || {});
    } catch (err) {
      console.error('Failed to load course details', err);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteLecture = async (lid: string) => {
    if (!confirm('Permanent deletion of this node will disrupt student sync traces. Proceed?')) return;
    try {
      await lecturesAPI.delete(lid);
      loadData();
    } catch (err) {
      console.error('Failed to delete lecture', err);
    }
  };

  const handleSyncYoutube = async () => {
    if (!syncUrl) return;
    setIsProcessing(true);
    try {
      await coursesAPI.importYoutube(courseId, syncUrl);
      setShowSyncModal(false);
      setSyncUrl('');
      loadData();
    } catch (err) {
      console.error('Sync failed', err);
      alert('Node synchronization failed. Please verify the URL.');
    } finally {
      setIsProcessing(false);
    }
  };

  const handleAddMaterial = async () => {
    if (!resourceForm.title || (!resourceForm.path && !resourceFile)) return;
    setIsProcessing(true);
    try {
      if (resourceFile) {
        await lecturesAPI.uploadMaterial(courseId, resourceForm.title, resourceForm.type, resourceFile);
      } else {
        await lecturesAPI.addMaterial(courseId, resourceForm.title, resourceForm.path, resourceForm.type);
      }
      setShowResourceModal(false);
      setResourceForm({ title: '', path: '', type: 'pdf' });
      setResourceFile(null);
      loadData();
    } catch (err) {
      console.error('Material addition failed', err);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleEnrollStudent = async () => {
    if (!enrollEmail) return;
    setIsProcessing(true);
    try {
      await teacherAPI.enrollStudent(courseId, enrollEmail);
      setShowEnrollModal(false);
      setEnrollEmail('');
      loadData();
    } catch (err: any) {
      console.error('Enrollment failed', err);
      const msg = err.response?.data?.detail || 'Failed to synchronize student enrollment. Ensure the email is correct and the user exists as a student.';
      alert(`Synchronicity Error: ${msg}`);
    } finally {
      setIsProcessing(false);
    }
  };

  const copyEnrollmentLink = () => {
    const link = `${window.location.origin}/courses/${courseId}`;
    navigator.clipboard.writeText(link);
    // Success feedback (would ideally be a toast, but keeping alert for now or adding a local state)
    alert('Semantic enrollment link captured to neural clipboard!');
  };

  const togglePublishStatus = async () => {
    if (!course) return;
    try {
      await coursesAPI.update(courseId, { is_published: !course.is_published });
      loadData();
    } catch (err) {
      console.error('Status shift failed', err);
    }
  };

  const handleDeleteMaterial = async (mid: string) => {
    if (!confirm('Purge this resource?')) return;
    try {
      await lecturesAPI.deleteMaterial(mid);
      loadData();
    } catch (err) {
      console.error('Deletion failed', err);
    }
  };

  const handleAddLecture = async () => {
    if (!newLecture.title || isUploading) return;
    setIsUploading(true);
    setUploadProgress(10);

    try {
      const lRes = await lecturesAPI.create({
        course_id: courseId,
        title: newLecture.title,
        description: newLecture.description,
        youtube_url: newLecture.type === 'youtube' ? newLecture.youtube_url : null
      });

      const lectureId = lRes.data.id;

      if (newLecture.type === 'upload' && videoFile) {
        setUploadProgress(30);
        await lecturesAPI.uploadVideo(lectureId, videoFile);
      }

      setUploadProgress(100);
      setShowAddModal(false);
      setNewLecture({ title: '', description: '', youtube_url: '', type: 'youtube' });
      setVideoFile(null);
      loadData();
    } catch (err) {
      console.error('Failed to add lecture', err);
      alert('Node deployment failed.');
    } finally {
      setIsUploading(false);
      setUploadProgress(0);
    }
  };

  const filteredStudents = (students || []).filter(s => {
    if (!s) return false;
    const matchesSearch = (s.full_name || '').toLowerCase().includes(searchQuery.toLowerCase()) || 
                          (s.email || '').toLowerCase().includes(searchQuery.toLowerCase());
    
    if (studentFilter === 'watchers' && selectedLectureId) {
      const lectureIndex = lectures.findIndex(l => l.id === selectedLectureId);
      const totalLectures = lectures.length;
      if (totalLectures === 0) return matchesSearch;
      const progressThreshold = (lectureIndex + 1) / totalLectures;
      return matchesSearch && (s.progress || 0) >= progressThreshold;
    }
    return matchesSearch;
  });

  if (loading) {
    return (
      <div className="flex min-h-screen bg-background">
        <Sidebar aria-hidden="true" />
        <main className="flex-1 ml-64 p-8 flex items-center justify-center">
          <div className="w-12 h-12 border-4 border-primary/20 border-t-primary rounded-full animate-spin" />
        </main>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <Sidebar />
      <main className="flex-1 ml-64 p-8 md:p-12 overflow-y-auto pb-32 relative">
        <div className="max-w-7xl mx-auto space-y-12">
          
          {/* Hero Header */}
          <header className="flex flex-col md:flex-row md:items-end justify-between gap-8 animate-fade-in">
             <div className="space-y-4">
                <div className="flex items-center gap-3">
                   <div className="px-3 py-1 bg-primary text-white rounded-full text-[10px] font-black uppercase tracking-widest shadow-lg shadow-primary/20">
                      {course?.category || 'Module'}
                   </div>
                   <div className="text-[10px] font-black text-text-muted uppercase tracking-[0.3em]">
                      {lectures.length} Semantic Nodes Active
                   </div>
                </div>
                <h1 className="text-7xl font-black tracking-tighter leading-none">{course?.title}</h1>
                <p className="text-text-muted font-bold text-lg max-w-2xl leading-relaxed">
                   {course?.description || 'Pedagogical flow management for the current curriculum branch.'}
                </p>
             </div>
             
              <div className="flex gap-4">
                <button 
                   onClick={() => router.back()}
                   className="p-5 bg-surface-alt border border-border rounded-full hover:bg-surface transition-all flex items-center justify-center text-text-muted hover:text-foreground shadow-lg"
                   title="Backward"
                >
                   <ArrowLeft size={20} />
                </button>
                <button 
                   onClick={togglePublishStatus}
                   className={`px-8 py-5 border rounded-[2.5rem] font-black text-xs uppercase tracking-widest transition-all flex items-center gap-3 shadow-lg ${course?.is_published ? 'bg-success/10 text-success border-success/20 hover:bg-success hover:text-white' : 'bg-warning/10 text-warning border-warning/20 hover:bg-warning hover:text-white'}`}
                >
                   {course?.is_published ? <Zap size={18} /> : <Clock size={18} />}
                   {course?.is_published ? 'Live Node' : 'Draft Mode'}
                </button>
                <button 
                   onClick={() => setShowSyncModal(true)}
                   className="px-8 py-5 bg-surface-alt border border-border rounded-[2.5rem] font-black text-xs uppercase tracking-widest hover:bg-surface transition-all flex items-center gap-3 shadow-lg"
                >
                   <Activity size={18} className="text-primary" /> Multi-Node Sync
                </button>
                <button 
                   onClick={() => setShowAddModal(true)}
                   className="px-10 py-5 bg-primary text-white rounded-[2.5rem] font-black text-xs uppercase tracking-widest crimson-glow hover:scale-105 transition-all flex items-center gap-3 shadow-xl"
                >
                   <Plus size={20} /> Add Lecture
                </button>
              </div>
          </header>

          {/* Navigation Matrix */}
           <nav className="flex gap-10 border-b border-border pb-1">
             {[
               { id: 'curriculum', label: 'Curriculum', icon: <Play size={16} /> },
               { id: 'students', label: 'Student Matrix', icon: <Users size={16} /> },
               { id: 'resources', label: 'Repository', icon: <FileText size={16} /> },
               { id: 'settings', label: 'Course Core', icon: <Settings size={16} /> }
             ].map(tab => (
               <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id as any)}
                  className={`flex items-center gap-3 py-6 border-b-[3px] transition-all font-black text-xs uppercase tracking-[0.2em] relative ${activeTab === tab.id ? 'border-primary text-foreground' : 'border-transparent text-text-muted hover:text-foreground'}`}
               >
                  {tab.icon} {tab.label}
                  {activeTab === tab.id && <div className="absolute inset-0 bg-primary/5 rounded-t-2xl -z-10 animate-fade-in" />}
               </button>
             ))}
          </nav>

          {/* Tab Content Panels */}
          <div className="animate-slide-up">
             {activeTab === 'curriculum' && (
                <div className="space-y-8">
                   <div className="flex items-center justify-between">
                      <div className="text-[10px] font-black text-text-muted uppercase tracking-[0.4em]">Pedagogical Node Management Table</div>
                      <button className="text-[10px] font-black text-primary uppercase tracking-widest hover:underline">Reorder Sequence</button>
                   </div>
                   
                   <div className="glass-card overflow-hidden">
                      <table className="w-full text-left border-collapse">
                         <thead className="bg-surface-alt border-b border-border text-[10px] font-black uppercase tracking-widest text-text-muted">
                            <tr>
                               <th className="p-8">Seq</th>
                               <th className="p-8">Lecture Architecture</th>
                               <th className="p-8">Engagement Profile</th>
                               <th className="p-8 text-right">Actions</th>
                            </tr>
                         </thead>
                         <tbody className="divide-y divide-border font-bold">
                            {lectures.map((lecture, idx) => (
                               <tr 
                                  key={lecture.id}
                                  onClick={() => {
                                     setSelectedLectureId(lecture.id);
                                     setStudentFilter('watchers');
                                     setActiveTab('students');
                                  }}
                                  className={`group cursor-pointer hover:bg-primary/5 transition-all ${selectedLectureId === lecture.id ? 'bg-primary/10' : ''}`}
                               >
                                  <td className="p-8">
                                     <div className="w-12 h-12 bg-background border border-border rounded-2xl flex items-center justify-center font-black text-sm text-primary group-hover:bg-primary group-hover:text-white transition-all shadow-sm">
                                        {(idx + 1).toString().padStart(2, '0')}
                                     </div>
                                  </td>
                                  <td className="p-8">
                                     <div className="space-y-1">
                                        <div className="text-lg font-black group-hover:text-primary transition-colors">{lecture.title}</div>
                                        <div className="flex items-center gap-3 text-[10px] text-text-muted uppercase tracking-widest font-black">
                                           {lecture.youtube_url ? <MonitorPlay size={12} /> : <Upload size={12} />}
                                           {lecture.youtube_url ? 'YouTube Linked' : 'Direct Upload'}
                                        </div>
                                     </div>
                                  </td>
                                  <td className="p-8">
                                     <div className="flex items-center gap-6">
                                        <div className="space-y-1">
                                           <div className="text-xs font-black">
                                              {lectureEngagement[lecture.id]?.avg_engagement || 0}% Engagement
                                           </div>
                                           <div className="w-24 h-1 bg-surface-alt rounded-full overflow-hidden border border-border">
                                              <div 
                                                className={`h-full rounded-full ${ (lectureEngagement[lecture.id]?.avg_engagement || 0) > 70 ? 'bg-success' : (lectureEngagement[lecture.id]?.avg_engagement || 0) > 40 ? 'bg-warning' : 'bg-danger' }`} 
                                                style={{ width: `${lectureEngagement[lecture.id]?.avg_engagement || 0}%` }} 
                                              />
                                           </div>
                                        </div>
                                        <div className="text-[10px] font-black text-text-muted uppercase tracking-widest bg-surface-alt px-2 py-1 rounded">
                                           {lectureEngagement[lecture.id]?.session_count || 0} Sessions
                                        </div>
                                     </div>
                                  </td>
                                  <td className="p-8 text-right">
                                     <div className="flex items-center justify-end gap-3 opacity-0 group-hover:opacity-100 transition-opacity">
                                         <button 
                                            onClick={(e) => { e.stopPropagation(); router.push(`/teacher/quizzes?lecture_id=${lecture.id}&course_id=${courseId}`); }}
                                            className="p-3 bg-surface-alt hover:bg-primary/20 text-primary rounded-xl border border-border transition-all flex items-center justify-center"
                                            title="AI Quiz Synthesis"
                                         >
                                            <Sparkles size={18} />
                                         </button>
                                        <button 
                                           onClick={(e) => { e.stopPropagation(); router.push(`/lectures/${lecture.id}`); }}
                                           className="p-3 bg-surface-alt hover:bg-primary/10 text-text-muted hover:text-primary rounded-xl border border-border transition-all"
                                        >
                                           <Eye size={18} />
                                        </button>
                                        <button 
                                           onClick={(e) => { e.stopPropagation(); handleDeleteLecture(lecture.id); }}
                                           className="p-3 bg-surface-alt hover:bg-danger/10 text-text-muted hover:text-danger rounded-xl border border-border transition-all"
                                        >
                                           <Trash2 size={18} />
                                        </button>
                                     </div>
                                  </td>
                               </tr>
                            ))}
                         </tbody>
                      </table>
                   </div>
                </div>
             )}

             {activeTab === 'students' && (
                <div className="space-y-10">
                   {/* Search & Selection Controls */}
                   <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
                      <div className="space-y-1">
                         <div className="flex items-center gap-4">
                            <h2 className="text-4xl font-black text-foreground tracking-tighter">Scholastic Matrix</h2>
                            {selectedLectureId && (
                               <button 
                                 onClick={() => { setSelectedLectureId(null); setActiveTab('curriculum'); }}
                                 className="flex items-center gap-2 px-6 py-3 bg-primary/10 text-primary border border-primary/20 rounded-2xl text-[10px] font-black uppercase tracking-widest hover:bg-primary hover:text-white transition-all shadow-lg"
                               >
                                  <ArrowLeft size={14} /> Back to Modules
                               </button>
                            )}
                         </div>
                          <div className="flex items-center gap-3 mt-2">
                             <span className="text-[10px] font-black text-text-muted uppercase tracking-widest">Active Focus:</span>
                             {selectedLectureId ? (
                                <div className="flex items-center gap-2 px-3 py-1 bg-surface-alt border border-border rounded-full text-[10px] font-black text-text-muted uppercase">
                                   Lecture: {lectures.find(l => l.id === selectedLectureId)?.title || 'Selected module'}
                                </div>
                             ) : (
                                <div className="flex items-center gap-2 px-3 py-1 bg-surface-alt border border-border rounded-full text-[10px] font-black text-text-muted uppercase">
                                   Global Class Enrollment
                                </div>
                             )}
                          </div>
                       </div>
                       
                       <div className="flex items-center gap-4">
                          <button 
                            onClick={() => setShowEnrollModal(true)}
                            className="px-6 py-4 bg-primary text-white border border-primary rounded-2xl text-[10px] font-black uppercase tracking-widest hover:scale-105 transition-all shadow-lg crimson-glow flex items-center gap-2"
                          >
                             <Plus size={14} /> Add Student
                          </button>
                          <div className="relative">
                            <Search className="absolute left-5 top-1/2 -translate-y-1/2 text-text-muted" size={18} />
                            <input 
                               type="text" 
                               value={searchQuery}
                               onChange={e => setSearchQuery(e.target.value)}
                               placeholder="Search participant name..."
                               className="pl-14 pr-8 py-4 bg-surface border border-border rounded-[2rem] text-sm font-bold w-80 focus:border-primary crimson-glow outline-none transition-all"
                            />
                         </div>
                         <div className="flex p-1 bg-surface-alt border border-border rounded-2xl">
                            <button 
                               onClick={() => setViewMode('grid')}
                               className={`p-3 rounded-xl transition-all ${viewMode === 'grid' ? 'bg-primary text-white shadow-lg' : 'text-text-muted hover:text-foreground'}`}
                            >
                               <LayoutGrid size={18} />
                            </button>
                            <button 
                               onClick={() => setViewMode('list')}
                               className={`p-3 rounded-xl transition-all ${viewMode === 'list' ? 'bg-primary text-white shadow-lg' : 'text-text-muted hover:text-foreground'}`}
                            >
                               <ListIcon size={18} />
                            </button>
                         </div>
                      </div>
                   </div>

                   {/* Student Grid / List */}
                   {viewMode === 'grid' ? (
                      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-8">
                         {filteredStudents.map(student => (
                            <div 
                               key={student.student_id}
                               onClick={() => router.push(`/teacher/students/${student.student_id}`)}
                               className="group glass-card p-8 border border-border hover:border-primary/40 transition-all cursor-pointer hover:-translate-y-2 relative overflow-hidden flex flex-col items-center text-center"
                            >
                               <div className="absolute top-0 right-0 p-4 opacity-0 group-hover:opacity-100 transition-all">
                                  <ArrowUpRight size={20} className="text-primary" />
                               </div>
                               <div className="w-24 h-24 rounded-[2.5rem] bg-surface-alt flex items-center justify-center font-black text-primary border border-border group-hover:bg-primary group-hover:text-white transition-all text-4xl mb-6 crimson-glow">
                                  {student.full_name?.charAt(0)}
                               </div>
                               <div className="space-y-1 mb-8">
                                  <h3 className="text-xl font-black tracking-tight">{student.full_name}</h3>
                                  <p className="text-[10px] font-black text-text-muted uppercase tracking-widest">{student.email}</p>
                               </div>
                               
                               <div className="w-full space-y-4">
                                  <div className="flex justify-between text-[10px] font-black uppercase tracking-widest px-1">
                                     <span className="text-text-muted">Module Sync</span>
                                     <span className="text-primary">{Math.round(student.progress * 100)}%</span>
                                  </div>
                                  <div className="w-full h-2 bg-background border border-border rounded-full overflow-hidden">
                                     <div className="h-full bg-primary rounded-full transition-all group-hover:crimson-glow" style={{ width: `${student.progress * 100}%` }} />
                                  </div>
                               </div>

                               <div className="mt-8 pt-6 border-t border-border w-full flex items-center justify-between text-[10px] font-black uppercase tracking-widest text-text-muted">
                                  <div className="flex items-center gap-2 px-3 py-1 bg-surface-alt rounded-full">
                                     <Activity size={12} className="text-success" /> Active
                                  </div>
                                  <span>ID: {student.student_id.slice(0, 8)}</span>
                               </div>
                            </div>
                         ))}
                      </div>
                   ) : (
                      <div className="glass-card overflow-hidden">
                         <table className="w-full text-left border-collapse">
                            <tbody className="divide-y divide-border">
                               {filteredStudents.map(student => (
                                  <tr 
                                     key={student.student_id}
                                     onClick={() => router.push(`/teacher/students/${student.student_id}`)}
                                     className="group cursor-pointer hover:bg-primary/5 transition-all"
                                  >
                                     <td className="p-6">
                                        <div className="flex items-center gap-4">
                                           <div className="w-10 h-10 rounded-xl bg-surface-alt flex items-center justify-center font-black text-primary border border-border group-hover:bg-primary group-hover:text-white transition-all">
                                              {student.full_name?.charAt(0)}
                                           </div>
                                           <div>
                                              <div className="text-sm font-black">{student.full_name}</div>
                                              <div className="text-[10px] font-black text-text-muted uppercase tracking-widest">{student.email}</div>
                                           </div>
                                        </div>
                                     </td>
                                     <td className="p-6 text-center">
                                        <div className="text-xs font-black text-text-muted uppercase tracking-widest">Sync: {Math.round(student.progress * 100)}%</div>
                                     </td>
                                     <td className="p-6 text-right">
                                        <button className="p-3 hover:bg-primary/10 text-primary border border-transparent hover:border-primary/20 rounded-xl transition-all">
                                           <ChevronRight size={18} />
                                        </button>
                                     </td>
                                  </tr>
                               ))}
                            </tbody>
                         </table>
                      </div>
                   )}
                   
                   {filteredStudents.length === 0 && (
                      <div className="p-24 text-center glass-card border-dashed flex flex-col items-center justify-center gap-6">
                         <div className="w-24 h-24 bg-primary/10 rounded-[2.5rem] flex items-center justify-center text-primary animate-pulse">
                            <Users size={40} />
                         </div>
                         <div className="space-y-2">
                            <h3 className="text-2xl font-black tracking-tight">Scholastic Matrix: Vacuum State</h3>
                            <p className="text-text-muted font-bold text-sm italic max-w-md mx-auto">
                               No active synchronization detected. Students must enroll in this module via the course portal to appear in the matrix.
                            </p>
                         </div>
                          <button 
                            onClick={copyEnrollmentLink}
                            className="px-8 py-4 bg-surface-alt border border-border rounded-2xl text-[10px] font-black uppercase tracking-widest hover:bg-primary hover:text-white transition-all shadow-xl flex items-center gap-2"
                          >
                             <ArrowUpRight size={14} /> Copy Enrollment Link
                          </button>
                       </div>
                   )}
                </div>
             )}

             {activeTab === 'resources' && (
                <div className="space-y-8">
                   <div className="text-[10px] font-black text-text-muted uppercase tracking-[0.4em]">Integrated Resource Repository</div>
                   <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
                      {materials.map(mat => (
                         <div key={mat.id} className="glass-card p-8 border border-border group hover:border-primary/40 transition-all flex flex-col justify-between h-56">
                            <div className="flex items-start justify-between">
                               <div className="w-14 h-14 bg-primary/10 rounded-2xl flex items-center justify-center text-primary border border-primary/20 group-hover:bg-primary group-hover:text-white transition-all duration-500">
                                  <FileText size={24} />
                               </div>
                               <button 
                                  onClick={() => handleDeleteMaterial(mat.id)}
                                  className="p-3 text-text-muted hover:text-danger hover:bg-danger/10 rounded-xl transition-all border border-transparent hover:border-danger/20"
                               >
                                  <Trash2 size={18} />
                               </button>
                            </div>
                            <div className="space-y-4">
                               <h4 className="text-lg font-black line-clamp-1 group-hover:text-primary transition-colors">{mat.title}</h4>
                               <div className="flex items-center justify-between">
                                  <span className="text-[10px] font-black text-text-muted uppercase tracking-widest">{mat.file_type} Resource</span>
                                  <button className="flex items-center gap-2 text-[10px] font-black text-primary uppercase tracking-widest hover:underline">
                                     <Eye size={12} /> Preview Node
                                  </button>
                               </div>
                            </div>
                         </div>
                      ))}
                      
                      <button 
                          onClick={() => setShowResourceModal(true)}
                          className="glass-card p-8 border-dashed border-2 border-border flex flex-col items-center justify-center gap-6 text-text-muted hover:text-primary hover:border-primary group transition-all h-56"
                       >
                          <div className="p-6 bg-surface-alt rounded-full border border-border group-hover:border-primary group-hover:scale-110 transition-all">
                             <Plus size={32} />
                          </div>
                          <span className="text-[10px] font-black uppercase tracking-[0.3em]">Add Static Resource</span>
                       </button>
                   </div>
                </div>
             )}

             {activeTab === 'settings' && (
                <div className="max-w-2xl space-y-16 py-8">
                   <div className="space-y-8">
                      <h3 className="text-3xl font-black tracking-tight">Module Parameters</h3>
                      <div className="space-y-8">
                         <div className="space-y-3 font-bold">
                            <label className="text-[10px] font-black text-text-muted uppercase tracking-widest ml-1">Identity Header</label>
                            <input 
                               type="text" 
                               defaultValue={course?.title}
                               className="w-full px-8 py-5 bg-surface border border-border rounded-3xl text-lg font-black focus:border-primary outline-none transition-all crimson-glow"
                            />
                         </div>
                         <div className="space-y-3 font-bold text-sm">
                            <label className="text-[10px] font-black text-text-muted uppercase tracking-widest ml-1">Contextual Description</label>
                            <textarea 
                               defaultValue={course?.description}
                               className="w-full px-8 py-5 bg-surface border border-border rounded-3xl h-48 focus:border-primary outline-none transition-all resize-none leading-relaxed"
                            />
                         </div>
                      </div>
                      <button className="px-12 py-5 bg-primary text-white rounded-[2rem] font-black text-xs uppercase tracking-[0.2em] crimson-glow hover:scale-105 transition-all shadow-xl">
                         Update Module Configuration
                      </button>
                   </div>

                   <div className="p-10 bg-danger/5 border border-danger/20 rounded-[3rem] space-y-10">
                      <div className="space-y-2">
                        <h3 className="text-2xl font-black text-danger">Nuclear Protocol</h3>
                        <p className="text-sm text-text-muted font-bold italic">This action will permanently eradicate the module and all associated synchronization data. There is no rollback mechanism.</p>
                      </div>
                      <button 
                        onClick={() => { if(confirm('INITIATE ERASE?')) coursesAPI.delete(courseId).then(() => router.push('/teacher/courses')); }}
                        className="flex items-center gap-4 px-10 py-5 bg-danger text-white rounded-2xl font-black text-xs uppercase tracking-widest hover:scale-105 transition-all shadow-xl shadow-danger/20"
                      >
                         <Trash2 size={20} /> Eradicate Entire Module
                      </button>
                   </div>
                </div>
             )}
          </div>
        </div>

        {/* Global Floating Communication Interface */}
        <CommunicationFab recipientId={filteredStudents.length === 1 ? filteredStudents[0].student_id : undefined} recipientName={filteredStudents.length === 1 ? filteredStudents[0].full_name : 'Selected Participants'} />
      </main>

      {/* Add Lecture Modal */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-2xl z-[200] flex items-center justify-center p-6">
          <div className="bg-surface border border-border w-full max-w-3xl rounded-[4rem] overflow-hidden shadow-2xl animate-in zoom-in-95 duration-500">
             <div className="p-12 border-b border-border flex items-center justify-between">
               <h2 className="text-4xl font-black tracking-tighter">Deploy New Semantic Node</h2>
               <button onClick={() => !isUploading && setShowAddModal(false)} className="p-4 hover:bg-surface-alt border border-border rounded-2xl transition-all"><X size={28} /></button>
             </div>
             
             <div className="p-12 space-y-10">
                <div className="space-y-4">
                   <label className="text-[10px] font-black text-text-muted uppercase tracking-widest ml-1">Identity Node Header</label>
                   <input type="text" value={newLecture.title} onChange={e => setNewLecture({...newLecture, title: e.target.value})} placeholder="e.g. Fundamental Neural Dynamics" className="w-full px-10 py-6 bg-surface-alt border border-border rounded-3xl font-black text-xl outline-none focus:border-primary transition-all" />
                </div>
                
                <div className="grid grid-cols-2 gap-6">
                   <button onClick={() => setNewLecture({...newLecture, type:'youtube'})} className={`p-8 rounded-[2rem] border-2 transition-all flex flex-col items-center gap-4 font-black uppercase text-xs tracking-widest ${newLecture.type === 'youtube' ? 'bg-primary border-primary text-white shadow-xl' : 'bg-surface border-border text-text-muted hover:border-primary/20'}`}>
                      <MonitorPlay size={32} /> YouTube Mechanism
                   </button>
                   <button onClick={() => setNewLecture({...newLecture, type:'upload'})} className={`p-8 rounded-[2rem] border-2 transition-all flex flex-col items-center gap-4 font-black uppercase text-xs tracking-widest ${newLecture.type === 'upload' ? 'bg-primary border-primary text-white shadow-xl' : 'bg-surface border-border text-text-muted hover:border-primary/20'}`}>
                      <Upload size={32} /> Direct Core Upload
                   </button>
                </div>

                {newLecture.type === 'youtube' ? (
                   <input type="text" value={newLecture.youtube_url} onChange={e => setNewLecture({...newLecture, youtube_url: e.target.value})} placeholder="Neural Stream URL (YouTube)" className="w-full px-10 py-6 bg-surface-alt border border-border rounded-3xl font-bold text-sm outline-none focus:border-primary transition-all" />
                ) : (
                   <label className="block p-12 border-2 border-dashed border-border rounded-[2rem] text-center cursor-pointer hover:border-primary transition-all">
                      <input type="file" onChange={e => e.target.files && setVideoFile(e.target.files[0])} className="hidden" />
                      <div className="flex flex-col items-center gap-4">
                         <div className="p-6 bg-primary/5 rounded-full text-primary"><Upload size={40} /></div>
                         <div className="text-sm font-black uppercase tracking-widest">{videoFile ? videoFile.name : 'Inject Video Payload'}</div>
                      </div>
                   </label>
                )}
             </div>

             <div className="p-12 bg-surface-alt/50 border-t border-border">
                <button onClick={handleAddLecture} disabled={!newLecture.title || isUploading} className="w-full py-8 bg-primary text-white rounded-[2.5rem] font-black text-xl uppercase tracking-widest crimson-glow hover:scale-[1.02] active:scale-95 transition-all shadow-2xl">
                   {isUploading ? 'Calibrating Neural Sync...' : 'Initiate Node Deployment'}
                </button>
             </div>
           </div>
        </div>
      )}

      {/* Sync YouTube Playlist Modal */}
      {showSyncModal && (
        <div className="fixed inset-0 bg-background/80 backdrop-blur-2xl z-[200] flex items-center justify-center p-6">
          <div className="bg-surface border border-border w-full max-w-2xl rounded-[3rem] overflow-hidden shadow-2xl animate-slide-up">
             <div className="p-10 border-b border-border bg-surface-alt/50 flex items-center justify-between">
               <div className="flex items-center gap-5">
                 <div className="w-12 h-12 rounded-2xl bg-primary/10 flex items-center justify-center text-primary animate-pulse">
                   <Activity size={24} />
                 </div>
                 <h2 className="text-3xl font-black tracking-tighter">Multi-Node Sync</h2>
               </div>
               <button onClick={() => !isProcessing && setShowSyncModal(false)} className="p-3 hover:bg-surface-alt border border-border rounded-xl transition-all"><X size={24} /></button>
             </div>
             <div className="p-10 space-y-8">
                <p className="text-[10px] font-black text-text-muted uppercase tracking-[0.2em] leading-relaxed">
                  Synchronize an entire YouTube playlist to automatically generate semantic nodes across the course timeline.
                </p>
                <div className="space-y-4">
                   <label className="text-[10px] font-black text-text-muted uppercase tracking-widest text-primary ml-1">Playlist URL</label>
                   <input 
                     type="text" 
                     value={syncUrl} 
                     onChange={e => setSyncUrl(e.target.value)} 
                     placeholder="https://youtube.com/playlist?list=..." 
                     className="w-full px-8 py-5 bg-surface-alt border border-border rounded-2xl font-bold outline-none focus:border-primary transition-all shadow-inner" 
                   />
                </div>
             </div>
             <div className="p-10 bg-surface-alt/50 border-t border-border">
                <button 
                  onClick={handleSyncYoutube} 
                  disabled={!syncUrl || isProcessing} 
                  className="w-full py-6 bg-primary text-white rounded-2xl font-black text-sm uppercase tracking-widest crimson-glow hover:scale-105 transition-all shadow-xl flex items-center justify-center gap-4"
                >
                   {isProcessing ? <Activity className="animate-spin" /> : <Zap size={20} />}
                   {isProcessing ? 'Synchronizing Neural Stream...' : 'Initiate Mass Import'}
                </button>
             </div>
          </div>
        </div>
      )}

      {/* Inject Resource Modal */}
      {showResourceModal && (
        <div className="fixed inset-0 bg-background/80 backdrop-blur-2xl z-[200] flex items-center justify-center p-6">
          <div className="bg-surface border border-border w-full max-w-xl rounded-[3rem] overflow-hidden shadow-2xl animate-slide-up">
             <div className="p-10 border-b border-border bg-surface-alt/50 flex items-center justify-between">
               <div className="flex items-center gap-5">
                 <div className="w-12 h-12 rounded-2xl bg-info/10 flex items-center justify-center text-info">
                   <FileText size={24} />
                 </div>
                 <h2 className="text-3xl font-black tracking-tighter">Resource Injection</h2>
               </div>
               <button onClick={() => !isProcessing && setShowResourceModal(false)} className="p-3 hover:bg-surface-alt border border-border rounded-xl transition-all"><X size={24} /></button>
             </div>
             <div className="p-10 space-y-8">
                <div className="space-y-6">
                   <div className="space-y-2">
                      <label className="text-[10px] font-black text-text-muted uppercase tracking-widest ml-1">Resource Identity</label>
                      <input 
                        type="text" 
                        value={resourceForm.title} 
                        onChange={e => setResourceForm({...resourceForm, title: e.target.value})} 
                        placeholder="e.g. Applied Physics Handbook" 
                        className="w-full px-8 py-5 bg-surface-alt border border-border rounded-2xl font-bold outline-none focus:border-primary transition-all shadow-inner" 
                      />
                   </div>

                   <div className="space-y-4">
                      <label className="text-[10px] font-black text-text-muted uppercase tracking-widest ml-1">Asset Injection Method</label>
                      <div className="flex p-1 bg-surface-alt border border-border rounded-2xl">
                         <button 
                            onClick={() => setResourceFile(null)}
                            className={`flex-1 py-3 rounded-xl font-black text-[10px] uppercase tracking-widest transition-all ${!resourceFile ? 'bg-primary text-white' : 'text-text-muted'}`}
                         >
                            Neural URL
                         </button>
                         <label className={`flex-1 py-3 rounded-xl font-black text-[10px] uppercase tracking-widest transition-all text-center cursor-pointer ${resourceFile ? 'bg-primary text-white' : 'text-text-muted'}`}>
                            <input type="file" onChange={e => e.target.files && setResourceFile(e.target.files[0])} className="hidden" />
                            Core Upload
                         </label>
                      </div>
                   </div>

                   {!resourceFile ? (
                      <div className="space-y-2">
                         <label className="text-[10px] font-black text-text-muted uppercase tracking-widest ml-1">Asset Neural Path (URL)</label>
                         <input 
                           type="text" 
                           value={resourceForm.path} 
                           onChange={e => setResourceForm({...resourceForm, path: e.target.value})} 
                           placeholder="Cloudinary link or local reference" 
                           className="w-full px-8 py-5 bg-surface-alt border border-border rounded-2xl font-bold outline-none focus:border-primary transition-all shadow-inner" 
                         />
                      </div>
                   ) : (
                      <div className="p-8 border-2 border-dashed border-primary/40 rounded-3xl bg-primary/5 flex items-center justify-between">
                         <div className="flex items-center gap-4">
                            <div className="p-3 bg-primary/20 rounded-xl text-primary"><FileText size={20} /></div>
                            <div className="text-sm font-black text-foreground truncate max-w-[200px]">{resourceFile.name}</div>
                         </div>
                         <button onClick={() => setResourceFile(null)} className="p-2 hover:bg-error/10 text-error rounded-lg transition-all"><X size={16} /></button>
                      </div>
                   )}

                   <div className="grid grid-cols-4 gap-3">
                      {['pdf', 'ppt', 'docx', 'txt'].map(type => (
                        <button 
                          key={type}
                          onClick={() => setResourceForm({...resourceForm, type})}
                          className={`py-3 rounded-xl font-black text-[10px] uppercase tracking-widest border transition-all ${resourceForm.type === type ? 'bg-primary text-white border-primary shadow-lg' : 'bg-surface-alt text-text-muted border-border hover:border-primary/40'}`}
                        >
                          {type}
                        </button>
                      ))}
                   </div>
                </div>
                <button 
                  onClick={handleAddMaterial} 
                  disabled={!resourceForm.title || (!resourceForm.path && !resourceFile) || isProcessing} 
                  className="w-full py-8 bg-primary text-white rounded-[2.5rem] font-black text-xl uppercase tracking-widest crimson-glow hover:scale-[1.02] active:scale-95 transition-all shadow-2xl mt-8"
                >
                   {isProcessing ? 'Materializing Resource...' : 'Initiate Injection Deployment'}
                </button>
             </div>
          </div>
        </div>
      )}

      {/* Enroll Student Modal */}
      {showEnrollModal && (
        <div className="fixed inset-0 bg-background/80 backdrop-blur-2xl z-[200] flex items-center justify-center p-6">
          <div className="bg-surface border border-border w-full max-w-xl rounded-[3rem] overflow-hidden shadow-2xl animate-slide-up">
             <div className="p-10 border-b border-border bg-surface-alt/50 flex items-center justify-between">
               <div className="flex items-center gap-5">
                 <div className="w-12 h-12 rounded-2xl bg-primary/10 flex items-center justify-center text-primary group-hover:scale-110 transition-transform">
                   <Users size={24} />
                 </div>
                 <h2 className="text-3xl font-black tracking-tighter">Manual Enrollment</h2>
               </div>
               <button onClick={() => !isProcessing && setShowEnrollModal(false)} className="p-3 hover:bg-surface-alt border border-border rounded-xl transition-all"><X size={24} /></button>
             </div>
             <div className="p-10 space-y-8">
                <div className="space-y-4 text-center">
                   <p className="text-[10px] font-black text-text-muted uppercase tracking-[0.2em] leading-relaxed">
                      Enter the cognitive identifier (email) of the student to manually synchronize them with this modular flow. They must already have an account.
                   </p>
                </div>
                <div className="space-y-2">
                   <label className="text-[10px] font-black text-text-muted uppercase tracking-widest text-primary ml-1">Student Identifier (Email)</label>
                   <input 
                     type="email" 
                     value={enrollEmail} 
                     onChange={e => setEnrollEmail(e.target.value)} 
                     placeholder="student@university.edu" 
                     className="w-full px-8 py-5 bg-surface-alt border border-border rounded-2xl font-bold outline-none focus:border-primary transition-all shadow-inner" 
                   />
                </div>
                <button 
                  onClick={handleEnrollStudent} 
                  disabled={!enrollEmail || isProcessing} 
                  className="w-full py-6 bg-primary text-white rounded-2xl font-black text-sm uppercase tracking-widest crimson-glow hover:scale-105 transition-all shadow-xl flex items-center justify-center gap-4"
                >
                   {isProcessing ? <Activity className="animate-spin" /> : <Plus size={20} />}
                   {isProcessing ? 'Synchronizing Participant...' : 'Authorize Enrollment'}
                </button>
             </div>
          </div>
        </div>
      )}
    </div>
  );
}
