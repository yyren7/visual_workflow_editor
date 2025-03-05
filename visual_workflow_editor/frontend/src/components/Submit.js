import React from 'react';
import { Container, Typography, Box, Button } from '@mui/material';
import { useNavigate } from 'react-router-dom';

/**
 * 提交界面组件
 * 此界面无需登录即可访问
 */
const Submit = () => {
  const navigate = useNavigate();
  
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
          提交界面
        </Typography>
        <Typography variant="body1" paragraph>
          这是一个公开访问的提交界面，无需登录即可查看。
        </Typography>
        <Typography variant="body1" paragraph>
          您可以在此页面提交您的工作流程、问题反馈或其他内容。
        </Typography>
        
        <Box sx={{ mt: 4, display: 'flex', gap: 2 }}>
          <Button 
            variant="contained" 
            color="primary"
            onClick={() => navigate('/login')}
          >
            返回登录
          </Button>
          
          <Button 
            variant="outlined" 
            color="primary"
            onClick={() => navigate('/flow')}
          >
            前往流程编辑器
            {/* 注意：这个按钮会将用户引导到受保护的路由，如果未登录将被重定向到登录页面 */}
          </Button>
        </Box>
      </Box>
    </Container>
  );
};

export default Submit;