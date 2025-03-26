import React, { createContext, useState, useContext, useEffect } from 'react';
import axios from 'axios';
import { useSnackbar } from 'notistack';

// 定义接口
interface Flow {
  id: string;
  name: string;
  data: any;
  owner_id: string;
  created_at: string;
  updated_at: string;
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
  
  // API基础URL
  const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000';
  
  // 获取所有流程图
  const fetchFlows = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await axios.get(`${API_BASE_URL}/flows`, {
        withCredentials: true
      });
      
      setFlows(response.data);
      
      // 如果有流程图但没有选中的流程图，选择第一个
      if (response.data.length > 0 && !currentFlowId) {
        setCurrentFlowId(response.data[0].id);
      }
    } catch (err) {
      console.error('获取流程图失败:', err);
      setError('加载流程图失败');
      enqueueSnackbar('无法加载流程图列表，请稍后再试', { variant: 'error' });
    } finally {
      setLoading(false);
    }
  };
  
  // 初始加载
  useEffect(() => {
    fetchFlows();
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

// 自定义钩子，简化上下文使用
export const useFlowContext = () => {
  const context = useContext(FlowContext);
  if (context === undefined) {
    throw new Error('useFlowContext must be used within a FlowProvider');
  }
  return context;
}; 