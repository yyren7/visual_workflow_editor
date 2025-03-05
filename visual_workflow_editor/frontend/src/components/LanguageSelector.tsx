// visual_workflow_editor/frontend/src/components/LanguageSelector.tsx
import React, { useState, useEffect } from 'react';
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

  // 添加effect来监听语言变化并触发页面更新
  useEffect(() => {
    // 当语言变更时，更新document的lang属性
    document.documentElement.lang = i18n.language;
    
    // 检查是否需要更新HTML标题
    const title = document.querySelector('title');
    if (title) {
      title.textContent = i18n.language === 'zh' ? '可视化工作流编辑器' : 'Visual Workflow Editor';
    }
  }, [i18n.language]);

  const handleClick = (event: React.MouseEvent<HTMLButtonElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleClose = () => {
    setAnchorEl(null);
  };

  const changeLanguage = (lng: string) => {
    i18n.changeLanguage(lng);
    localStorage.setItem('preferredLanguage', lng); // 存储用户语言偏好
    handleClose();
    
    // 触发自定义事件，通知其他组件语言已更改
    window.dispatchEvent(new Event('languageChanged'));
  };

  // 组件加载时检查用户之前的语言偏好
  useEffect(() => {
    const savedLanguage = localStorage.getItem('preferredLanguage');
    if (savedLanguage && savedLanguage !== i18n.language) {
      i18n.changeLanguage(savedLanguage);
    }
  }, [i18n]);

  return (
    <>
      <Button
        color="inherit"
        startIcon={<LanguageIcon />}
        onClick={handleClick}
        aria-label="select language"
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