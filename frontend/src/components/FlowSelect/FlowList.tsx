import React from 'react';
import {
  Box,
  CircularProgress,
  Typography,
  List
} from '@mui/material';
import { useTranslation } from 'react-i18next';
import { FlowListProps } from './types';
import FlowItem from './FlowItem';

const FlowList: React.FC<FlowListProps> = ({
  flows,
  loading,
  error,
  searchTerm,
  onFlowSelect,
  onEditClick,
  onDeleteClick,
  onDuplicateClick
}) => {
  const { t } = useTranslation();

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Typography color="error" sx={{ p: 2 }}>
        {error}
      </Typography>
    );
  }

  if (flows.length === 0) {
    return (
      <Box sx={{ p: 2, textAlign: 'center' }}>
        {searchTerm ? (
          <Typography sx={{ color: '#aaa', fontStyle: 'italic' }}>
            {t('flowSelect.noSearchResults', '没有找到匹配的流程图')}
          </Typography>
        ) : (
          <Typography sx={{ color: '#aaa', fontStyle: 'italic' }}>
            {t('flowSelect.noFlows', '没有找到流程图')}
          </Typography>
        )}
      </Box>
    );
  }

  return (
    <Box sx={{ maxHeight: '350px', overflow: 'auto' }}>
      <List sx={{ width: '100%', p: 0 }}>
        {flows.map((flow) => (
          <FlowItem
            key={flow.id}
            flow={flow}
            onSelect={onFlowSelect}
            onEdit={onEditClick}
            onDelete={onDeleteClick}
            onDuplicate={onDuplicateClick}
          />
        ))}
      </List>
    </Box>
  );
};

export default FlowList; 