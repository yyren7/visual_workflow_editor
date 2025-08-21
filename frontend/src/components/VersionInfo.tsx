import React, { useEffect, useState } from 'react';
import { Box, Typography, Tooltip } from '@mui/material';
import { useTranslation } from 'react-i18next';
import InfoIcon from '@mui/icons-material/Info';

// 导入API配置
const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000';

/**
 * VersionInfo组件 - 显示应用的版本信息
 * 
 * 从后端API获取版本信息
 */
const VersionInfo: React.FC = () => {
  const { t } = useTranslation();
  const [versionData, setVersionData] = useState<{version: string, lastUpdated: string} | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<boolean>(false);

  useEffect(() => {
    const fetchVersionInfo = async () => {
      try {
        // 直接使用fetch，避免axios配置问题
        console.log(`尝试从API获取版本信息: ${API_BASE_URL}/api/version`);
        const response = await fetch(`${API_BASE_URL}/api/version`);
        
        if (response.ok) {
          const data = await response.json();
          console.log('API版本信息获取成功:', data);
          setVersionData(data);
          setError(false);
        } else {
          console.error('API请求失败, 状态码:', response.status);
          setError(true);
        }
      } catch (apiError) {
        console.error('无法从API获取版本信息', apiError);
        setError(true);
      } finally {
        setLoading(false);
      }
    };

    fetchVersionInfo();
  }, []);

  // 只有在成功获取到数据后才显示版本信息
  if (loading) {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', mr: 2, opacity: 0.5 }}>
        <Typography variant="caption" color="inherit">
          {t('version.label')}: 加载中...
        </Typography>
      </Box>
    );
  }

  if (error || !versionData) {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', mr: 2, opacity: 0.7 }}>
        <Typography variant="caption" color="inherit" sx={{ color: '#ff9800' }}>
          {t('version.label')}: 未知
        </Typography>
      </Box>
    );
  }

  return (
    <Tooltip 
      title={`${t('version.lastUpdated')}: ${versionData.lastUpdated}`} 
      arrow 
      placement="top"
    >
      <Box 
        sx={{ 
          display: 'flex',
          alignItems: 'center',
          padding: '4px 8px',
          borderRadius: '4px',
          opacity: 0.7,
          backgroundColor: '#2d2d2d',
          border: '1px solid #444',
          '&:hover': {
            opacity: 1,
          }
        }}
      >
        <InfoIcon sx={{ fontSize: '0.8rem', mr: 0.5, color: 'inherit' }} />
        <Typography 
          variant="caption" 
          color="inherit" 
          sx={{ 
            fontSize: '0.75rem',
            userSelect: 'none',
          }}
        >
          Visual Workflow Editor {versionData.version}
        </Typography>
      </Box>
    </Tooltip>
  );
};

export default VersionInfo; 