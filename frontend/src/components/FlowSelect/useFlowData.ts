import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { FlowData, getFlowsForUser } from '../../api/flowApi';

export const useFlowData = () => {
  const [flows, setFlows] = useState<FlowData[]>([]);
  const [filteredFlows, setFilteredFlows] = useState<FlowData[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState<string>('');
  const { t } = useTranslation();

  // 获取流程列表
  useEffect(() => {
    const fetchFlows = async () => {
      try {
        setLoading(true);
        setError(null);
        // 减少请求数量，避免可能的性能问题
        const userFlows = await getFlowsForUser(0, 100);
        console.log("成功获取流程图列表:", userFlows.length);
        // 按更新时间降序排序，处理undefined情况
        userFlows.sort((a, b) => 
          new Date(b.updated_at || 0).getTime() - new Date(a.updated_at || 0).getTime()
        );
        setFlows(userFlows);
        setFilteredFlows(userFlows);
      } catch (err) {
        console.error('加载流程图列表失败:', err);
        // 添加更多错误信息输出
        if (err instanceof Error) {
          console.error('错误详情:', err.message);
          setError(`${t('flowSelect.error', '加载流程图失败')}: ${err.message}`);
        } else {
          setError(t('flowSelect.error', '加载流程图失败'));
        }
      } finally {
        setLoading(false);
      }
    };

    fetchFlows();
  }, [t]);

  // 当搜索词变化时，过滤流程图
  useEffect(() => {
    if (searchTerm.trim() === '') {
      setFilteredFlows(flows);
    } else {
      const filtered = flows.filter(flow =>
        flow.name.toLowerCase().includes(searchTerm.toLowerCase())
      );
      setFilteredFlows(filtered);
    }
  }, [searchTerm, flows]);

  // 更新本地流程列表
  const updateFlows = (updatedFlows: FlowData[]) => {
    setFlows(updatedFlows);
    setFilteredFlows(updatedFlows.filter(flow =>
      searchTerm.trim() === '' || flow.name.toLowerCase().includes(searchTerm.toLowerCase())
    ));
  };

  // 从列表中移除流程
  const removeFlow = (flowIdToRemove: string) => {
    const updatedFlows = flows.filter(flow => flow.id !== flowIdToRemove);
    updateFlows(updatedFlows);
  };

  // 刷新流程列表
  const refreshFlows = async () => {
    try {
      const updatedFlows = await getFlowsForUser(0, 100);
      updateFlows(updatedFlows);
    } catch (err) {
      console.error('刷新流程列表失败:', err);
    }
  };

  return {
    flows,
    filteredFlows,
    loading,
    error,
    searchTerm,
    setSearchTerm,
    setLoading,
    updateFlows,
    removeFlow,
    refreshFlows
  };
}; 