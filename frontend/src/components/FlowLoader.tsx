import React, { useEffect, useState, useRef } from 'react';
import { useNavigate, useParams, useLocation } from 'react-router-dom';
import { Box, CircularProgress, Typography } from '@mui/material';
import { getFlow } from '../api/api';
import FlowEditorWrapper from './FlowEditor';
import { useSnackbar } from 'notistack';
import { useTranslation } from 'react-i18next';

// 创建组件外的缓存，即使在StrictMode下组件重复挂载也能保持
// 缓存最近的请求，避免重复调用API
const requestCache: Record<string, {
  timestamp: number;
  promise?: Promise<any>;
  data?: any;
}> = {};

// 缓存有效期（毫秒）
const CACHE_DURATION = 2000; // 2秒内的相同请求将使用缓存

/**
 * FlowLoader组件
 * 
 * 该组件用于加载指定ID的流程图
 * 如果URL中有flowId，则直接加载该流程图
 * 如果没有flowId，则重定向到流程图选择页面
 */
const FlowLoader: React.FC = () => {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [loadedFlowId, setLoadedFlowId] = useState<string | null>(null);
  const { flowId } = useParams<{ flowId: string }>();
  const navigate = useNavigate();
  const { enqueueSnackbar } = useSnackbar();
  const location = useLocation();
  const queryParams = new URLSearchParams(location.search);
  const flowIdFromQuery = queryParams.get('id');
  const userId = queryParams.get('user') || localStorage.getItem('user_id');
  
  // 使用ref跟踪已加载的流程图ID和初始加载状态
  const loadedFlowIdRef = useRef<string | null>(null);
  // 使用ref标记组件是否经历过初始渲染，避免StrictMode带来的重复请求
  const mountedRef = useRef(false);

  // 封装获取流程图的函数，带有缓存功能
  const fetchFlowWithCache = async (flowId: string) => {
    const cacheKey = `flow_${flowId}`;
    const now = Date.now();
    
    // 检查缓存是否存在且有效
    if (requestCache[cacheKey]) {
      const cache = requestCache[cacheKey];
      
      // 如果缓存未过期
      if (now - cache.timestamp < CACHE_DURATION) {
        console.log(`使用缓存的流程图数据: ${flowId}`);
        
        // 如果有缓存的promise，返回它
        if (cache.promise) {
          return cache.promise;
        }
        
        // 如果有缓存的数据，直接返回
        if (cache.data) {
          return cache.data;
        }
      }
    }
    
    // 创建新的请求promise
    console.log(`创建新的流程图数据请求: ${flowId}`);
    const promise = getFlow(flowId);
    
    // 保存到缓存
    requestCache[cacheKey] = {
      timestamp: now,
      promise
    };
    
    try {
      // 等待请求完成
      const data = await promise;
      
      // 更新缓存中的数据
      requestCache[cacheKey].data = data;
      requestCache[cacheKey].promise = undefined;
      
      return data;
    } catch (error) {
      // 请求失败，从缓存中移除
      delete requestCache[cacheKey];
      throw error;
    }
  };

  // 仅在组件挂载或URL参数变化时执行一次
  useEffect(() => {
    // 获取目标流程图ID
    const targetFlowId = flowIdFromQuery || flowId || '';
    
    // 如果没有指定流程图ID，重定向到选择页面
    if (!targetFlowId) {
      console.log("没有指定流程图ID，重定向到选择页面");
      navigate('/select', { replace: true });
      return;
    }
    
    // 在StrictMode下防止重复请求，仅在首次挂载和URL变化时加载
    if (mountedRef.current && loadedFlowIdRef.current === targetFlowId) {
      console.log("跳过重复加载 (StrictMode)", targetFlowId);
      return;
    }
    
    // 标记组件已挂载
    mountedRef.current = true;
    
    // 创建加载函数
    const loadFlowData = async () => {
      // 如果已经加载了相同ID的流程图，则跳过
      if (loadedFlowIdRef.current === targetFlowId && loadedFlowId === targetFlowId) {
        console.log("已加载相同ID的流程图，跳过重复加载", targetFlowId);
        return;
      }
      
      setLoading(true);
      setError(null);
      
      try {
        console.log("开始加载流程图", targetFlowId);
        // 使用带缓存的函数获取流程图
        const flowData = await fetchFlowWithCache(targetFlowId);
        
        if (flowData) {
          // 更新已加载的流程图ID
          loadedFlowIdRef.current = targetFlowId;
          setLoadedFlowId(targetFlowId);
          
          // 确保URL正确
          const targetUrl = `/flow?id=${targetFlowId}${userId ? `&user=${userId}` : ''}`;
          const currentPath = location.pathname + location.search;
          if (currentPath !== targetUrl) {
            console.log("更新URL为", targetUrl);
            navigate(targetUrl, { replace: true });
          }
        } else {
          setError(t('flowEditor.invalidFlowData'));
          enqueueSnackbar(t('flowEditor.invalidFlowData'), { variant: 'error' });
          // 流程图无效，重定向到选择页面
          setTimeout(() => {
            navigate('/select', { replace: true });
          }, 3000);
        }
      } catch (err: any) {
        handleLoadError(err);
      } finally {
        setLoading(false);
      }
    };
    
    // 处理加载错误
    const handleLoadError = (err: any) => {
      if (err.message === "没有权限访问此流程图") {
        setError(t('flowEditor.permissionDenied', '没有权限访问此流程图'));
        enqueueSnackbar(t('flowEditor.permissionDenied', '没有权限访问此流程图'), {
          variant: 'error',
          autoHideDuration: 5000
        });
      } else if (err.message === "流程图不存在") {
        setError(t('flowEditor.notExist', '流程图不存在'));
        enqueueSnackbar(t('flowEditor.notExist', '流程图不存在'), { 
          variant: 'error',
          autoHideDuration: 5000 
        });
      } else {
        console.error('Error loading flow:', err);
        const errorMessage = err instanceof Error ? err.message : t('flowEditor.loadError');
        setError(errorMessage);
        enqueueSnackbar(errorMessage, { variant: 'error' });
      }
      
      // 所有错误都重定向到选择页面
      setTimeout(() => {
        navigate('/select', { replace: true });
      }, 3000);
    };
    
    // 执行加载
    loadFlowData();
    
  // 注意：我们故意不将loadedFlowId作为依赖项，以防止重复加载
  }, [flowId, flowIdFromQuery, userId, navigate, enqueueSnackbar, t]);
  
  // 添加一个新的useEffect来监听flow-changed事件
  useEffect(() => {
    const handleFlowChanged = (event: CustomEvent) => {
      if (event.detail && event.detail.flowId) {
        const targetFlowId = event.detail.flowId;
        const userId = localStorage.getItem('user_id');
        
        // 如果流程图ID已更改，更新URL并加载新流程图
        if (targetFlowId !== loadedFlowId) {
          console.log('接收到流程图变更事件:', targetFlowId);
          // 更新URL，但不刷新整个页面
          navigate(`/flow?id=${targetFlowId}${userId ? `&user=${userId}` : ''}`, { replace: true });
        }
      }
    };
    
    // 添加事件监听器
    window.addEventListener('flow-changed', handleFlowChanged as EventListener);
    
    // 清理函数
    return () => {
      window.removeEventListener('flow-changed', handleFlowChanged as EventListener);
    };
  }, [loadedFlowId, navigate]);

  if (loading) {
    return (
      <Box sx={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        height: '100vh',
        flexDirection: 'column',
        gap: 2,
        bgcolor: '#1e1e1e',
        color: 'white'
      }}>
        <CircularProgress color="inherit" />
        <Typography variant="h6">{t('common.loading')}</Typography>
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        height: '100vh',
        flexDirection: 'column',
        gap: 2,
        color: 'error.main',
        bgcolor: '#1e1e1e',
      }}>
        <Typography variant="h6">{error}</Typography>
        <Typography variant="body2">
          {t('flowEditor.redirectToSelect', '正在重定向到流程图选择页面...')}
        </Typography>
      </Box>
    );
  }

  return loadedFlowId ? <FlowEditorWrapper flowId={loadedFlowId} /> : null;
};

export default FlowLoader; 