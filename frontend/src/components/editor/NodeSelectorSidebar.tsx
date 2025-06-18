import React from 'react';
import {
  Box,
  Typography
} from '@mui/material';
import NodeSelector from '../NodeSelector'; // Assuming NodeSelector is in parent dir
import { useTranslation } from 'react-i18next'; // Import hook

interface NodeSelectorSidebarProps {
  open: boolean; // Use 'open' to match convention/FlowEditor usage
}

const NodeSelectorSidebar: React.FC<NodeSelectorSidebarProps> = ({ open }) => {
  const { t } = useTranslation(); // Use hook

  if (!open) {
    return null; // Don't render if closed
  }

  return (
    <Box
      sx={{
        position: 'absolute',
        top: '12px',
        left: '12px',
        width: '220px',
        height: 'auto',
        maxHeight: '60%',
        bgcolor: '#2d2d2d',
        borderRadius: '4px',
        boxShadow: '0 4px 20px rgba(0,0,0,0.5)',
        zIndex: 5,
        display: 'flex',
        flexDirection: 'column',
        border: '1px solid #444',
        overflow: 'hidden'
      }}
    >
      <Box sx={{
        p: 1,
        bgcolor: '#333',
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        borderBottom: '1px solid #444'
      }}>
        <Typography variant="subtitle2" color="white"> {/* Ensure text is visible */}
          {t('sidebar.title')}
        </Typography>
      </Box>
      <Box sx={{ p: 1.5, overflowY: 'auto', flexGrow: 1 }}>
        <Typography
          variant="body2"
          sx={{
            mb: 1.5,
            color: '#aaa',
            fontStyle: 'italic',
            fontSize: '0.8rem'
          }}
        >
          {t('sidebar.dragHint')}
        </Typography>
        
        <NodeSelector />
      </Box>
    </Box>
  );
};

export default NodeSelectorSidebar; 