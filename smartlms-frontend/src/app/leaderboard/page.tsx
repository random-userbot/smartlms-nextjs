'use client';

import React, { useState, useEffect } from 'react';
import Sidebar from '@/components/Sidebar';
import { gamificationAPI } from '@/lib/api';
import { 
  Trophy, 
  Medal, 
  Zap, 
  Target, 
  TrendingUp, 
  Crown,
  Search,
  Filter,
  ArrowUpRight,
  Sparkles
} from 'lucide-react';
import { useAuth } from '@/context/AuthContext';

import NavigationHeader from '@/components/NavigationHeader';

export default function LeaderboardPage() {
  const [leaderboard, setLeaderboard] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const { user } = useAuth();

  useEffect(() => {
    gamificationAPI.getLeaderboard().then(res => {
      setLeaderboard(Array.isArray(res.data) ? res.data : []);
    }).finally(() => setLoading(false));
  }, []);

  const topThree = leaderboard.slice(0, 3);
  const remaining = leaderboard.slice(3);

  if (loading) return (
    <div className="flex min-h-screen bg-background">
      <Sidebar />
      <main className="flex-1 ml-64 p-12 flex items-center justify-center">
        <div className="w-12 h-12 border-4 border-primary/20 border-t-primary rounded-full animate-spin"></div>
      </main>
    </div>
  );

  const totalPoints = leaderboard.reduce((acc, p) => acc + (p.points || 0), 0);

  return (
    <div className="flex h-screen bg-background overflow-hidden font-sans text-foreground">
      <Sidebar />
      <main className="flex-1 ml-64 flex flex-col p-12 gap-12 overflow-y-auto custom-scrollbar animate-fade-in">
        
        <NavigationHeader 
          title="Global Leaderboard"
          subtitle="Scholar Rankings & Achievements"
        />

        {/* Podium Section */}
        <div className="grid grid-cols-3 gap-8 items-end max-w-5xl mx-auto w-full pt-12">
           {/* Rank 2 */}
           {topThree[1] && (
             <div className="glass-card p-8 text-center space-y-6 border-border order-1 relative group hover:border-slate-400/50 transition-all">
                <div className="w-20 h-20 rounded-full border-4 border-slate-400/20 mx-auto relative group-hover:scale-110 transition-transform">
                   <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-slate-400 text-white rounded-full p-1 border-2 border-surface">
                     <Medal size={16} />
                   </div>
                   <div className="w-full h-full rounded-full flex items-center justify-center bg-surface-alt font-black text-2xl text-foreground">
                     {(topThree[1]?.full_name || "S")?.charAt(0)}
                   </div>
                </div>
                <div>
                   <h3 className="text-xl font-black text-foreground truncate">{topThree[1]?.full_name || "Secret Scholar"}</h3>
                   <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Silver Tier</p>
                </div>
                <div className="text-2xl font-black text-foreground italic">{(topThree[1]?.points ?? 0).toLocaleString()} <span className="text-sm font-bold text-text-muted not-italic">XP</span></div>
             </div>
           )}

           {/* Rank 1 (Tallest) */}
           {topThree[0] && (
             <div className="glass-card p-12 text-center space-y-8 border-primary/20 crimson-glow order-2 scale-110 relative z-10 group hover:border-primary/40 transition-all">
                <div className="absolute -top-6 left-1/2 -translate-x-1/2 bg-primary text-white rounded-full p-2 border-4 border-surface shadow-2xl animate-bounce duration-[2000ms]">
                   <Crown size={24} />
                </div>
                <div className="w-28 h-28 rounded-full border-4 border-primary/40 mx-auto relative bg-gradient-to-tr from-primary/20 to-transparent group-hover:scale-110 transition-transform">
                   <div className="w-full h-full rounded-full flex items-center justify-center bg-surface-alt font-black text-4xl text-foreground">
                      {(topThree[0]?.full_name || "G")?.charAt(0)}
                   </div>
                </div>
                <div>
                   <h3 className="text-2xl font-black text-foreground truncate">{topThree[0]?.full_name || "Grand Scholar"}</h3>
                   <p className="text-[10px] font-black text-primary uppercase tracking-widest flex items-center justify-center gap-2">
                     <Sparkles size={10} /> Grandmaster Tier <Sparkles size={10} />
                   </p>
                </div>
                <div className="text-4xl font-black text-foreground italic shimmer">{(topThree[0]?.points ?? 0).toLocaleString()} <span className="text-sm font-bold text-text-muted not-italic">XP</span></div>
             </div>
           )}

           {/* Rank 3 */}
           {topThree[2] && (
             <div className="glass-card p-8 text-center space-y-6 border-border order-3 relative group hover:border-orange-700/50 transition-all">
                <div className="w-20 h-20 rounded-full border-4 border-orange-700/20 mx-auto relative group-hover:scale-110 transition-transform">
                   <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-orange-700 text-white rounded-full p-1 border-2 border-surface">
                     <Medal size={16} />
                   </div>
                   <div className="w-full h-full rounded-full flex items-center justify-center bg-surface-alt font-black text-2xl text-foreground">
                     {(topThree[2]?.full_name || "B")?.charAt(0)}
                   </div>
                </div>
                <div>
                   <h3 className="text-xl font-black text-foreground truncate">{topThree[2]?.full_name || "Rising Scholar"}</h3>
                   <p className="text-[10px] font-black text-orange-800 uppercase tracking-widest">Bronze Tier</p>
                </div>
                <div className="text-2xl font-black text-foreground italic">{(topThree[2]?.points ?? 0).toLocaleString()} <span className="text-sm font-bold text-text-muted not-italic">XP</span></div>
             </div>
           )}
        </div>

        {/* List Section */}
        <div className="glass-card overflow-hidden border-border bg-surface shadow-2xl">
           <table className="w-full text-left font-sans">
              <thead className="bg-surface-alt border-b border-border">
                 <tr>
                    <th className="px-8 py-6 text-[10px] font-black text-text-muted uppercase tracking-widest">Position</th>
                    <th className="px-8 py-6 text-[10px] font-black text-text-muted uppercase tracking-widest">Scholar</th>
                    <th className="px-8 py-6 text-[10px] font-black text-text-muted uppercase tracking-widest">Level</th>
                    <th className="px-8 py-6 text-right text-[10px] font-black text-text-muted uppercase tracking-widest">Total XP</th>
                 </tr>
              </thead>
              <tbody className="divide-y divide-border">
                 {remaining.map((player, idx) => {
                   const isMe = player.id === user?.id;
                   return (
                      <tr key={idx} className={`group hover:bg-primary/5 transition-colors ${isMe ? 'bg-primary/5 border-l-4 border-l-primary' : ''}`}>
                         <td className="px-8 py-6">
                            <div className="text-xl font-black text-text-muted/40 group-hover:text-primary transition-colors">#{idx + 4}</div>
                         </td>
                         <td className="px-8 py-6">
                            <div className="flex items-center gap-4">
                               <div className="w-10 h-10 rounded-full bg-surface-alt flex items-center justify-center font-black text-foreground text-xs border border-border group-hover:crimson-glow">
                                 {player.full_name?.charAt(0)}
                               </div>
                               <div className="font-black text-foreground text-sm flex items-center gap-2">
                                 {player.full_name} {isMe && <span className="text-[8px] bg-primary text-white px-2 py-0.5 rounded-lg flex items-center gap-1 shadow-lg shadow-primary/20"><Sparkles size={8} /> YOU</span>}
                               </div>
                            </div>
                         </td>
                        <td className="px-8 py-6">
                           <span className="px-4 py-1 bg-surface-alt border border-border rounded-xl text-[10px] font-black text-text-muted uppercase tracking-widest group-hover:border-primary/20 group-hover:text-primary transition-colors">
                              Level {player.level || 1}
                           </span>
                        </td>
                         <td className="px-8 py-6 text-right">
                            <div className="text-lg font-black text-foreground italic">{(player.points || 0).toLocaleString()}</div>
                         </td>
                      </tr>
                   );
                 })}
                 {remaining.length === 0 && (
                   <tr>
                     <td colSpan={4} className="px-8 py-12 text-center text-text-muted font-bold">
                        No additional scholars ranked yet. Start learning to climb the ranks!
                     </td>
                   </tr>
                 )}
              </tbody>
           </table>
        </div>

        {/* Global Stats Footer */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
           {[
             { label: 'Cumulative Community XP', val: totalPoints.toLocaleString(), icon: Zap },
             { label: 'Active Scholars', val: leaderboard.length, icon: Target },
             { label: 'Network Stability', val: '99.9%', icon: TrendingUp },
           ].map((stat, i) => (
             <div key={i} className="glass-card p-8 flex flex-col gap-4 border-border bg-surface hover:border-primary/20 transition-all group">
                <div className="flex items-center justify-between">
                   <div className="text-[10px] font-black text-text-muted uppercase tracking-widest">{stat.label}</div>
                   <div className="p-2 bg-primary/5 rounded-lg text-primary group-hover:bg-primary group-hover:text-white transition-all">
                    <stat.icon size={16} />
                   </div>
                </div>
                <div className="text-4xl font-black text-foreground tracking-tighter">{stat.val}</div>
             </div>
           ))}
        </div>

      </main>
    </div>
  );
}
