// visual_workflow_editor/frontend/src/components/NavBar.tsx
import React, { useState } from 'react';
import {
  AppBar,
  Toolbar,
  Typography,
  IconButton,
  Button,
  Box,
  Menu,
  MenuItem,
  Divider
} from '@mui/material';
import MenuIcon from '@mui/icons-material/Menu';
import AccountCircleIcon from '@mui/icons-material/AccountCircle';
import { useNavigate } from 'react-router-dom';
import i18n from '../i18n';
import LanguageSelector from './LanguageSelector';
import VersionInfo from './VersionInfo';
import { useAuth } from '../contexts/AuthContext';

const NavBar: React.FC = () => {
  // 使用i18n.t代替useTranslation
  const t = (key: string) => i18n.t(key);
  const navigate = useNavigate();
  const { isAuthenticated, logout } = useAuth();
  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null);
  
  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };
  
  const handleMenuClose = () => {
    setAnchorEl(null);
  };
  
  const handleLogout = () => {
    logout(); // 使用AuthContext提供的logout方法
    handleMenuClose();
  };
  
  return (
    <AppBar position="static">
      <Toolbar>
        <IconButton
          size="large"
          edge="start"
          color="inherit"
          aria-label="menu"
          sx={{ mr: 2 }}
        >
          <MenuIcon />
        </IconButton>
        <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
          {t('nav.flowEditor')}
        </Typography>
        
        <VersionInfo />
        
        <LanguageSelector />
        
        {isAuthenticated ? (
          <>
            <IconButton
              color="inherit"
              onClick={handleMenuOpen}
              aria-controls="user-menu"
              aria-haspopup="true"
            >
              <AccountCircleIcon />
            </IconButton>
            <Menu
              id="user-menu"
              anchorEl={anchorEl}
              open={Boolean(anchorEl)}
              onClose={handleMenuClose}
              anchorOrigin={{
                vertical: 'bottom',
                horizontal: 'right',
              }}
              transformOrigin={{
                vertical: 'top',
                horizontal: 'right',
              }}
            >
              <MenuItem onClick={() => {
                handleMenuClose();
                navigate('/flow');
              }}>
                {t('nav.flowEditor')}
              </MenuItem>
              <Divider />
              <MenuItem onClick={handleLogout}>{t('nav.logout')}</MenuItem>
            </Menu>
          </>
        ) : (
          <Box sx={{ display: 'flex' }}>
            <Button 
              color="inherit" 
              onClick={() => navigate('/login')}
              sx={{ mr: 1 }}
            >
              {t('nav.login')}
            </Button>
            <Button 
              color="inherit" 
              onClick={() => navigate('/register')}
            >
              {t('nav.register')}
            </Button>
          </Box>
        )}
      </Toolbar>
    </AppBar>
  );
};

export default NavBar;