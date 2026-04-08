"use client";

import React, { useEffect, useState } from 'react';
import { 
  BarChart3, 
  TrendingUp, 
  Info, 
  Search, 
  Filter, 
  ArrowUpRight, 
  CheckCircle2, 
  AlertCircle,
  HelpCircle,
  ScatterChart as ScatterIcon,
  Zap
} from 'lucide-react';
import { adminAPI } from '@/lib/api';
import { 
  ScatterChart, 
  Scatter, 
  XAxis, 
  YAxis, 
  ZAxis,
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  Cell,
  ReferenceLine,
  Label
} from 'recharts';

export default function CorrelationPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');

  useEffect(() => {
    const fetchData = async () => {
      try {
        const result = await adminAPI.getEngagementCorrelation();
        setData(result.data);
      } catch (err) {
        console.error('Failed to fetch correlation data:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const filteredPoints = data?.data_points?.filter((p: any) => 
    p.student_name.toLowerCase().includes(searchTerm.toLowerCase())
  ) || [];

  if (loading) return (
    <div className="flex items-center justify-center h-96">
      <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
    </div>
  );

  return (
    <div className="space-y-8 animate-in slide-in-from-bottom duration-700">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-white mb-2 flex items-center gap-2">
            <ScatterIcon className="w-8 h-8 text-blue-500" />
            Predicted vs. Actual Engagement
          </h1>
          <p className="text-slate-400">Validating XGBoost telemetry against real-world performance metrics</p>
        </div>
        
        <div className="bg-slate-900 border border-slate-800 p-1 rounded-2xl flex items-center gap-1 shadow-inner">
          <button className="px-4 py-2 bg-blue-600 rounded-xl text-sm font-bold text-white shadow-lg">Global</button>
          <button className="px-4 py-2 hover:bg-slate-800 rounded-xl text-sm font-bold text-slate-500 transition-colors">By Course</button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
        {/* Main Chart Card */}
        <div className="lg:col-span-3 space-y-6">
          <div className="bg-slate-900/50 backdrop-blur-xl border border-slate-800 rounded-3xl p-8 shadow-2xl relative overflow-hidden">
            <div className="absolute top-0 right-0 p-8">
              <Zap className="w-32 h-32 text-blue-500/10" />
            </div>
            
            <div className="flex items-center justify-between mb-10 relative z-10">
              <div>
                <h3 className="text-xl font-bold text-white mb-1">Correlation Matrix</h3>
                <p className="text-sm text-slate-500">Each node represents a student's cognitive resonance profile</p>
              </div>
              <div className="flex items-center gap-6 text-sm">
                <div className="flex items-center gap-2">
                  <span className="w-3 h-3 rounded-full bg-blue-500 shadow-md shadow-blue-500/50"></span>
                  <span className="text-slate-400">High Confidence</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="w-3 h-3 rounded-full bg-amber-500 shadow-md shadow-amber-500/50"></span>
                  <span className="text-slate-400">Potential Anomaly</span>
                </div>
              </div>
            </div>
            
            <div className="h-[500px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" opacity={0.5} />
                  <XAxis 
                    type="number" 
                    dataKey="predicted_engagement" 
                    name="Predicted" 
                    unit="%" 
                    stroke="#64748b" 
                    domain={[0, 100]}
                    tickLine={false}
                    axisLine={false}
                  >
                    <Label value="ML Predicted Engagement" position="bottom" offset={0} fill="#94a3b8" style={{ fontSize: '12px', fontWeight: 'bold' }} />
                  </XAxis>
                  <YAxis 
                    type="number" 
                    dataKey="actual_performance" 
                    name="Performance" 
                    unit="%" 
                    stroke="#64748b" 
                    domain={[0, 100]}
                    tickLine={false}
                    axisLine={false}
                  >
                    <Label value="Actual Quiz Score" angle={-90} position="left" offset={0} fill="#94a3b8" style={{ fontSize: '12px', fontWeight: 'bold' }} />
                  </YAxis>
                  <ZAxis type="number" dataKey="delta" range={[60, 400]} />
                  <Tooltip 
                    cursor={{ strokeDasharray: '3 3', stroke: '#3b82f6' }}
                    content={({ active, payload }) => {
                      if (active && payload && payload.length) {
                        const p = payload[0].payload;
                        return (
                          <div className="bg-slate-950 border border-slate-700 p-4 rounded-2xl shadow-2xl animate-in zoom-in duration-200">
                            <p className="text-blue-400 font-bold mb-1">{p.student_name}</p>
                            <div className="space-y-1 text-xs">
                              <p className="flex justify-between gap-4"><span className="text-slate-500 uppercase tracking-tighter">Predicted</span> <span className="text-slate-200">{p.predicted_engagement}%</span></p>
                              <p className="flex justify-between gap-4"><span className="text-slate-500 uppercase tracking-tighter">Actual</span> <span className="text-slate-200">{p.actual_performance}%</span></p>
                              <div className="mt-2 pt-2 border-t border-slate-800">
                                <p className="flex justify-between gap-6"><span className="text-slate-500 uppercase tracking-tighter">Performance Delta</span> <span className={p.delta >= 0 ? 'text-emerald-400' : 'text-red-400'}>{p.delta}%</span></p>
                              </div>
                            </div>
                          </div>
                        );
                      }
                      return null;
                    }}
                  />
                  {/* Performance Target Line */}
                  <ReferenceLine x={75} stroke="#1e293b" />
                  <ReferenceLine y={75} stroke="#1e293b" />
                  <Scatter name="Students" data={filteredPoints}>
                    {filteredPoints.map((entry: any, index: number) => (
                      <Cell key={`cell-${index}`} fill={Math.abs(entry.delta) < 15 ? '#3b82f6' : '#f59e0b'} fillOpacity={0.7} strokeWidth={2} stroke={Math.abs(entry.delta) < 15 ? '#60a5fa' : '#fbbf24'} />
                    ))}
                  </Scatter>
                </ScatterChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Student Grid */}
          <div className="bg-slate-900/50 backdrop-blur-xl border border-slate-800 rounded-3xl p-6 shadow-2xl">
            <div className="flex items-center justify-between mb-8 gap-4 px-2">
              <div className="relative flex-1 max-w-sm">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                <input 
                  type="text" 
                  placeholder="Search students..." 
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl py-2 pl-10 pr-4 text-sm focus:outline-none focus:border-blue-500/50 transition-colors"
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                />
              </div>
              <div className="flex items-center gap-2">
                <button className="p-2 bg-slate-950 border border-slate-800 rounded-xl text-slate-500 hover:text-slate-300 transition-colors">
                  <Filter className="w-4 h-4" />
                </button>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
              {filteredPoints.map((point: any) => (
                <div key={point.student_id} className="bg-slate-950/50 border border-slate-800/50 rounded-2xl p-5 hover:border-slate-700 transition-all group">
                   <div className="flex justify-between items-start mb-4">
                      <div>
                        <h4 className="font-bold text-white group-hover:text-blue-400 transition-colors">{point.student_name}</h4>
                        <p className="text-xs text-slate-500">ID: {point.student_id.slice(0, 8)}</p>
                      </div>
                      <div className={`p-2 rounded-lg ${Math.abs(point.delta) < 15 ? 'bg-emerald-500/10' : 'bg-amber-500/10'}`}>
                        {Math.abs(point.delta) < 15 ? <CheckCircle2 className="w-4 h-4 text-emerald-500" /> : <AlertCircle className="w-4 h-4 text-amber-500" />}
                      </div>
                   </div>
                   
                   <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-1">
                        <p className="text-[10px] uppercase font-bold text-slate-600 tracking-widest">Predicted</p>
                        <p className="text-lg font-bold text-slate-300">{point.predicted_engagement}%</p>
                      </div>
                      <div className="space-y-1 text-right">
                        <p className="text-[10px] uppercase font-bold text-slate-600 tracking-widest">Actual</p>
                        <p className="text-lg font-bold text-slate-300">{point.actual_performance}%</p>
                      </div>
                   </div>
                   
                   <div className="mt-4 pt-4 border-t border-slate-800 flex items-center justify-between">
                     <span className="text-[10px] uppercase font-bold text-slate-500 tracking-widest">Performance Delta</span>
                     <span className={`text-sm font-black ${point.delta >= 0 ? 'text-emerald-500' : 'text-red-500'}`}>
                        {point.delta > 0 ? '+' : ''}{point.delta}%
                     </span>
                   </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Sidebar Info */}
        <div className="space-y-8">
          <div className="bg-blue-600 rounded-3xl p-6 shadow-xl shadow-blue-500/20 relative overflow-hidden">
            <BarChart3 className="absolute -bottom-4 -right-4 w-24 h-24 text-white/10" />
            <h3 className="text-xl font-bold text-white mb-2">Platform Delta</h3>
            <div className="text-4xl font-black text-white mb-1">
              {data?.avg_delta > 0 ? '+' : ''}{data?.avg_delta || 0}%
            </div>
            <p className="text-blue-100 text-sm leading-relaxed">Global performance deviation from predicted engagement mean.</p>
            
            <div className="mt-8 flex items-center gap-2 text-xs font-bold text-blue-900 bg-white/20 backdrop-blur-md px-3 py-2 rounded-xl w-fit">
              <TrendingUp className="w-4 h-4" />
              SYSTEM OPTIMIZED
            </div>
          </div>

          <div className="bg-slate-900/50 backdrop-blur-xl border border-slate-800 rounded-3xl p-6 shadow-2xl">
            <h3 className="text-lg font-bold text-white mb-6 flex items-center gap-2">
              <HelpCircle className="w-5 h-5 text-slate-400" />
              Interpreting the Data
            </h3>
            <div className="space-y-6">
              <div className="space-y-2">
                <p className="text-xs font-bold text-blue-400 uppercase tracking-widest">High Correlation (Blue)</p>
                <p className="text-sm text-slate-400 leading-relaxed">Engagement telemetry accurately predicted the quiz outcome (within 15%). These models are performing perfectly.</p>
              </div>
              <div className="space-y-2 pt-2">
                <p className="text-xs font-bold text-amber-400 uppercase tracking-widest">Negative Delta (Red)</p>
                <p className="text-sm text-slate-400 leading-relaxed">Student appeared engaged during lecture but failed the quiz. Indicates potential 'Superficial Engagement' or content difficulty issues.</p>
              </div>
              <div className="space-y-2 pt-2 text-slate-500 opacity-60">
                <p className="text-xs font-bold uppercase tracking-widest flex items-center gap-2 underline decoration-slate-500 decoration-2 underline-offset-4">
                  Forensic Deep Dive
                </p>
                <p className="text-xs italic">Click any student node to view raw ICAP evidence logs (chats, notes, activity) for that session.</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
