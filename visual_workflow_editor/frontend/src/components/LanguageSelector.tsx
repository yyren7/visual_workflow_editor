import React, { useState } from 'react';
import { Button, Menu, MenuItem } from '@mui/material';
import LanguageIcon from '@mui/icons-material/Language';
import { useTranslation } from 'react-i18next';

/**
 * LanguageSelector Component
 * 
 * Allows users to switch between different languages in the application.
 */
const LanguageSelector: React.FC = () => {
  const { i18n } = useTranslation();
  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null);
  const open = Boolean(anchorEl);

  const handleClick = (event: React.MouseEvent<HTMLButtonElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleClose = () => {
    setAnchorEl(null);
  };

  const changeLanguage = (lng: string) => {
    i18n.changeLanguage(lng);
    handleClose();
  };

  return (
    <>
      <Button
        color="inherit"
        startIcon={<LanguageIcon />}
        onClick={handleClick}
      >
        {i18n.language === 'zh' ? '中文' : 'English'}
      </Button>
      <Menu
        anchorEl={anchorEl}
        open={open}
        onClose={handleClose}
      >
        <MenuItem onClick={() => changeLanguage('zh')}>中文</MenuItem>
        <MenuItem onClick={() => changeLanguage('en')}>English</MenuItem>
      </Menu>
    </>
  );
};

export default LanguageSelector;