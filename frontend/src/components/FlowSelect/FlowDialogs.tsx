import React from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Button,
  Typography
} from '@mui/material';
import { useTranslation } from 'react-i18next';
import { FlowDialogsProps } from './types';

const FlowDialogs: React.FC<FlowDialogsProps> = ({
  editDialog,
  deleteDialog,
  loading,
  onEditDialogClose,
  onSaveFlowName,
  onDeleteDialogClose,
  onConfirmDelete,
  onNewFlowNameChange
}) => {
  const { t } = useTranslation();

  return (
    <>
      {/* 编辑流程图名称的对话框 */}
      <Dialog
        open={editDialog.open}
        onClose={onEditDialogClose}
        fullWidth
        maxWidth="xs"
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
        <DialogTitle sx={{ bgcolor: '#333', borderBottom: '1px solid #444' }}>
          <Typography component="div">{t('flowSelect.editFlowName', '编辑流程图名称')}</Typography>
        </DialogTitle>
        <DialogContent sx={{ pt: 2, pb: 1, mt: 1 }}>
          <TextField
            autoFocus
            margin="dense"
            label={t('flowSelect.flowName', '流程图名称')}
            type="text"
            fullWidth
            variant="outlined"
            value={editDialog.newName}
            onChange={(e) => onNewFlowNameChange(e.target.value)}
            InputProps={{
              sx: {
                color: 'white',
              }
            }}
            InputLabelProps={{
              sx: {
                color: 'rgba(255, 255, 255, 0.7)',
              }
            }}
            sx={{
              '& .MuiOutlinedInput-root': {
                '& fieldset': {
                  borderColor: 'rgba(255, 255, 255, 0.23)',
                },
                '&:hover fieldset': {
                  borderColor: 'rgba(255, 255, 255, 0.87)',
                },
                '&.Mui-focused fieldset': {
                  borderColor: 'primary.main',
                },
              }
            }}
          />
        </DialogContent>
        <DialogActions sx={{ p: 2, pt: 1 }}>
          <Button
            onClick={onEditDialogClose}
            sx={{ color: 'rgba(255, 255, 255, 0.7)' }}
          >
            {t('common.cancel', '取消')}
          </Button>
          <Button
            onClick={onSaveFlowName}
            variant="contained"
            disabled={!editDialog.newName.trim() || loading}
          >
            {t('common.save', '保存')}
          </Button>
        </DialogActions>
      </Dialog>

      {/* 删除流程图确认对话框 */}
      <Dialog
        open={deleteDialog.open}
        onClose={onDeleteDialogClose}
        fullWidth
        maxWidth="xs"
        disableEnforceFocus={true}
        disableRestoreFocus={true}
        PaperProps={{
          sx: {
            bgcolor: '#2d2d2d',
            color: 'white',
            border: '1px solid #444'
          }
        }}
        disableEscapeKeyDown
      >
        <DialogTitle sx={{
          bgcolor: '#333',
          borderBottom: '1px solid #444',
          color: '#ff5252'
        }}>
          <Typography component="div">{t('flowEditor.deleteConfirmTitle', '确认删除流程图?')}</Typography>
        </DialogTitle>
        <DialogContent sx={{ pt: 2, pb: 1, mt: 1 }}>
          <Typography sx={{ mb: 2 }}>
            {t('flowEditor.deleteConfirmContent', '此操作无法撤销')}
          </Typography>
          {deleteDialog.flow?.name && (
            <Typography sx={{
              fontWeight: 'bold',
              fontSize: '1.1rem',
              p: 1,
              bgcolor: 'rgba(255, 0, 0, 0.1)',
              borderRadius: 1
            }}>
              "{deleteDialog.flow.name}"
            </Typography>
          )}
        </DialogContent>
        <DialogActions sx={{ p: 2, pt: 1 }}>
          <Button
            onClick={onDeleteDialogClose}
            sx={{ color: 'rgba(255, 255, 255, 0.7)' }}
          >
            {t('flowEditor.cancel', '取消')}
          </Button>
          <Button
            onClick={onConfirmDelete}
            variant="contained"
            color="error"
            disabled={loading}
          >
            {t('flowEditor.delete', '删除')}
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
};

export default FlowDialogs; 