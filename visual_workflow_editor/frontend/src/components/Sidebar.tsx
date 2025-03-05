// frontend/src/components/Sidebar.tsx
import React from 'react';
import { Box, Drawer, Divider, Typography } from '@mui/material';
import NodeSelector from './NodeSelector';

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
        },
      }}
    >
      <Box sx={{ overflow: 'auto' }}>
        <Typography
          variant="h6"
          sx={{
            padding: '16px',
            textAlign: 'center',
            borderBottom: '1px solid rgba(255, 255, 255, 0.12)',
            bgcolor: '#333',
            color: 'white'
          }}
        >
          节点选择器
        </Typography>
        <Divider />
        <Box sx={{ p: 1 }}>
          <Typography variant="body2" sx={{ mb: 2, color: '#aaa', fontStyle: 'italic' }}>
            拖拽节点到流程图区域
          </Typography>
          <NodeSelector />
        </Box>
      </Box>
    </Drawer>
  );
};

export default Sidebar;