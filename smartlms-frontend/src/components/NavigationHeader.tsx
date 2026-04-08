'use client';

import React from 'react';
import { useRouter } from 'next/navigation';
import { ArrowLeft, ChevronLeft } from 'lucide-react';

interface NavigationHeaderProps {
  title: string;
  subtitle?: string;
  showBack?: boolean;
}

export default function NavigationHeader({ title, subtitle, showBack = true }: NavigationHeaderProps) {
  const router = useRouter();

  return (
    <div className="flex items-center justify-between mb-8 animate-in fade-in slide-in-from-top-4 duration-700">
      <div className="flex items-center gap-6">
        {showBack && (
          <button 
            onClick={() => router.back()}
            className="w-12 h-12 rounded-2xl bg-surface border border-border flex items-center justify-center text-text-muted hover:text-primary hover:border-primary/50 hover:bg-background transition-all group"
          >
            <ChevronLeft size={24} className="group-hover:-translate-x-0.5 transition-transform" />
          </button>
        )}
        <div>
          {subtitle && (
            <div className="text-[10px] font-black text-primary uppercase tracking-[0.3em] mb-1">
              {subtitle}
            </div>
          )}
          <h1 className="text-4xl font-black text-foreground tracking-tighter capitalize">
            {title}
          </h1>
        </div>
      </div>
    </div>
  );
}
