import React, { useMemo, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Info, BarChart2, AlertCircle, TrendingUp, LayoutGrid } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';

interface FeatureImpact {
  label: string;
  weight: number; 
  category: 'Engagement' | 'Obstacle' | 'Learning Flow';
  key: string;
}

interface EngagementFactorChartProps {
  features: Record<string, any>;
  shapExplanations?: Record<string, any>;
  timeline?: any[]; // Pass feature_timeline here
}

// ... existing AU_MAP ...

// ... existing AU_MAP ...
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

export default function EngagementFactorChart({ features, shapExplanations, timeline }: EngagementFactorChartProps) {
  const [view, setView] = useState<'bars' | 'trend'>('bars');

  const processedImpacts = useMemo(() => {
    const impacts: FeatureImpact[] = [];
    const sourceData = shapExplanations?.feature_contributions || features;

    Object.entries(sourceData).forEach(([key, value]) => {
      const mapping = AU_MAP[key] || (key.startsWith('AU') ? { label: `Muscle Movement (${key})`, category: 'Engagement' } : null);
      if (mapping) {
        let weight = typeof value === 'number' ? value : 0;
        if (!shapExplanations) {
            weight = Math.min(100, (weight / 5) * 100);
        } else {
            weight = weight * 100;
        }
        
        impacts.push({
          key,
          label: mapping.label,
          weight: weight,
          category: mapping.category
        });
      }
    });

    if (impacts.length === 0) {
      impacts.push({ key: 'focus', label: 'Focus Consistency', weight: 75, category: 'Learning Flow' });
      impacts.push({ key: 'distraction', label: 'Movement Distraction', weight: -10, category: 'Obstacle' });
    }

    return impacts.sort((a, b) => Math.abs(b.weight) - Math.abs(a.weight)).slice(0, 6);
  }, [features, shapExplanations]);

  const trendData = useMemo(() => {
    if (!timeline) return [];
    return timeline.map((point, i) => {
      const p: any = { timestamp: point.timestamp || i };
      processedImpacts.forEach(impact => {
         p[impact.label] = point[impact.key] || 0;
      });
      return p;
    });
  }, [timeline, processedImpacts]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-xl font-black text-foreground tracking-tight flex items-center gap-2 uppercase italic">
           <BarChart2 size={20} className="text-primary" /> Pedagogical Predictors
        </h3>
        
        <div className="flex bg-surface-alt p-1 rounded-xl border border-white/5">
           <button 
             onClick={() => setView('bars')}
             className={`p-1.5 rounded-lg transition-all ${view === 'bars' ? 'bg-primary text-white shadow-lg' : 'text-text-muted hover:text-foreground'}`}
           >
             <LayoutGrid size={14} />
           </button>
           <button 
             onClick={() => setView('trend')}
             className={`p-1.5 rounded-lg transition-all ${view === 'trend' ? 'bg-primary text-white shadow-lg' : 'text-text-muted hover:text-foreground'}`}
           >
             <TrendingUp size={14} />
           </button>
        </div>
      </div>

      <AnimatePresence mode="wait">
        {view === 'bars' ? (
          <motion.div 
            key="bars"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="grid grid-cols-1 gap-4"
          >
            {processedImpacts.map((impact, i) => (
              <div key={i} className="group flex flex-col gap-2">
                <div className="flex justify-between items-end px-1">
                   <span className="text-[10px] font-black text-text-muted uppercase tracking-widest flex items-center gap-2">
                      {impact.label}
                   </span>
                   <span className={`text-xs font-black ${impact.weight >= 0 ? 'text-foreground' : 'text-danger'}`}>
                      {impact.weight > 0 ? '+' : ''}{impact.weight.toFixed(0)}%
                   </span>
                </div>
                <div className="relative h-2 bg-surface rounded-full overflow-hidden border border-white/5">
                   <motion.div 
                     initial={{ width: 0 }}
                     animate={{ width: `${Math.abs(impact.weight)}%` }}
                     className={`h-full rounded-full ${
                        impact.category === 'Engagement' ? 'bg-primary' : 
                        impact.category === 'Learning Flow' ? 'bg-success' : 'bg-danger'
                     } crimson-glow`}
                   />
                </div>
              </div>
            ))}
          </motion.div>
        ) : (
          <motion.div 
            key="trend"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="h-[240px] w-full bg-surface-alt/50 rounded-2xl border border-white/5 p-4"
          >
            {timeline ? (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={trendData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#ffffff05" vertical={false} />
                  <XAxis dataKey="timestamp" hide />
                  <YAxis hide domain={[0, 'auto']} />
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#111', border: 'none', borderRadius: '12px', fontSize: '10px' }}
                    itemStyle={{ fontWeight: 'bold' }}
                  />
                  {processedImpacts.map((impact, i) => (
                    <Line 
                      key={impact.label} 
                      type="monotone" 
                      dataKey={impact.label} 
                      stroke={impact.category === 'Engagement' ? '#CC3344' : impact.category === 'Learning Flow' ? '#33CC99' : '#FFBB33'} 
                      strokeWidth={2}
                      dot={false}
                    />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center text-[10px] font-black uppercase text-text-muted tracking-widest opacity-30">
                 Timeline data sync in progress...
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      <div className="p-4 bg-primary/5 border border-primary/20 rounded-2xl flex items-start gap-3">
         <AlertCircle size={16} className="text-primary shrink-0 mt-0.5" />
         <p className="text-[10px] font-medium text-text-muted leading-relaxed">
            {view === 'bars' 
              ? `Educational impact profile identifies "${processedImpacts[0]?.label}" as the primary driver for this student.`
              : "Engagement rhythm visualization identifies fluctuations in concentrated processing during the session."}
         </p>
      </div>
    </div>
  );
}
