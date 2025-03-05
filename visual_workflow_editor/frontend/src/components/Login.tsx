// visual_workflow_editor/frontend/src/components/Login.tsx
import React, { useState, FormEvent } from 'react';
import { Container, TextField, Button, Typography, Box } from '@mui/material';
import { loginUser, UserLoginData, LoginResponse } from '../api/api.ts';
import { useNavigate } from 'react-router-dom';
import { useSnackbar } from 'notistack';
import { AxiosError } from 'axios';
import { useTranslation } from 'react-i18next';

const Login: React.FC = () => {
  const { t } = useTranslation();
  const [username, setUsername] = useState<string>('');
  const [password, setPassword] = useState<string>('');
  const navigate = useNavigate();
  const { enqueueSnackbar } = useSnackbar();

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    try {
      // 直接传递用户名和密码对象，api.js中会将其转换为表单数据
      const userData: UserLoginData = {
        username,
        password
      };
      
      const response: LoginResponse = await loginUser(userData);
      
      // 先判断并存储token
      if (response.access_token) {
        try {
          localStorage.setItem('access_token', response.access_token); // 存储 token
          
          // 触发登录状态变化事件，通知NavBar更新
          window.dispatchEvent(new Event('loginChange'));
          
          enqueueSnackbar(t('login.success'), { variant: 'success' });
          // 成功存储token后再导航
          navigate('/flow');
        } catch (e) { // 捕获 localStorage.setItem 异常
          console.error('Error saving access token to localStorage:', e);
          enqueueSnackbar(t('login.tokenError'), { variant: 'warning' }); // 提示警告 Snackbar
        }
      } else {
        console.error('Access token not found in response');
        enqueueSnackbar(t('login.noToken'), { variant: 'warning' });
      }
    } catch (error) {
      console.error('Login Error:', error);
      
      // 处理错误信息，确保类型安全
      let errorMessage = t('common.unknown');
      if (error instanceof AxiosError && error.response?.data?.detail) {
        errorMessage = error.response.data.detail;
      } else if (error instanceof Error) {
        errorMessage = error.message;
      }
      
      enqueueSnackbar(`${t('login.failed')}: ${errorMessage}`, { variant: 'error' });
    }
  };

  return (
    <Container component="main" maxWidth="xs">
      <Box
        sx={{
          marginTop: 8,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
        }}
      >
        <Typography component="h1" variant="h5">
          {t('login.title')}
        </Typography>
        <Box component="form" noValidate onSubmit={handleSubmit} sx={{ mt: 1 }}>
          <TextField
            margin="normal"
            required
            fullWidth
            id="username"
            label={t('login.username')}
            name="username"
            autoComplete="username"
            autoFocus
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />
          <TextField
            margin="normal"
            required
            fullWidth
            name="password"
            label={t('login.password')}
            type="password"
            id="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <Button
            type="submit"
            fullWidth
            variant="contained"
            sx={{ mt: 3, mb: 2 }}
          >
            {t('login.submit')}
          </Button>
          <Box sx={{ mt: 2, display: 'flex', justifyContent: 'center', flexDirection: 'column', alignItems: 'center' }}>
            <Button
              variant="text"
              color="primary"
              onClick={() => navigate('/register')}
            >
              {t('login.noAccount')}
            </Button>
            
            <Button
              variant="contained"
              color="secondary"
              onClick={() => navigate('/submit')}
              sx={{ mt: 2, width: '100%' }}
            >
              {t('login.goSubmit')}
            </Button>
          </Box>
        </Box>
      </Box>
    </Container>
  );
};

export default Login;