import axios from 'axios';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: { 'Content-Type': 'application/json' },
});

// Interceptors for Auth & Loading (Next.js client-side)
if (typeof window !== 'undefined') {
  api.interceptors.request.use((config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  });

  api.interceptors.response.use(
    (response) => {
      const { data } = response;
      if (!data) return response;

      // Exhaustive list of all possible array-like keys across the entire platform
      const arrayKeys = new Set([
        'questions', 'tables', 'rows', 'messages', 'concentrations', 'concerns', 
        'suggestions', 'waveform', 'forensic_logs', 'components', 'active_nodes', 
        'focus_pulse', 'top_keywords', 'recommendations', 'teachingScore', 
        'history', 'students', 'courses', 'lectures', 'attempts', 'notifications',
        'feedbacks', 'analysis', 'timeline', 'entries', 'points', 'lapses', 'switches',
        'risk_matrix', 'waveform_data', 'lapse_wave', 'tab_wave', 'friction_zones', 'topic_analysis'
      ]);

      const deepFix = (obj: any) => {
        if (!obj || typeof obj !== 'object') return obj;
        
        if (Array.isArray(obj)) {
          obj.forEach(deepFix);
          return obj;
        }

        const idKeys = ['id', 'student_id', 'lecture_id', 'course_id', 'session_id'];

        for (const key in obj) {
          const val = obj[key];

          // Force ID strings
          if (idKeys.includes(key)) {
            if (val === null || val === undefined) {
              obj[key] = "";
            } else if (typeof val !== 'string') {
              obj[key] = String(val);
            }
          }
          // Force arrays
          else if (arrayKeys.has(key)) {
            if (!Array.isArray(val)) {
              obj[key] = [];
            }
          }
          
          // Recursive
          if (val && typeof val === 'object') {
            deepFix(val);
          }
        }
        return obj;
      };

      response.data = deepFix(data);
      return response;
    },
    (error) => {
      if (error.response?.status === 401) {
        localStorage.removeItem('token');
        localStorage.removeItem('user');
        if (window.location.pathname !== '/login') {
          window.location.href = '/login';
        }
      }

      // Flatten FastAPI/Pydantic validation errors (422)
      if (error.response?.status === 422 && Array.isArray(error.response?.data?.detail)) {
        const detail = error.response.data.detail;
        if (detail.length > 0) {
          const first = detail[0];
          const field = first.loc ? first.loc[first.loc.length - 1] : '';
          error.response.data.detail = field 
            ? `${field.charAt(0).toUpperCase() + field.slice(1)}: ${first.msg}`
            : first.msg;
        }
      }

      return Promise.reject(error);
    }
  );
}

// ─── API SECTIONS ─────────────────────────────────────────

export const authAPI = {
  register: (data: any) => api.post('/api/auth/register', data),
  login: (data: any) => api.post('/api/auth/login', data),
  googleLogin: (data: { id_token: string; role?: string; intent?: string }) => api.post('/api/auth/google', data),
  getProfile: () => api.get('/api/auth/me'),
};

export const coursesAPI = {
  list: (params?: { view?: string; search?: string; category?: string; teacher_id?: string }) => 
    api.get('/api/courses', { params }),
  get: (id: string) => api.get(`/api/courses/${id}`),
  getMyCourses: () => api.get('/api/courses/enrolled/my-courses'),
  enroll: (id: string) => api.post(`/api/courses/${id}/enroll`),
  getStudents: (id: string) => api.get(`/api/courses/${id}/students`),
  create: (data: any) => api.post('/api/courses', data),
  update: (id: string, data: any) => api.put(`/api/courses/${id}`, data),
  delete: (id: string) => api.delete(`/api/courses/${id}`),
  importYoutube: (courseId: string, url: string) => 
    api.post('/api/lectures/youtube-import', { 
      course_id: courseId, 
      playlist_url: url, 
      import_transcripts: true 
    }),
  getProgress: (courseId: string) => api.get(`/api/courses/${courseId}/progress`),
};

export const lecturesAPI = {
  getByCourse: (courseId: string) => api.get(`/api/lectures/course/${courseId}`),
  get: (id: string) => api.get(`/api/lectures/${id}`),
  create: (data: any) => api.post('/api/lectures', data),
  update: (id: string, data: any) => api.put(`/api/lectures/${id}`, data),
  delete: (id: string) => api.delete(`/api/lectures/${id}`),
  uploadVideo: (id: string, file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post(`/api/lectures/${id}/upload-video`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
  },
  importYoutube: (data: { course_id: string; playlist_url: string; import_transcripts: boolean }) => 
    api.post('/api/lectures/youtube-import', data),
  getMaterials: (lectureId: string) => api.get(`/api/lectures/${lectureId}/materials`),
  getCourseMaterials: (courseId: string) => api.get(`/api/lectures/course/${courseId}/materials`),
  addMaterial: (course_id: string, title: string, file_path: string, type: string) => 
    api.post('/api/lectures/materials', { 
      course_id, 
      title, 
      file_path, 
      type 
    }),
  uploadMaterial: (course_id: string, title: string, type: string, file: File, lecture_id?: string) => {
    const formData = new FormData();
    formData.append('course_id', course_id);
    formData.append('title', title);
    formData.append('type', type);
    formData.append('file', file);
    if (lecture_id) formData.append('lecture_id', lecture_id);
    
    return api.post('/api/lectures/materials/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
  },
  deleteMaterial: (id: string) => api.delete(`/api/lectures/materials/${id}`),
  generateTranscript: (id: string) => api.post(`/api/lectures/${id}/generate-transcript`),
};

export const engagementAPI = {
  submit: (data: any) => api.post('/api/engagement/submit', data),
  getJobStatus: (job_id: string) => api.get(`/api/engagement/job/${job_id}`),
  getHeatmap: (lectureId: string) => api.get(`/api/engagement/heatmap/${lectureId}`),
  getLiveWatchers: (lectureId: string) => api.get(`/api/engagement/live-watchers/${lectureId}`),
  getHistory: (lectureId: string) => api.get(`/api/engagement/history/${lectureId}`),
  finalizeSession: (data: { session_id: string; lecture_id: string; waveform: any[]; watch_duration?: number; total_duration?: number }) => 
    api.post('/api/engagement/finalize-session', data),
};

export const analyticsAPI = {
  getStudentDashboard: () => api.get('/api/analytics/student-dashboard'),
  getStudentEngagementHistory: (days: number) => api.get(`/api/analytics/student-engagement-history?days=${days}`),
  getStudentICAP: () => api.get('/api/analytics/student/icap-distribution'),
  exportData: (courseId?: string) => api.get(`/api/analytics/student/export${courseId ? `?course_id=${courseId}` : ''}`),
  getLectureEngagementWaves: (lectureId: string, studentIds?: string) => 
    api.get(`/api/analytics/lecture-waves/${lectureId}${studentIds ? `?student_ids=${studentIds}` : ''}`),
  getCourseDashboard: (course_id: string) => api.get(`/api/analytics/course-dashboard/${course_id}`),
  getLectureWaves: (lecture_id: string, student_ids?: string) => 
    api.get(`/api/analytics/lecture-waves/${lecture_id}${student_ids ? `?student_ids=${student_ids}` : ''}`),
  getLecturesEngagement: (courseId: string) => api.get(`/api/analytics/course/${courseId}/lectures-engagement`),
  getFeedbackAnalysis: (courseId: string) => api.get(`/api/analytics/course/${courseId}/feedback-analysis`),
  getTeachingScore: (courseId: string) => api.get(`/api/analytics/teaching-score/${courseId}`),
  getLiveSessions: () => api.get('/api/analytics/live-sessions'),
  getLectureIntelligence: (lectureId: string) => api.get(`/api/analytics/lecture/${lectureId}/intelligence`),
  deployPatch: (courseId: string) => api.post(`/api/analytics/course/${courseId}/deploy-patch`),
};

export const teacherAPI = {
  getDashboard: () => api.get('/api/teacher/dashboard'),
  getCourses: () => api.get('/api/teacher/courses'),
  getStudentEngagement: (courseId: string) => api.get(`/api/analytics/course/${courseId}/engagement`),
  getStudentDetail: (studentId: string, courseId?: string) => 
    api.get(`/api/analytics/student/${studentId}${courseId ? `?course_id=${courseId}` : ''}`),
  getStudentSessionDiagnostics: (studentId: string, sessionId: string) => 
    api.get(`/api/analytics/student/${studentId}/session/${sessionId}/diagnostics`),
  enrollStudent: (courseId: string, email: string) => 
    api.post(`/api/courses/${courseId}/enroll-student`, { email }),
};

export const feedbackAPI = {
  submit: (data: any) => api.post('/api/feedback', data),
};

export const tutorAPI = {
  getSessions: () => api.get('/api/tutor/sessions'),
  createSession: (data: { title: string; mode: string }) => 
    api.post(`/api/tutor/sessions?title=${encodeURIComponent(data.title)}&mode=${encodeURIComponent(data.mode)}`),
  chat: async (data: any, onChunk?: (text: string) => void) => {
    const response = await fetch(`${API_BASE_URL}/api/tutor/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('token')}`
      },
      body: JSON.stringify(data)
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error(`AI Chat Failure: ${response.status} - ${errorText}`);
      throw new Error(`Chat failed: ${response.status}`);
    }

    const reader = response.body?.getReader();
    if (!reader) return '';
    
    const decoder = new TextDecoder('utf-8');
    let fullText = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      const chunk = decoder.decode(value, { stream: true });
      fullText += chunk;
      if (onChunk) onChunk(fullText);
    }
    return fullText;
  },
  deleteSession: (id: string) => api.delete(`/api/tutor/sessions/${id}`),
  clearSession: (id: string) => api.delete(`/api/tutor/sessions/${id}/clear`),
  deleteMessage: (id: string) => api.delete(`/api/tutor/messages/${id}`),
  getSessionMessages: (id: string) => api.get(`/api/tutor/sessions/${id}/messages`),
};

export const quizzesAPI = {
  get: (id: string) => api.get(`/api/quizzes/${id}`),
  getByLecture: (lectureId: string) => api.get(`/api/quizzes/lecture/${lectureId}`),
  create: (data: any) => api.post('/api/quizzes', data),
  update: (id: string, data: any) => api.put(`/api/quizzes/${id}`, data),
  delete: (id: string) => api.delete(`/api/quizzes/${id}`),
  listMine: () => api.get('/api/quizzes/mine'),
  generateAI: (data: { lecture_id: string; num_questions: number; difficulty: string; include_icap: boolean }) => 
    api.post('/api/quizzes/generate-ai', data),
  refineAI: (data: { lecture_id: string; current_questions: any[]; feedback: string }) => 
    api.post('/api/quizzes/generate-ai-refine', data),
  submitAttempt: (data: any) => api.post('/api/quizzes/attempt', data),
  getAttempts: (quizId: string) => api.get(`/api/quizzes/attempts/${quizId}`),
  getStudentAttempts: (studentId: string, courseId: string) => 
    api.get(`/api/quizzes/student/${studentId}/course/${courseId}`),
  getCourseAnalytics: (courseId: string) => 
    api.get(`/api/quizzes/course/${courseId}/analytics`),
};

export const messagesAPI = {
  getConversations: () => api.get('/api/messages/conversations'),
  getMessagesWithUser: (userId: string, courseId?: string) => 
    api.get(`/api/messages/with/${userId}${courseId ? `?course_id=${courseId}` : ''}`),
  sendMessage: (data: { receiver_id: string; content: string; subject?: string; course_id?: string; category?: string; parent_id?: string }) => 
    api.post('/api/messages', data),
  getUnreadCount: () => api.get('/api/messages/unread-count'),
  markAsRead: (messageId: string) => api.put(`/api/messages/${messageId}/read`),
  getStudentAnalytics: (studentId: string, courseId?: string) => 
    api.get(`/api/messages/student-analytics/${studentId}${courseId ? `?course_id=${courseId}` : ''}`),
  bulkSend: (data: any) => api.post('/api/messages/bulk-send', data),
  getAtRiskStudents: (courseId: string) => api.get(`/api/messages/at-risk-students/${courseId}`),
  deleteConversation: (userId: string) => api.delete(`/api/messages/conversation/${userId}`),
  deleteMessage: (messageId: string) => api.delete(`/api/messages/${messageId}`),
};

export const notificationsAPI = {
  list: (unreadOnly: boolean = false) => api.get(`/api/notifications${unreadOnly ? '?unread_only=true' : ''}`),
  getUnreadCount: () => api.get('/api/notifications/unread-count'),
  markAsRead: (id: string) => api.put(`/api/notifications/${id}/read`),
  markAllRead: () => api.put('/api/notifications/read-all'),
  sendAnnouncement: (data: any) => api.post('/api/notifications/announce', data),
};

export const assignmentsAPI = {
  get: (id: string) => api.get(`/api/assignments/${id}`),
  getByCourse: (courseId: string) => api.get(`/api/assignments/course/${courseId}`),
  create: (data: any) => api.post('/api/assignments', data),
  submit: (data: any) => api.post('/api/assignments/submit', data),
  getSubmissions: (assignmentId: string) => api.get(`/api/assignments/${assignmentId}/submissions`),
  grade: (data: { submission_id: string; grade: number; teacher_feedback?: string }) => 
    api.put(`/api/assignments/submissions/${data.submission_id}/grade`, data),
  generateAI: (data: { lecture_id: string; subject_type: string; difficulty: string }) => 
    api.post('/api/assignments/generate-ai', data),
  getReference: (assignmentId: string) => api.get(`/api/assignments/${assignmentId}/ai-reference`),
  getRecap: (submissionId: string) => api.get(`/api/assignments/submissions/${submissionId}/ai-recap`),
};

export const adminAPI = {
  listTeachers: () => api.get('/api/admin/teachers'),
  getTeacherDetail: (id: string) => api.get(`/api/admin/teacher/${id}`),
  listUsers: (role?: string) => api.get(`/api/admin/users${role ? `?role=${role}` : ''}`),
  toggleUserActive: (id: string) => api.put(`/api/admin/users/${id}/toggle-active`),
  deleteUser: (id: string) => api.delete(`/api/admin/users/${id}`),
  deleteCourse: (id: string) => api.delete(`/api/admin/courses/${id}`),
  getSystemStats: () => api.get('/api/admin/system-stats'),
  getEngagementCorrelation: () => api.get('/api/admin/engagement-correlation'),
  exportDatasets: () => api.get('/api/admin/export-datasets', { responseType: 'blob' }),
  getDBTables: () => api.get('/api/admin/db/tables'),
  getTableData: (tableName: string, page: number = 1) => 
    api.get(`/api/admin/db/tables/${tableName}?page=${page}`),
};

export const activityAPI = {
  submitBatch: (data: any) => api.post('/api/activity/batch', data),
  sessionEnd: (data: any) => api.post('/api/activity/session-end', data),
};

export const gamificationAPI = {
  getStats: () => api.get('/api/gamification/profile'),
  getLeaderboard: (limit: number = 20) => api.get(`/api/gamification/leaderboard?limit=${limit}`),
  awardPoints: (activity: string, amount: number = 10) => 
    api.post(`/api/gamification/award-points?activity=${encodeURIComponent(activity)}&amount=${amount}`),
};

export const materialsAPI = {
  getByLecture: (lectureId: string) => api.get(`/api/lectures/${lectureId}/materials`),
};

export default api;
