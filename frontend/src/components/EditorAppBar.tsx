import React, { useState, useCallback, useMemo } from 'react';
import {
  Box,
  IconButton,
  Tooltip,
  Paper,
  Menu,
  MenuItem,
  Divider,
  TextField,
  debounce,
  Typography,
  CircularProgress
} from '@mui/material';
import MenuIcon from '@mui/icons-material/Menu';
import AccountCircleIcon from '@mui/icons-material/AccountCircle';
import AddIcon from '@mui/icons-material/Add';
import SortIcon from '@mui/icons-material/Sort';
import LanguageSelector from './LanguageSelector';
import { useTranslation } from 'react-i18next';
import SaveIcon from '@mui/icons-material/Save';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import { formatDistanceToNow } from 'date-fns';
import { zhCN } from 'date-fns/locale/zh-CN';
import { enUS } from 'date-fns/locale/en-US';

// Props for the AppBar component
interface EditorAppBarProps {
  flowName: string;
  onFlowNameChange: (newName: string) => void;
  isAuthenticated: boolean;
  onToggleSidebar: () => void;
  onToggleGlobalVars: () => void;
  onToggleChat: () => void;
  onSelectFlowClick: () => void;
  onLayoutClick: () => void;
  onLogout: () => void;
  isSaving?: boolean;
  lastSaveTime?: string | null;
}

// Helper to get locale for date-fns
const getDateFnsLocale = (lang: string) => {
    switch (lang.split('-')[0]) {
        case 'zh': return zhCN;
        default: return enUS;
    }
};

const EditorAppBar: React.FC<EditorAppBarProps> = ({
  flowName,
  onFlowNameChange,
  isAuthenticated,
  onToggleSidebar,
  onToggleGlobalVars,
  onToggleChat,
  onSelectFlowClick,
  onLayoutClick,
  onLogout,
  isSaving,
  lastSaveTime,
}) => {
  const { t, i18n } = useTranslation();
  const [localFlowName, setLocalFlowName] = useState<string>(flowName);

  React.useEffect(() => {
      setLocalFlowName(flowName);
  }, [flowName]);

  const debouncedFlowNameChange = useCallback(
      debounce((newName: string) => {
          onFlowNameChange(newName);
      }, 500),
      [onFlowNameChange]
  );

  const handleLocalNameChange = (event: React.ChangeEvent<HTMLInputElement>) => {
      const newName = event.target.value;
      setLocalFlowName(newName);
      debouncedFlowNameChange(newName);
  };

  const [toggleMenuAnchorEl, setToggleMenuAnchorEl] = useState<null | HTMLElement>(null);
  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null);

  const handleToggleMenuOpen = (event: React.MouseEvent<HTMLButtonElement>) => {
    setToggleMenuAnchorEl(event.currentTarget);
  };
  const handleToggleMenuClose = () => {
    setToggleMenuAnchorEl(null);
  };
  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };
  const handleMenuClose = () => {
    setAnchorEl(null);
  };

  const handleUserMenuAction = (action: () => void) => {
      action();
      handleMenuClose();
  };

  const handleToggleMenuAction = (action: () => void) => {
      action();
      handleToggleMenuClose();
  };

  // Format the last save time
  const formattedLastSaveTime = useMemo(() => {
      if (!lastSaveTime) return null;
      try {
          const date = new Date(lastSaveTime);
          const locale = getDateFnsLocale(i18n.language);
          return formatDistanceToNow(date, { addSuffix: true, locale });
      } catch (e) {
          console.error("Error formatting date:", e);
          return "Invalid date";
      }
  }, [lastSaveTime, i18n.language]);

  return (
    <Paper elevation={2} sx={{
      p: 0.75,
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      borderRadius: 0,
      minHeight: '48px',
      bgcolor: '#1e1e1e',
      borderBottom: '1px solid #333',
      color: 'white',
      flexShrink: 0,
      zIndex: 10
    }}>
      {/* Left Side */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexGrow: 0 }}>
        <Tooltip title={t('flowEditor.toggleMenu')}>
          <IconButton color="inherit" onClick={handleToggleMenuOpen} size="small">
            <MenuIcon />
          </IconButton>
        </Tooltip>
        <Menu
          anchorEl={toggleMenuAnchorEl}
          open={Boolean(toggleMenuAnchorEl)}
          onClose={handleToggleMenuClose}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
          transformOrigin={{ vertical: 'top', horizontal: 'left' }}
          PaperProps={{
            sx: { bgcolor: '#333', color: 'white', '& .MuiMenuItem-root:hover': { bgcolor: 'rgba(255, 255, 255, 0.1)' }, '& .MuiDivider-root': { borderColor: 'rgba(255, 255, 255, 0.12)' } },
          }}
        >
          <MenuItem onClick={() => handleToggleMenuAction(onToggleGlobalVars)}>
            {t('flowEditor.toggleGlobalVars')}
          </MenuItem>
          <MenuItem onClick={() => handleToggleMenuAction(onToggleChat)}>
            {t('flowEditor.toggleChat')}
          </MenuItem>
        </Menu>

        <Tooltip title={t('flowEditor.addNode')}>
          <IconButton color="inherit" onClick={onToggleSidebar} size="small">
            <AddIcon />
          </IconButton>
        </Tooltip>

        <Tooltip title={t('flowEditor.autoLayout')}>
             <IconButton color="inherit" onClick={onLayoutClick} size="small">
                 <SortIcon />
             </IconButton>
        </Tooltip>

        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <TextField
            label={t('flowEditor.flowName')}
            variant="outlined"
            size="small"
            value={localFlowName}
            onChange={handleLocalNameChange}
            sx={{
              width: '250px',
              '& .MuiOutlinedInput-root': { color: 'white', height: '36px', '& fieldset': { borderColor: 'rgba(255, 255, 255, 0.23)' }, '&:hover fieldset': { borderColor: 'rgba(255, 255, 255, 0.23)' } },
              '& .MuiInputLabel-root': { color: 'rgba(255, 255, 255, 0.7)', transform: 'translate(14px, 9px) scale(0.75)', '&.MuiInputLabel-shrink': { transform: 'translate(14px, -6px) scale(0.75)' } },
            }}
          />
        </Box>
      </Box>

      {/* Center Area - Show Saving Status */}
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', flexGrow: 1, gap: 1, height: '24px' /* Fixed height */ }}>
          {isSaving && (
              <>
                  <CircularProgress size={16} color="inherit" />
                  <Typography variant="caption" sx={{ color: 'text.secondary' }}>{t('flowEditor.saving')}...</Typography>
              </>
          )}
          {!isSaving && lastSaveTime && (
              <Tooltip title={`${t('flowEditor.lastSaved')}: ${new Date(lastSaveTime).toLocaleString()}`}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, color: 'text.secondary' }}>
                       <SaveIcon fontSize="small" sx={{ fontSize: '1rem' }} />
                      <Typography variant="caption">
                          {formattedLastSaveTime}
                      </Typography>
                  </Box>
              </Tooltip>
          )}
          {/* Add indicator for save error? Maybe a tooltip on the save icon? */}
      </Box>

      {/* Right Side */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexGrow: 0 }}>
        <LanguageSelector />
        {isAuthenticated && (
          <>
            <IconButton color="inherit" onClick={handleMenuOpen} size="small">
              <AccountCircleIcon />
            </IconButton>
            <Menu
              anchorEl={anchorEl}
              open={Boolean(anchorEl)}
              onClose={handleMenuClose}
              anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
              transformOrigin={{ vertical: 'top', horizontal: 'right' }}
              PaperProps={{
                sx: { bgcolor: '#333', color: 'white', '& .MuiMenuItem-root:hover': { bgcolor: 'rgba(255, 255, 255, 0.1)' }, '& .MuiDivider-root': { borderColor: 'rgba(255, 255, 255, 0.12)' } },
              }}
            >
              <MenuItem onClick={() => handleUserMenuAction(onSelectFlowClick)}>
                {t('nav.flowSelect', '选择流程图')}
              </MenuItem>
              <Divider />
              <MenuItem onClick={() => handleUserMenuAction(onLogout)}>{t('nav.logout')}</MenuItem>
            </Menu>
          </>
        )}
      </Box>
    </Paper>
  );
};

export default EditorAppBar; 