import React from 'react';
import {
  Paper,
  ListItemButton,
  ListItem,
  IconButton,
  Box,
  Typography
} from '@mui/material';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import { FlowItemProps } from './types';
import { formatDate } from './utils';

const FlowItem: React.FC<FlowItemProps> = ({
  flow,
  onSelect,
  onEdit,
  onDelete,
  onDuplicate
}) => {
  return (
    <Paper
      elevation={2}
      sx={{
        mb: 1,
        bgcolor: '#383838',
        '&:hover': {
          bgcolor: '#444',
        }
      }}
    >
      <ListItemButton onClick={() => onSelect(flow.id)}>
        <ListItem
          disablePadding
          sx={{ display: 'block', width: '100%' }}
        >
          <Box display="flex" justifyContent="space-between" alignItems="flex-start" width="100%" p={1}>
            <Box sx={{ flexGrow: 1, minWidth: 0, pr: 2 }}>
              <Typography 
                variant="body1"
                sx={{ 
                  fontWeight: 'medium',
                  color: 'white',
                  mb: 0.5,
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap'
                }}
              >
                {flow.name}
              </Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', color: '#aaa' }}>
                <AccessTimeIcon fontSize="small" sx={{ mr: 0.5, fontSize: '0.9rem' }} />
                <Typography variant="caption" sx={{ fontSize: '0.8rem' }}>
                  {flow.updated_at ? formatDate(flow.updated_at) : formatDate(flow.created_at)}
                </Typography>
              </Box>
            </Box>
            <Box 
              display="flex" 
              gap={0.5} 
              sx={{ 
                flexShrink: 0,
                opacity: 0.7,
                transition: 'opacity 0.2s ease',
                '&:hover': { opacity: 1 }
              }}
            >
              <IconButton
                size="small"
                onClick={(e) => onEdit(e, flow)}
                sx={{ 
                  color: '#2196f3',
                  backgroundColor: 'rgba(33, 150, 243, 0.1)',
                  border: '1px solid rgba(33, 150, 243, 0.3)',
                  width: '32px',
                  height: '32px',
                  '&:hover': { 
                    backgroundColor: 'rgba(33, 150, 243, 0.2)',
                    borderColor: 'rgba(33, 150, 243, 0.5)',
                    transform: 'scale(1.05)'
                  },
                  transition: 'all 0.2s ease'
                }}
              >
                <EditIcon sx={{ fontSize: '1rem' }} />
              </IconButton>
              <IconButton
                size="small"
                onClick={(e) => onDuplicate(e, flow)}
                sx={{
                  color: '#42a5f5',
                  backgroundColor: 'rgba(66, 165, 245, 0.1)',
                  border: '1px solid rgba(66, 165, 245, 0.3)',
                  width: '32px',
                  height: '32px',
                  '&:hover': {
                    backgroundColor: 'rgba(66, 165, 245, 0.2)',
                    borderColor: 'rgba(66, 165, 245, 0.5)',
                    transform: 'scale(1.05)'
                  },
                  transition: 'all 0.2s ease'
                }}
              >
                <ContentCopyIcon sx={{ fontSize: '1rem' }} />
              </IconButton>
              <IconButton
                size="small"
                onClick={(e) => onDelete(e, flow)}
                sx={{
                  color: '#f44336',
                  backgroundColor: 'rgba(244, 67, 54, 0.1)',
                  border: '1px solid rgba(244, 67, 54, 0.3)',
                  width: '32px',
                  height: '32px',
                  '&:hover': {
                    backgroundColor: 'rgba(244, 67, 54, 0.2)',
                    borderColor: 'rgba(244, 67, 54, 0.5)',
                    transform: 'scale(1.05)'
                  },
                  transition: 'all 0.2s ease'
                }}
              >
                <DeleteIcon sx={{ fontSize: '1rem' }} />
              </IconButton>
            </Box>
          </Box>
        </ListItem>
      </ListItemButton>
    </Paper>
  );
};

export default FlowItem; 