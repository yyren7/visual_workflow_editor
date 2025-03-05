import React, { useState } from 'react';
import { Container, TextField, Button, Typography, Box } from '@mui/material';
import { registerUser } from '../api/api'; // 使用命名导入
import { useNavigate } from 'react-router-dom';
import { useSnackbar } from 'notistack';

const Register = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const navigate = useNavigate();
  const { enqueueSnackbar } = useSnackbar();

  const handleSubmit = async (event) => {
    event.preventDefault();
    try {
      const response = await registerUser({ // 调用 registerUser API
        username,
        password,
      });
      console.log('注册成功', response.data); // 注册成功后的处理
      enqueueSnackbar('注册成功', { variant: 'success' });
      navigate('/login'); // 注册成功后导航到登录页面
    } catch (error) {
      console.error('注册失败', error); // 注册失败后的处理
      enqueueSnackbar('注册失败: ' + (error.response?.data?.detail || '未知错误'), { variant: 'error' });
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
          注册
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
            注册
          </Button>
          <Box sx={{ display: 'flex', justifyContent: 'center' }}>
            <Button
              variant="text"
              color="primary"
              onClick={() => navigate('/login')}
              sx={{ textAlign: 'center' }}
            >
              已有账号？去登录
            </Button>
          </Box>
        </Box>
      </Box>
    </Container>
  );
};

export default Register;