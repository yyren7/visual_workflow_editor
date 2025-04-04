// visual_workflow_editor/frontend/src/components/Login.tsx
import React, { useState, FormEvent, useEffect } from 'react';
import { Container, TextField, Button, Typography, Box, CircularProgress } from '@mui/material';
import { loginUser, UserLoginData, LoginResponse } from '../api/api.ts';
import { useNavigate } from 'react-router-dom';
import { useSnackbar } from 'notistack';
import { AxiosError } from 'axios';
import { useTranslation } from 'react-i18next';

// 定义表单验证的接口
interface FormErrors {
  username?: string;
  password?: string;
}

const Login: React.FC = () => {
  const { t } = useTranslation();
  const [username, setUsername] = useState<string>('');
  const [password, setPassword] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [errors, setErrors] = useState<FormErrors>({});
  const navigate = useNavigate();
  const { enqueueSnackbar } = useSnackbar();

  // 清理表单错误
  useEffect(() => {
    if (username) {
      setErrors(prev => ({ ...prev, username: undefined }));
    }
    if (password) {
      setErrors(prev => ({ ...prev, password: undefined }));
    }
  }, [username, password]);

  // 验证表单数据
  const validateForm = (): boolean => {
    const newErrors: FormErrors = {};
    let isValid = true;

    if (!username.trim()) {
      newErrors.username = t('login.errors.usernameRequired');
      isValid = false;
    }

    if (!password) {
      newErrors.password = t('login.errors.passwordRequired');
      isValid = false;
    } else if (password.length < 1) {
      newErrors.password = t('login.errors.passwordLength');
      isValid = false;
    }

    setErrors(newErrors);
    return isValid;
  };

  // 存储认证信息
  const saveAuthData = (token: string, userId: string): boolean => {
    try {
      // 主要存储方式
      localStorage.setItem('access_token', token);
      localStorage.setItem('user_id', userId);
      
      // 触发登录状态变化事件，通知NavBar更新
      window.dispatchEvent(new Event('loginChange'));
      return true;
    } catch (e) {
      console.error('Error saving authentication data:', e);
      return false;
    }
  };

  // 处理登录成功
  const handleLoginSuccess = (response: LoginResponse): void => {
    if (!response.access_token || !response.user_id) {
      enqueueSnackbar(t('login.noToken'), { variant: 'warning' });
      return;
    }
    
    const saved = saveAuthData(response.access_token, response.user_id);
    
    if (saved) {
      enqueueSnackbar(t('login.success'), { variant: 'success' });
      navigate('/select');
    } else {
      enqueueSnackbar(t('login.tokenError'), { variant: 'warning' });
    }
  };

  // 处理登录错误
  const handleLoginError = (error: unknown): void => {
    let errorMessage = t('common.unknown');
    
    if (error instanceof AxiosError) {
      if (error.response?.data?.detail) {
        // 处理后端返回的详细错误信息，但不直接显示后端原始错误
        const backendError = error.response.data.detail;
        if (typeof backendError === 'string' && backendError.includes('Incorrect')) {
          errorMessage = t('login.errors.invalidCredentials');
        } else {
          errorMessage = t('login.errors.serverError');
        }
      } else if (error.response?.status === 401) {
        errorMessage = t('login.errors.unauthorized');
      } else if (error.response?.status === 404) {
        errorMessage = t('login.errors.serviceUnavailable');
      } else if (error.request) {
        errorMessage = t('login.errors.noResponse');
      }
    } else if (error instanceof Error) {
      errorMessage = t('login.errors.networkError');
    }
    
    enqueueSnackbar(`${t('login.failed')}: ${errorMessage}`, { variant: 'error' });
  };

  // 提交表单
  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    
    // 表单验证
    if (!validateForm()) {
      return;
    }
    
    setLoading(true);
    
    try {
      // 准备用户数据
      const userData: UserLoginData = {
        username,
        password
      };
      
      // 调用登录API
      const response: LoginResponse = await loginUser(userData);
      
      // 处理登录成功
      handleLoginSuccess(response);
    } catch (error) {
      // 处理登录错误
      handleLoginError(error);
    } finally {
      setLoading(false);
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
            error={!!errors.username}
            helperText={errors.username}
            disabled={loading}
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
            error={!!errors.password}
            helperText={errors.password}
            disabled={loading}
          />
          <Button
            type="submit"
            fullWidth
            variant="contained"
            sx={{ mt: 3, mb: 2 }}
            disabled={loading}
          >
            {loading ? <CircularProgress size={24} /> : t('login.submit')}
          </Button>
          <Box sx={{ mt: 2, display: 'flex', justifyContent: 'center', flexDirection: 'column', alignItems: 'center' }}>
            <Button
              variant="text"
              color="primary"
              onClick={() => navigate('/register')}
              disabled={loading}
            >
              {t('login.noAccount')}
            </Button>
            
            <Button
              variant="contained"
              color="secondary"
              onClick={() => navigate('/submit')}
              sx={{ mt: 2, width: '100%' }}
              disabled={loading}
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