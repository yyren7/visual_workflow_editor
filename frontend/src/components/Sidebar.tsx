// visual_workflow_editor/frontend/src/components/Sidebar.tsx
import React from 'react';
import { Box, Drawer, Divider, Typography } from '@mui/material';
import NodeSelector from './NodeSelector';
import { useTranslation } from 'react-i18next';

// 侧边栏属性接口
interface SidebarProps {
  isOpen: boolean;
  toggleSidebar: () => void;
}

/**
 * Sidebar Component
 *
 * This component provides a sidebar with a NodeSelector for adding nodes to the flow.
 */
const Sidebar: React.FC<SidebarProps> = ({ isOpen, toggleSidebar }) => {
  const { t } = useTranslation();
  
  return (
    <Drawer
      anchor="left"
      open={isOpen}
      onClose={toggleSidebar}
      variant="persistent"
      sx={{
        width: 240,
        flexShrink: 0,
        '& .MuiDrawer-paper': {
          width: 240,
          boxSizing: 'border-box',
          bgcolor: '#1e1e1e',
          color: 'white',
          marginTop: '40px', // 与顶部工具栏高度对齐
          height: 'calc(100% - 40px)', // 减去顶部工具栏的高度
          borderRight: '1px solid rgba(255, 255, 255, 0.12)',
          zIndex: 5
        },
      }}
    >
      <Box sx={{ overflow: 'auto', height: '100%' }}>
        <Typography
          variant="subtitle1"
          sx={{
            padding: '10px 16px',
            textAlign: 'center',
            borderBottom: '1px solid rgba(255, 255, 255, 0.12)',
            bgcolor: '#333',
            color: 'white',
            fontWeight: 'medium'
          }}
        >
          {t('sidebar.title')}
        </Typography>
        <Box sx={{ p: 2, height: 'calc(100% - 40px)', overflowY: 'auto' }}>
          <Typography 
            variant="body2" 
            sx={{ 
              mb: 2, 
              color: '#aaa', 
              fontStyle: 'italic',
              fontSize: '0.85rem'
            }}
          >
            {t('sidebar.dragHint')}
          </Typography>
          <NodeSelector />
        </Box>
      </Box>
    </Drawer>
  );
};

export default Sidebar;