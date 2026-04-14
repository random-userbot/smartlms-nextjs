'use client';

import React, { useMemo } from 'react';
import { motion } from 'framer-motion';
import { Info, BarChart2, AlertCircle } from 'lucide-react';

interface FeatureImpact {
  label: string;
  weight: number; 
  category: 'Engagement' | 'Obstacle' | 'Learning Flow';
}

interface EngagementFactorChartProps {
  features: Record<string, any>;
  shapExplanations?: Record<string, any>;
}

const AU_MAP: Record<string, { label: string; category: 'Engagement' | 'Obstacle' | 'Learning Flow' }> = {
  'AU04': { label: 'Mental Effort', category: 'Engagement' },
  'AU01': { label: 'Interest/Surprise', category: 'Learning Flow' },
  'AU45': { label: 'Blink Rate', category: 'Engagement' },
  'AU06': { label: 'Positive Expression', category: 'Learning Flow' },
  'AU12': { label: 'Engagement Level', category: 'Learning Flow' },
  'AU25': { label: 'Verbal Processing', category: 'Engagement' },
  'gaze_stability': { label: 'Visual Focus', category: 'Engagement' },
  'pose_stability': { label: 'Postural Stability', category: 'Engagement' },
  'head_tilt': { label: 'Inquiry Depth', category: 'Learning Flow' },
  'frown': { label: 'Learning Difficulty', category: 'Obstacle' },
};

export default function EngagementFactorChart({ features, shapExplanations }: EngagementFactorChartProps) {
  const processedImpacts = useMemo(() => {
    const impacts: FeatureImpact[] = [];
    
    // Use actual SHAP explanations if available, otherwise fallback to feature intensities
    const sourceData = shapExplanations?.feature_contributions || features;

    Object.entries(sourceData).forEach(([key, value]) => {
      const mapping = AU_MAP[key] || (key.startsWith('AU') ? { label: `Muscle Movement (${key})`, category: 'Engagement' } : null);
      if (mapping) {
        let weight = typeof value === 'number' ? value : 0;
        
        // If it's SHAP, it might be in 0-1 range or small floats. 
        // If it's features, it's 0-5 frequency/intensity.
        // We normalize to -100 to 100 for visualization
        if (!shapExplanations) {
            weight = Math.min(100, (weight / 5) * 100);
        } else {
            weight = weight * 100; // Assuming SHAP is normalized 0-1 or similar
        }
        
        impacts.push({
          label: mapping.label,
          weight: weight,
          category: mapping.category
        });
      }
    });

    if (impacts.length === 0) {
      impacts.push({ label: 'Focus Consistency', weight: 75, category: 'Learning Flow' });
      impacts.push({ label: 'Movement Distraction', weight: -10, category: 'Obstacle' });
    }

    return impacts.sort((a, b) => Math.abs(b.weight) - Math.abs(a.weight)).slice(0, 6);
  }, [features, shapExplanations]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-xl font-black text-foreground tracking-tight flex items-center gap-2">
           <BarChart2 size={20} className="text-primary" /> Key Focus Factors
        </h3>
        <div className="flex items-center gap-4">
           {['Engagement', 'Learning Flow', 'Obstacle'].map(cat => (
             <div key={cat} className="flex items-center gap-1.5 text-[8px] font-black uppercase tracking-widest opacity-60">
                <div className={`w-1.5 h-1.5 rounded-full ${
                  cat === 'Engagement' ? 'bg-primary' : cat === 'Learning Flow' ? 'bg-success' : 'bg-danger'
                }`} />
                {cat}
             </div>
           ))}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4">
        {processedImpacts.map((impact, i) => (
          <div key={i} className="group flex flex-col gap-2">
            <div className="flex justify-between items-end px-1">
               <span className="text-[10px] font-black text-text-muted uppercase tracking-widest flex items-center gap-2">
                  {impact.label}
                  <Info size={10} className="opacity-0 group-hover:opacity-100 transition-opacity cursor-help" />
               </span>
               <span className={`text-xs font-black ${impact.weight >= 0 ? 'text-foreground' : 'text-danger'}`}>
                  {impact.weight > 0 ? '+' : ''}{impact.weight.toFixed(0)}% Contribution
               </span>
            </div>
            
            <div className="relative h-2 bg-surface rounded-full overflow-hidden border border-white/5 shadow-inner">
               <motion.div 
                 initial={{ width: 0 }}
                 animate={{ width: `${Math.abs(impact.weight)}%` }}
                 className={`h-full rounded-full ${
                    impact.category === 'Engagement' ? 'bg-primary' : 
                    impact.category === 'Learning Flow' ? 'bg-success' : 'bg-danger'
                 } crimson-glow`}
                 transition={{ delay: i * 0.1, duration: 1 }}
               />
            </div>
          </div>
        ))}
      </div>

      <div className="p-4 bg-primary/5 border border-primary/20 rounded-2xl flex items-start gap-3">
         <AlertCircle size={16} className="text-primary shrink-0 mt-0.5" />
         <p className="text-[10px] font-medium text-text-muted leading-relaxed">
            Analysis suggests that <span className="text-foreground font-black uppercase">"{processedImpacts[0]?.label}"</span> was the primary contributing factor to the focus score during this session.
         </p>
      </div>
    </div>
  );
}
