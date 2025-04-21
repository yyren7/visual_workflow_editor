import React from 'react';
import { Box, Typography, Tooltip } from '@mui/material';
import { useTranslation } from 'react-i18next';
import InfoIcon from '@mui/icons-material/Info';

/**
 * VersionInfo组件 - 显示应用的版本信息
 * 
 * 版本信息通过构建时环境变量注入
 */
const VersionInfo: React.FC = () => {
  const { t } = useTranslation();
  // Directly read the version from environment variable, default to 'dev'
  const appVersion = process.env.REACT_APP_VERSION || 'dev';

  return (
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
        Visual Workflow Editor {appVersion}
      </Typography>
    </Box>
  );
};

export default VersionInfo; 