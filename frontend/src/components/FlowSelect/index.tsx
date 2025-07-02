import React from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  Typography,
  IconButton
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import { useTranslation } from 'react-i18next';
import { FlowSelectProps } from './types';
import { useFlowData } from './useFlowData';
import { useFlowActions } from './useFlowActions';
import SearchBar from './SearchBar';
import FlowList from './FlowList';
import FlowDialogs from './FlowDialogs';

const FlowSelect: React.FC<FlowSelectProps> = ({ open, onClose }) => {
  const { t } = useTranslation();
  
  // 数据管理hook
  const {
    filteredFlows,
    loading,
    error,
    searchTerm,
    setSearchTerm,
    setLoading,
    updateFlows,
    removeFlow,
    refreshFlows
  } = useFlowData(open);

  // 操作逻辑hook
  const {
    editDialog,
    deleteDialog,
    handleFlowSelect,
    handleCreateNewFlow,
    handleEditClick,
    handleEditDialogClose,
    handleSaveFlowName,
    handleDeleteClick,
    handleDeleteDialogClose,
    handleConfirmDelete,
    handleDuplicateClick,
    handleNewFlowNameChange
  } = useFlowActions(
    updateFlows,
    removeFlow,
    refreshFlows,
    setLoading,
    onClose
  );

  return (
    <>
      <Dialog
        open={open}
        onClose={onClose}
        fullWidth
        maxWidth="sm"
        disableEnforceFocus={true}
        disableRestoreFocus={true}
        PaperProps={{
          sx: {
            bgcolor: '#2d2d2d',
            color: 'white',
            border: '1px solid #444'
          }
        }}
      >
        <DialogTitle sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          bgcolor: '#333',
          borderBottom: '1px solid #444'
        }}>
          <Typography variant="h6" component="div">
            {t('flowSelect.title', '选择流程图')}
          </Typography>
          <IconButton
            edge="end"
            color="inherit"
            onClick={onClose}
            aria-label="close"
          >
            <CloseIcon />
          </IconButton>
        </DialogTitle>
        
        <DialogContent sx={{ pt: 2, pb: 2 }}>
          <SearchBar
            searchTerm={searchTerm}
            onSearchChange={setSearchTerm}
            onCreateNew={handleCreateNewFlow}
            loading={loading}
          />
          
          <FlowList
            flows={filteredFlows}
            loading={loading}
            error={error}
            searchTerm={searchTerm}
            onFlowSelect={handleFlowSelect}
            onEditClick={handleEditClick}
            onDeleteClick={handleDeleteClick}
            onDuplicateClick={handleDuplicateClick}
          />
        </DialogContent>
      </Dialog>

      <FlowDialogs
        editDialog={editDialog}
        deleteDialog={deleteDialog}
        loading={loading}
        onEditDialogClose={handleEditDialogClose}
        onSaveFlowName={handleSaveFlowName}
        onDeleteDialogClose={handleDeleteDialogClose}
        onConfirmDelete={handleConfirmDelete}
        onNewFlowNameChange={handleNewFlowNameChange}
      />
    </>
  );
};

export default FlowSelect; 