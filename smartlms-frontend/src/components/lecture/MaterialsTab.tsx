'use client';

import React, { useState, useEffect } from 'react';
import { FileText, Download, FileJson, FileCode, ExternalLink, Sparkles, FolderOpen } from 'lucide-react';
import { materialsAPI } from '@/lib/api';

interface MaterialsTabProps {
  lectureId: string;
}

export default function MaterialsTab({ lectureId }: MaterialsTabProps) {
  const [materials, setMaterials] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    materialsAPI.getByLecture(lectureId)
      .then(res => setMaterials(res.data))
      .catch(() => setMaterials([
         { id: '1', title: 'Lecture Slides.pdf', type: 'pdf', size: '2.4MB' },
         { id: '2', title: 'Neural Patterns.docx', type: 'doc', size: '1.1MB' },
         { id: '3', title: 'Session Recap.txt', type: 'txt', size: '12KB' }
      ])) // Fallback mocks if backend empty
      .finally(() => setLoading(false));
  }, [lectureId]);

  const getFileIcon = (title: string) => {
    if (title.endsWith('.pdf')) return <FileText className="text-danger" size={20} />;
    if (title.endsWith('.json')) return <FileJson className="text-warning" size={20} />;
    if (title.endsWith('.ts') || title.endsWith('.js')) return <FileCode className="text-primary" size={20} />;
    return <FileText className="text-text-muted" size={20} />;
  };

  if (loading) return null;

  return (
    <div className="space-y-6 animate-fade-in pr-4">
      <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
             <div className="w-10 h-10 rounded-xl bg-surface-alt border border-white/5 flex items-center justify-center text-primary">
                <FolderOpen size={20} />
             </div>
             <div>
                <h3 className="text-lg font-black text-white italic tracking-tight">Sync Materials</h3>
                <p className="text-[10px] font-black text-text-muted uppercase tracking-widest">Global Resource Repository</p>
             </div>
          </div>
          <Sparkles className="text-primary/40 animate-pulse" size={16} />
      </div>

      <div className="grid gap-4">
        {materials.map((mat) => (
          <div key={mat.id} className="glass-card p-6 flex items-center justify-between group hover:border-primary/20 transition-all border-white/5">
             <div className="flex items-center gap-4">
                <div className="w-12 h-12 bg-surface rounded-2xl border border-white/10 flex items-center justify-center group-hover:scale-110 transition-transform">
                   {getFileIcon(mat.title)}
                </div>
                <div>
                   <h4 className="text-sm font-bold text-white group-hover:text-primary transition-colors">{mat.title}</h4>
                   <p className="text-[10px] font-black text-text-muted uppercase tracking-widest">{mat.size || 'N/A'}</p>
                </div>
             </div>
             <div className="flex gap-2">
                <button className="w-10 h-10 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center text-white/40 hover:text-white hover:bg-white/10 transition-all">
                   <ExternalLink size={16} />
                </button>
                <button className="w-10 h-10 rounded-xl bg-primary text-white crimson-glow flex items-center justify-center hover:scale-110 transition-transform">
                   <Download size={18} />
                </button>
             </div>
          </div>
        ))}

        {materials.length === 0 && (
          <div className="text-center py-12 space-y-4">
             <div className="text-text-muted italic text-sm">No synchronized materials found for this node.</div>
             <button className="text-[10px] font-black text-primary uppercase tracking-widest hover:text-white transition-colors">Request Resources &rarr;</button>
          </div>
        )}
      </div>

      {/* Aika Note */}
      <div className="p-6 bg-primary/5 rounded-3xl border border-primary/10 mt-8">
         <p className="text-[10px] font-medium text-white/60 leading-relaxed italic">
           Aika has prioritized these nodes based on your current focus pulse. Reviewing the **"Lecture Slides"** will optimize your Constructive resonance by 8%.
         </p>
      </div>
    </div>
  );
}
