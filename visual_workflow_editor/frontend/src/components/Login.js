import React, { useState } from 'react';
import { Container, TextField, Button, Typography, Box } from '@mui/material';
import { loginUser } from '../api/api';
import { useNavigate } from 'react-router-dom';
import { useSnackbar } from 'notistack';

const Login = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const navigate = useNavigate();
  const { enqueueSnackbar } = useSnackbar();

  const handleSubmit = async (event) => {
    event.preventDefault();
    try {
      // 直接传递用户名和密码对象，api.js中会将其转换为表单数据
      const response = await loginUser({
        username,
        password
      });
      
      // 先判断并存储token
      if (response.access_token) {
        try {
          localStorage.setItem('access_token', response.access_token); // 存储 token
          
          // 触发登录状态变化事件，通知NavBar更新
          window.dispatchEvent(new Event('loginChange'));
          
          enqueueSnackbar('登录成功', { variant: 'success' });
          // 成功存储token后再导航
          navigate('/flow');
        } catch (e) { // 捕获 localStorage.setItem 异常
          console.error('Error saving access token to localStorage:', e);
          enqueueSnackbar('登录成功，但令牌存储失败', { variant: 'warning' }); // 提示警告 Snackbar
        }
      } else {
        console.error('Access token not found in response');
        enqueueSnackbar('登录成功，但未收到有效的认证令牌', { variant: 'warning' });
      }
    } catch (error) {
      console.error('Login Error:', error);
      console.error('登录失败', error);
      enqueueSnackbar('登录失败: ' + (error.response?.data?.detail || '未知错误'), { variant: 'error' });
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
          登录
        </Typography>
        <Box component="form" noValidate onSubmit={handleSubmit} sx={{ mt: 1 }}>
          <TextField
            margin="normal"
            required
            fullWidth
            id="username"
            label="用户名"
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
            label="密码"
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
            登录
          </Button>
          <Box sx={{ mt: 2, display: 'flex', justifyContent: 'center', flexDirection: 'column', alignItems: 'center' }}>
            <Button
              variant="text"
              color="primary"
              onClick={() => navigate('/register')}
            >
              没有账号？去注册
            </Button>
            
            <Button
              variant="contained"
              color="secondary"
              onClick={() => navigate('/submit')}
              sx={{ mt: 2, width: '100%' }}
            >
              前往提交页面
            </Button>
          </Box>
        </Box>
      </Box>
    </Container>
  );
};

export default Login;