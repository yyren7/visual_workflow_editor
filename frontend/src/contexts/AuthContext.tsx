import React, { createContext, useContext, useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
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
  const location = useLocation();

  // 验证token有效性的函数
  const verifyToken = async (token: string): Promise<boolean> => {
    if (!token) return false;

    try {
      console.log('验证token...');
      const response = await axios.get(`${API_BASE_URL}/auth/verify-token`, {
        headers: {
          Authorization: `Bearer ${token}`
        },
        withCredentials: true
      });
      console.log('Token验证成功');
      return response.status === 200;
    } catch (error) {
      console.error('Token验证失败:', error);
      return false;
    }
  };

  // 登录函数 - 不自动跳转，让路由系统处理
  const login = (token: string) => {
    console.log('设置认证token');
    localStorage.setItem('access_token', token);
    setIsAuthenticated(true);
  };

  // 登出函数 - 只设置状态，并在确定状态后使用统一的路由处理
  const logout = () => {
    console.log('触发退出登录事件，让组件可以取消未完成的请求');
    // 发送自定义事件通知所有组件用户即将注销
    window.dispatchEvent(new CustomEvent('user-logout'));
    
    // 给组件一点时间处理退出事件 (50ms应该足够)
    setTimeout(() => {
      console.log('移除认证token，设置为未认证状态');
      localStorage.removeItem('access_token');
      setIsAuthenticated(false);
      navigate('/login', { replace: true });
    }, 50);
  };

  // 初始加载时验证token - 使用async/await提高可读性
  useEffect(() => {
    const initAuth = async () => {
      console.log('初始化认证状态...');
      setIsLoading(true);
      try {
        const token = localStorage.getItem('access_token');
        console.log('获取到token:', token ? '存在' : '不存在');
        
        if (token) {
          const isValid = await verifyToken(token);
          console.log('Token验证结果:', isValid ? '有效' : '无效');
          
          if (isValid) {
            setIsAuthenticated(true);
          } else {
            localStorage.removeItem('access_token');
            setIsAuthenticated(false);
          }
        } else {
          setIsAuthenticated(false);
        }
      } catch (error) {
        console.error('认证初始化错误:', error);
        setIsAuthenticated(false);
      } finally {
        console.log('认证初始化完成');
        setIsLoading(false);
      }
    };
    
    initAuth();
  }, []);

  // 监听本地存储变化 - 处理多标签页同步登录状态
  useEffect(() => {
    const checkAuth = async () => {
      const token = localStorage.getItem('access_token');
      console.log('存储变化检测, token:', token ? '存在' : '不存在');
      
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

  // 记录认证状态变化
  useEffect(() => {
    console.log('认证状态变化:', {
      isAuthenticated,
      isLoading,
      currentPath: location.pathname
    });
  }, [isAuthenticated, isLoading, location]);

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