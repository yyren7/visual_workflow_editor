import React, { createContext, useContext, useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000';

interface AuthContextType {
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (token: string) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | null>(null);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(true); // 添加加载状态
  const navigate = useNavigate();

  // 验证token有效性的函数
  const verifyToken = async (token: string): Promise<boolean> => {
    if (!token) return false;

    try {
      const response = await axios.get(`${API_BASE_URL}/auth/verify-token`, {
        headers: {
          Authorization: `Bearer ${token}`
        }
      });

      return response.status === 200;
    } catch (error) {
      console.error('Token验证失败:', error);
      return false;
    }
  };

  // 登录函数
  const login = (token: string) => {
    localStorage.setItem('access_token', token);
    setIsAuthenticated(true);
  };

  // 登出函数 - 只在这一个地方处理导航
  const logout = () => {
    localStorage.removeItem('access_token');
    setIsAuthenticated(false);
    navigate('/login', { replace: true });
  };

  // 初始加载时验证token
  useEffect(() => {
    const initAuth = async () => {
      setIsLoading(true);
      const token = localStorage.getItem('access_token');
      
      if (token) {
        const isValid = await verifyToken(token);
        
        if (isValid) {
          setIsAuthenticated(true);
        } else {
          localStorage.removeItem('access_token');
          setIsAuthenticated(false);
        }
      } else {
        setIsAuthenticated(false);
      }
      
      setIsLoading(false);
    };
    
    initAuth();
  }, []);

  // 监听本地存储变化
  useEffect(() => {
    const checkAuth = async () => {
      const token = localStorage.getItem('access_token');
      
      if (token) {
        const isValid = await verifyToken(token);
        setIsAuthenticated(isValid);
        
        if (!isValid) {
          localStorage.removeItem('access_token');
        }
      } else {
        setIsAuthenticated(false);
      }
    };
    
    window.addEventListener('storage', checkAuth);
    window.addEventListener('loginChange', checkAuth);
    
    return () => {
      window.removeEventListener('storage', checkAuth);
      window.removeEventListener('loginChange', checkAuth);
    };
  }, []);

  return (
    <AuthContext.Provider value={{ isAuthenticated, isLoading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

// 自定义钩子，方便组件使用
export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};