import React, { useEffect, useState } from 'react';
import { Box, Typography, Tooltip } from '@mui/material';
import axios from 'axios';
import { useTranslation } from 'react-i18next';

/**
 * VersionInfo组件 - 显示应用的版本信息
 * 
 * 尝试从后端API获取版本信息，如果失败则尝试直接从version.json获取
 */
const VersionInfo: React.FC = () => {
  const { t } = useTranslation();
  const [versionData, setVersionData] = useState<{version: string, lastUpdated: string} | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    const fetchVersionInfo = async () => {
      try {
        // 首先尝试从API获取版本信息
        const response = await axios.get('/api/version');
        setVersionData(response.data);
      } catch (apiError) {
        console.log('无法从API获取版本信息，尝试直接读取version.json', apiError);
        
        try {
          // API失败后尝试直接获取version.json
          const fileResponse = await fetch('/version.json');
          if (fileResponse.ok) {
            const data = await fileResponse.json();
            setVersionData(data);
          } else {
            console.error('无法读取version.json文件');
          }
        } catch (fileError) {
          console.error('读取version.json失败:', fileError);
        }
      } finally {
        setLoading(false);
      }
    };

    fetchVersionInfo();
  }, []);

  if (loading || !versionData) {
    return null; // 加载中或没有数据时不显示
  }

  return (
    <Tooltip title={`${t('version.lastUpdated')}: ${versionData.lastUpdated}`} arrow placement="top">
      <Box 
        sx={{ 
          display: 'flex',
          alignItems: 'center',
          mr: 2,
          opacity: 0.7,
          '&:hover': {
            opacity: 1
          }
        }}
      >
        <Typography variant="caption" color="inherit">
          {t('version.label')}: {versionData.version}
        </Typography>
      </Box>
    </Tooltip>
  );
};

export default VersionInfo; 