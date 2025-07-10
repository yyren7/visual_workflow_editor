import React, { createContext, useContext, useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { useSnackbar } from 'notistack';
import { useAuth } from './AuthContext';

interface Flow {
  id: string;
  name: string;
  updated_at: string;
  // 其他流程图字段...
}

interface FlowContextType {
  flows: Flow[];
  currentFlowId: string | null;
  setCurrentFlowId: (id: string | null) => void;
  fetchFlows: () => Promise<void>;
  loading: boolean;
  error: string | null;
}

// 创建上下文
const FlowContext = createContext<FlowContextType | undefined>(undefined);

// Provider 组件
export const FlowProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [flows, setFlows] = useState<Flow[]>([]);
  const [currentFlowId, setCurrentFlowId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { enqueueSnackbar } = useSnackbar();
  const { isAuthenticated, isLoading } = useAuth(); // 使用认证上下文
  
  // 防止重复请求的标记
  const isFetchingRef = useRef(false);
  const lastFetchTimeRef = useRef(0);
  const hasFetchedRef = useRef(false);
  
  // API基础URL
  const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000';
  
  // 获取所有流程图
  const fetchFlows = async () => {
    // 如果用户未认证，不执行请求
    if (!isAuthenticated) {
      console.log('用户未认证，跳过请求流程图');
      return;
    }
    
    // 防止重复请求
    const now = Date.now();
    const MIN_FETCH_INTERVAL = 3000; // 3秒内不重复请求
    
    if (isFetchingRef.current || (now - lastFetchTimeRef.current) < MIN_FETCH_INTERVAL) {
      console.log('跳过重复的流程图请求');
      return;
    }
    
    isFetchingRef.current = true;
    lastFetchTimeRef.current = now;
    setLoading(true);
    setError(null);
    
    try {
      const token = localStorage.getItem('access_token');
      if (!token) {
        console.log('没有找到访问令牌，跳过请求');
        return;
      }
      
      console.log('开始请求流程图数据...');
      const response = await axios.get(`${API_BASE_URL}/flows/`, {
        withCredentials: true,
        headers: {
          Authorization: `Bearer ${token}`
        }
      });
      
      console.log('成功获取流程图数据:', response.data.length);
      setFlows(response.data);
      hasFetchedRef.current = true;
      
      // 如果有流程图但没有选中的流程图，选择第一个
      if (response.data.length > 0 && !currentFlowId) {
        setCurrentFlowId(response.data[0].id);
      }
    } catch (err) {
      console.error('获取流程图失败:', err);
      setError('加载流程图失败');
      // 只有在非认证错误时才显示错误提示
      if (!axios.isAxiosError(err) || err.response?.status !== 401) {
        enqueueSnackbar('无法加载流程图列表，请稍后再试', { variant: 'error' });
      }
    } finally {
      setLoading(false);
      isFetchingRef.current = false;
    }
  };
  
  // 初始加载 - 等待认证状态就绪后再获取数据
  useEffect(() => {
    // 只有当认证加载完成且用户已认证时才获取数据
    if (!isLoading && isAuthenticated && !hasFetchedRef.current) {
      console.log('认证状态就绪且已认证，开始获取流程图');
      fetchFlows();
    } else if (!isLoading && !isAuthenticated) {
      console.log('认证状态就绪但未认证，清空流程图数据');
      setFlows([]); // 清空流程图数据
      setCurrentFlowId(null);
      hasFetchedRef.current = false; // 重置获取标记
    }
  }, [isLoading, isAuthenticated]); // 减少依赖，避免频繁触发
  
  // 监听用户登出事件，清理数据
  useEffect(() => {
    const handleUserLogout = () => {
      console.log('FlowContext: 用户登出，清理数据');
      setFlows([]);
      setCurrentFlowId(null);
      setError(null);
      hasFetchedRef.current = false;
      // 重置请求标记
      isFetchingRef.current = false;
      lastFetchTimeRef.current = 0;
    };
    
    window.addEventListener('user-logout', handleUserLogout);
    
    return () => {
      window.removeEventListener('user-logout', handleUserLogout);
    };
  }, []);
  
  // 提供上下文值
  const value = {
    flows,
    currentFlowId,
    setCurrentFlowId,
    fetchFlows,
    loading,
    error
  };
  
  return <FlowContext.Provider value={value}>{children}</FlowContext.Provider>;
};

// 自定义钩子，方便组件使用
export const useFlowContext = () => {
  const context = useContext(FlowContext);
  if (!context) {
    throw new Error('useFlowContext must be used within a FlowProvider');
  }
  return context;
}; 