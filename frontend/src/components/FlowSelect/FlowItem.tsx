import React from 'react';
import {
  Paper,
  ListItemButton,
  ListItem,
  ListItemText,
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
          sx={{ display: 'block' }}
          secondaryAction={
            <Box sx={{ display: 'flex' }}>
              <IconButton
                edge="end"
                aria-label="edit"
                onClick={(e) => onEdit(e, flow)}
                sx={{ color: 'rgba(255, 255, 255, 0.7)' }}
              >
                <EditIcon />
              </IconButton>
              <IconButton
                edge="end"
                aria-label="duplicate"
                onClick={(e) => onDuplicate(e, flow)}
                sx={{
                  color: 'rgba(255, 255, 255, 0.7)',
                  '&:hover': {
                    color: '#42a5f5',
                  }
                }}
              >
                <ContentCopyIcon />
              </IconButton>
              <IconButton
                edge="end"
                aria-label="delete"
                onClick={(e) => onDelete(e, flow)}
                sx={{
                  color: 'rgba(255, 255, 255, 0.7)',
                  '&:hover': {
                    color: '#f44336',
                  }
                }}
              >
                <DeleteIcon />
              </IconButton>
            </Box>
          }
        >
          <ListItemText
            primary={flow.name}
            secondary={
              <Box sx={{ display: 'flex', alignItems: 'center', color: '#aaa', mt: 0.5 }}>
                <AccessTimeIcon fontSize="small" sx={{ mr: 0.5, fontSize: '0.9rem' }} />
                <Typography variant="caption" sx={{ fontSize: '0.8rem' }}>
                  {flow.updated_at ? formatDate(flow.updated_at) : formatDate(flow.created_at)}
                </Typography>
              </Box>
            }
            primaryTypographyProps={{
              fontWeight: 'medium',
              color: 'white'
            }}
            secondaryTypographyProps={{
              component: 'div'
            }}
          />
        </ListItem>
      </ListItemButton>
    </Paper>
  );
};

export default FlowItem; 