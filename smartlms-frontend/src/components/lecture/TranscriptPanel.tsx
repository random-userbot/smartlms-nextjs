'use client';

import React, { useState, useMemo } from 'react';
import { Search, FileText, Download, Target, ChevronRight } from 'lucide-react';

interface TranscriptPanelProps {
  transcript: string;
  onJumpToTime?: (seconds: number) => void;
  isLoading?: boolean;
}

export default function TranscriptPanel({ transcript, onJumpToTime, isLoading }: TranscriptPanelProps) {
  const [searchTerm, setSearchTerm] = useState('');

  // Simple parsing of timestamped lines like "[00:12] Hello world"
  const transcriptLines = useMemo(() => {
    if (!transcript) return [];
    
    return transcript.split('\n').filter(line => line.trim()).map((line, index) => {
      const timestampMatch = line.match(/^\[(\d{1,2}):(\d{2})\]/);
      if (timestampMatch) {
         const mins = parseInt(timestampMatch[1]);
         const secs = parseInt(timestampMatch[2]);
         const timeInSecs = mins * 60 + secs;
         const content = line.replace(/^\[\d{1,2}:\d{2}\]\s*/, '');
         return { id: index, time: timeInSecs, timestamp: `[${timestampMatch[1]}:${timestampMatch[2]}]`, content };
      }
      return { id: index, time: null, timestamp: null, content: line };
    });
  }, [transcript]);

  const filteredLines = useMemo(() => {
    if (!searchTerm) return transcriptLines;
    return transcriptLines.filter(line => 
      line.content.toLowerCase().includes(searchTerm.toLowerCase())
    );
  }, [transcriptLines, searchTerm]);

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center h-full space-y-4 opacity-50">
        <div className="w-8 h-8 border-2 border-primary/20 border-t-primary rounded-full animate-spin"></div>
        <div className="text-[10px] font-black uppercase tracking-widest">Generating Transcript...</div>
      </div>
    );
  }

  if (!transcript) {
    return (
      <div className="flex flex-col items-center justify-center p-12 text-center space-y-4 h-full">
        <div className="w-16 h-16 rounded-3xl bg-surface-alt border border-border flex items-center justify-center text-text-muted">
          <FileText size={32} />
        </div>
        <div className="space-y-1">
          <div className="text-sm font-black text-foreground uppercase tracking-widest">No Transcript Available</div>
          <p className="text-xs text-text-muted max-w-[200px]">The pedagogical script for this module has not been synchronized yet.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full overflow-hidden bg-background">
      {/* Search Bar */}
      <div className="p-6 border-b border-border">
        <div className="relative">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-text-muted" size={16} />
          <input 
            type="text" 
            placeholder="Search pedagogical insights..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full bg-surface border border-border rounded-xl py-3 pl-12 pr-4 text-xs font-medium text-white placeholder:text-text-muted focus:border-primary/50 outline-none transition-all"
          />
        </div>
      </div>

      {/* Transcript List */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4 no-scrollbar">
        {filteredLines.length > 0 ? filteredLines.map((line) => (
          <div 
            key={line.id} 
            className={`group flex gap-4 p-4 rounded-2xl border border-transparent hover:bg-surface hover:border-border transition-all cursor-default ${searchTerm && line.content.toLowerCase().includes(searchTerm.toLowerCase()) ? 'bg-primary/5 border-primary/20 shadow-lg' : ''}`}
          >
            {line.time !== null && (
              <button 
                onClick={() => onJumpToTime?.(line.time!)}
                className="shrink-0 flex items-center justify-center w-12 h-8 bg-surface-alt border border-border rounded-lg text-[10px] font-black text-primary hover:bg-primary/10 hover:border-primary/40 transition-all uppercase"
              >
                {line.timestamp?.replace(/[\[\]]/g, '')}
              </button>
            )}
            <div className="flex-1">
              <p className="text-sm font-medium text-white/90 leading-relaxed selection:bg-primary/30">
                {line.content}
              </p>
            </div>
            {line.time !== null && (
               <Target size={14} className="text-text-muted opacity-0 group-hover:opacity-100 transition-opacity translate-y-1" />
            )}
          </div>
        )) : (
          <div className="text-center py-12 text-text-muted text-[10px] font-black uppercase tracking-widest">
            No matching terms found
          </div>
        )}
      </div>

      {/* Footer Info */}
      <div className="p-4 border-t border-border bg-surface/30 flex items-center justify-between">
         <div className="flex items-center gap-2 text-[9px] font-black text-text-muted uppercase tracking-widest">
            <Download size={12} /> export transcript.txt
         </div>
         <div className="text-[9px] font-black text-primary uppercase tracking-widest">
            Auto-Sync Active
         </div>
      </div>
    </div>
  );
}
