import React, { useState, FormEvent } from 'react';
import { Container, TextField, Button, Typography, Box } from '@mui/material';
import { registerUser, UserRegisterData } from '../api/api'; // 使用命名导入和类型
import { useNavigate } from 'react-router-dom';
import { useSnackbar } from 'notistack';
import { AxiosError } from 'axios';

const Register: React.FC = () => {
  const [username, setUsername] = useState<string>('');
  const [password, setPassword] = useState<string>('');
  const navigate = useNavigate();
  const { enqueueSnackbar } = useSnackbar();

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    try {
      const userData: UserRegisterData = {
        username,
        password,
      };
      
      const response = await registerUser(userData);
      console.log('注册成功', response); // 注册成功后的处理
      enqueueSnackbar('注册成功', { variant: 'success' });
      navigate('/login'); // 注册成功后导航到登录页面
    } catch (error) {
      console.error('注册失败', error);
      
      // 处理错误信息，确保类型安全
      let errorMessage = '未知错误';
      if (error instanceof AxiosError && error.response?.data?.detail) {
        errorMessage = error.response.data.detail;
      } else if (error instanceof Error) {
        errorMessage = error.message;
      }
      
      enqueueSnackbar('注册失败: ' + errorMessage, { variant: 'error' });
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