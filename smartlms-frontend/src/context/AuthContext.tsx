'use client';

import React, { createContext, useContext, useState, useEffect } from 'react';
import { authAPI } from '@/lib/api';

interface User {
  id: string;
  full_name: string;
  email: string;
  role: 'student' | 'teacher' | 'admin';
  avatar_url?: string;
  [key: string]: any;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  loading: boolean;
  login: (credentials: any) => Promise<User>;
  googleLogin: (token: string, role?: string, intent?: 'login' | 'register') => Promise<User>;
  register: (credentials: any) => Promise<User>;
  logout: () => void;
  updateUser: (updates: Partial<User>) => void;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Initial token load from local storage
    const storedToken = localStorage.getItem('token');
    const storedUser = localStorage.getItem('user');

    if (storedToken) {
      setToken(storedToken);
      if (storedUser) {
        try {
          setUser(JSON.parse(storedUser));
        } catch (e) {
          console.error('Failed to parse stored user', e);
        }
      }
      
      // Verify token/Fetch fresh profile
      authAPI.getProfile()
        .then(res => {
          const userData = res.data;
          setUser(userData);
          localStorage.setItem('user', JSON.stringify(userData));
        })
        .catch(() => {
          logout();
        })
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  const login = async (credentials: any) => {
    const res = await authAPI.login(credentials);
    const { access_token, user: userData } = res.data;
    localStorage.setItem('token', access_token);
    localStorage.setItem('user', JSON.stringify(userData));
    setToken(access_token);
    setUser(userData);
    return userData;
  };

  const register = async (credentials: any) => {
    const res = await authAPI.register(credentials);
    const { access_token, user: userData } = res.data;
    localStorage.setItem('token', access_token);
    localStorage.setItem('user', JSON.stringify(userData));
    setToken(access_token);
    setUser(userData);
    return userData;
  };

  const googleLogin = async (id_token: string, role?: string, intent: 'login' | 'register' = 'login') => {
    setLoading(true);
    let lastError: any = null;
    const maxRetries = 2;

    for (let attempt = 0; attempt <= maxRetries; attempt++) {
      try {
        const res = await authAPI.googleLogin({ id_token, role, intent });
        const { access_token, user: userData } = res.data;
        
        localStorage.setItem('token', access_token);
        localStorage.setItem('user', JSON.stringify(userData));
        setToken(access_token);
        setUser(userData);
        setLoading(false);
        return userData;
      } catch (err: any) {
        lastError = err;
        console.warn(`Google login attempt ${attempt + 1} failed:`, err);
        
        // Only retry on potential server issues (5xx) or network errors
        const isRetryable = !err.response || err.response.status >= 500;
        if (!isRetryable || attempt === maxRetries) {
          setLoading(false);
          throw err;
        }
        
        // Wait 1s before retry
        await new Promise(resolve => setTimeout(resolve, 1000));
      }
    }
    
    setLoading(false);
    throw lastError;
  };

  const logout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    setToken(null);
    setUser(null);
    window.location.href = '/login';
  };

  const updateUser = (updates: Partial<User>) => {
    setUser(prev => prev ? ({ ...prev, ...updates }) : null);
    if (user) {
      localStorage.setItem('user', JSON.stringify({ ...user, ...updates }));
    }
  };

  return (
    <AuthContext.Provider value={{ user, token, loading, login, googleLogin, register, logout, updateUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within AuthProvider');
  return context;
}
