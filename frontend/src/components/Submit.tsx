// visual_workflow_editor/frontend/src/components/Submit.tsx
import React, { useState } from 'react';
import { 
  Container, 
  Typography, 
  Box, 
  Button, 
  TextField, 
  Paper,
  Snackbar,
  Alert
} from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { sendEmail } from '../api/api'; // 引入 sendEmail 函数
import { useTranslation } from 'react-i18next';

/**
 * 提交界面组件
 * 此界面无需登录即可访问，用户可以发送邮件
 */
const Submit: React.FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [loading, setLoading] = useState(false);
  const [openSnackbar, setOpenSnackbar] = useState(false);
  const [snackbarMessage, setSnackbarMessage] = useState('');
  const [snackbarSeverity, setSnackbarSeverity] = useState<'success' | 'error'>('success');
  
  const handleSendEmail = async () => {
    if (!title.trim()) {
      setSnackbarMessage(t('submit.emptyTitle'));
      setSnackbarSeverity('error');
      setOpenSnackbar(true);
      return;
    }
    
    if (!content.trim()) {
      setSnackbarMessage(t('submit.emptyContent'));
      setSnackbarSeverity('error');
      setOpenSnackbar(true);
      return;
    }
    
    setLoading(true);
    
    try {
      // 调用 api.ts 中的 sendEmail 函数
      await sendEmail(title, content);
      
      // 显示成功消息
      setSnackbarMessage(t('submit.success'));
      setSnackbarSeverity('success');
      setOpenSnackbar(true);
      
      // 重置表单
      setTitle('');
      setContent('');
      
      // 1.5秒后跳转到登录页面
      setTimeout(() => {
        navigate('/login');
      }, 1500);
      
    } catch (error: any) {
      console.error('发送邮件失败:', error);
      setSnackbarMessage(error.response?.data?.message || t('submit.error')); // 显示后端返回的错误信息
      setSnackbarSeverity('error');
      setOpenSnackbar(true);
    } finally {
      setLoading(false);
    }
  };
  
  return (
    <Container component="main" maxWidth="md">
      <Box
        sx={{
          marginTop: 8,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
        }}
      >
        <Typography component="h1" variant="h4" gutterBottom>
          {t('submit.title')}
        </Typography>
        <Typography variant="body1" paragraph>
          {t('submit.description')}
        </Typography>
        
        <Paper elevation={3} sx={{ p: 4, mt: 2, width: '100%', maxWidth: 600 }}>
          <TextField
            margin="normal"
            required
            fullWidth
            id="title"
            label={t('submit.emailTitle')}
            name="title"
            autoFocus
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
          
          <TextField
            margin="normal"
            required
            fullWidth
            name="content"
            label={t('submit.emailContent')}
            id="content"
            multiline
            rows={6}
            value={content}
            onChange={(e) => setContent(e.target.value)}
          />
          
          <Snackbar
            open={openSnackbar}
            autoHideDuration={3000}
            onClose={() => setOpenSnackbar(false)}
            anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
          >
            <Alert onClose={() => setOpenSnackbar(false)} severity={snackbarSeverity} sx={{ width: '100%' }}>
              {snackbarMessage}
            </Alert>
          </Snackbar>
          
          <Box sx={{ mt: 4, display: 'flex', gap: 2, justifyContent: 'space-between' }}>
            <Button 
              variant="outlined" 
              color="primary"
              onClick={() => navigate('/login')}
            >
              {t('submit.backToLogin')}
            </Button>
            
            <Button 
              variant="contained" 
              color="primary"
              onClick={handleSendEmail}
              disabled={loading}
            >
              {loading ? t('submit.sending') : t('submit.sendEmail')}
            </Button>
          </Box>
        </Paper>
      </Box>
    </Container>
  );
};

export default Submit;