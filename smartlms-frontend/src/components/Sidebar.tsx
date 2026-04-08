'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { 
  BarChart3, 
  BookOpen, 
  Activity, 
  Bot, 
  Award, 
  LayoutDashboard,
  Settings,
  LogOut,
  ChevronRight,
  Sparkles,
  Bell,
  ArrowLeft,
  ArrowRight,
  Zap
} from 'lucide-react';
import { useAuth } from '@/context/AuthContext';
import { useTheme } from '@/context/ThemeContext';
import { Sun, Moon } from 'lucide-react';

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();

  const getNavItems = () => {
    const baseItems = [
      { name: 'Dashboard', icon: LayoutDashboard, href: '/dashboard' },
      { name: 'Messages', icon: Bot, href: '/messages', count: 0 },
      { name: 'Notifications', icon: Bell, href: '/notifications', count: 0 },
    ];

    if (user?.role === 'student') {
      return [
        ...baseItems,
        { name: 'My Courses', icon: BookOpen, href: '/courses' },
        { name: 'Assignments', icon: Award, href: '/assignments', count: 0 },
        { name: 'Quizzes', icon: Zap, href: '/quizzes', count: 0 },
        { name: 'AI Sensei', icon: Sparkles, href: '/ai-tutor', count: 0 },
        { name: 'Analytics', icon: BarChart3, href: '/analytics', count: 0 },
        { name: 'Leaderboard', icon: Award, href: '/leaderboard', count: 0 },
      ];
    }

    if (user?.role === 'teacher' || user?.role === 'admin') {
      const teacherItems = [
        ...baseItems,
        { name: 'My Courses', icon: BookOpen, href: '/teacher/courses', count: 0 },
        { name: 'Quizzes', icon: Sparkles, href: '/teacher/quizzes', count: 0 },
        { name: 'Grading', icon: Award, href: '/teacher/assignments', count: 0 },
        { name: 'Analytics', icon: BarChart3, href: '/teacher/analytics', count: 0 },
      ];

      if (user?.role === 'admin') {
        teacherItems.push({ name: 'Admin Panel', icon: Settings, href: '/admin', count: 0 });
      }

      return teacherItems;
    }

    return baseItems;
  };

  const navItems = getNavItems();

  return (
    <aside className="w-64 h-screen bg-surface border-r border-border flex flex-col fixed left-0 top-0 z-50 transition-colors duration-300">
      <div className="p-8 space-y-6">
        <div className="text-2xl font-black tracking-tighter text-foreground flex items-center gap-2">
          <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center crimson-glow text-lg text-white">S</div>
          SmartLMS
        </div>
      </div>

      <nav className="flex-1 px-4 space-y-2 mt-4 overflow-y-auto">
        {navItems.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.name}
              href={item.href}
              className={`flex items-center justify-between px-4 py-3 rounded-2xl transition-all group ${
                isActive 
                ? 'bg-primary text-white crimson-glow' 
                : 'text-text-muted hover:bg-primary/5 hover:text-primary'
              }`}
            >
              <div className="flex items-center gap-3">
                <item.icon size={20} className={isActive ? 'text-white' : 'text-primary'} />
                <span className="font-bold text-sm tracking-tight">{item.name}</span>
              </div>
              <div className="flex items-center gap-2">
                {item.count !== undefined && item.count > 0 && (
                  <span className="w-5 h-5 bg-primary text-white text-[10px] font-black rounded-full flex items-center justify-center">
                    {item.count}
                  </span>
                )}
                <ChevronRight size={16} className={`transition-transform group-hover:translate-x-1 ${isActive ? 'block' : 'hidden'}`} />
              </div>
            </Link>
          );
        })}
      </nav>

      <div className="p-6 border-t border-border mt-auto space-y-4">
        {user && (
          <div className="flex items-center gap-3 p-3 bg-surface-alt rounded-2xl border border-border">
            <div className="w-10 h-10 bg-surface rounded-full flex items-center justify-center font-black text-primary border border-primary/20">
              {user.full_name?.charAt(0) || '?'}
            </div>
            <div className="overflow-hidden">
              <div className="text-sm font-black text-foreground truncate">{user.full_name}</div>
              <div className="text-[10px] font-bold text-primary uppercase tracking-widest">{user.role}</div>
            </div>
          </div>
        )}

        <button 
          onClick={toggleTheme}
          className="w-full flex items-center gap-3 px-4 py-3 text-text-muted hover:text-primary transition-colors font-bold text-sm bg-surface-alt rounded-2xl border border-border group"
        >
          {theme === 'dark' ? (
            <>
              <Sun size={18} className="text-primary group-hover:rotate-45 transition-transform" />
              Light Mode
            </>
          ) : (
            <>
              <Moon size={18} className="text-primary group-hover:-rotate-12 transition-transform" />
              Dark Mode
            </>
          )}
        </button>

        <button 
          onClick={logout}
          className="w-full flex items-center gap-3 px-4 py-3 text-text-muted hover:text-primary transition-colors font-bold text-sm"
        >
          <LogOut size={18} />
          Sign Out
        </button>
      </div>
    </aside>
  );
}
