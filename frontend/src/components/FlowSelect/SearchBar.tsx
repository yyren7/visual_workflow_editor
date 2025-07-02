import React from 'react';
import {
  Box,
  TextField,
  InputAdornment,
  Button,
  Divider
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import AddIcon from '@mui/icons-material/Add';
import { useTranslation } from 'react-i18next';
import { SearchBarProps } from './types';

const SearchBar: React.FC<SearchBarProps> = ({
  searchTerm,
  onSearchChange,
  onCreateNew,
  loading
}) => {
  const { t } = useTranslation();

  return (
    <>
      {/* 搜索框 */}
      <Box sx={{ mb: 2 }}>
        <TextField
          fullWidth
          variant="outlined"
          placeholder={t('flowSelect.search', '搜索流程图...')}
          value={searchTerm}
          onChange={(e) => onSearchChange(e.target.value)}
          size="small"
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon sx={{ color: 'rgba(255, 255, 255, 0.7)' }} />
              </InputAdornment>
            ),
            sx: {
              color: 'white',
              '& .MuiOutlinedInput-notchedOutline': {
                borderColor: 'rgba(255, 255, 255, 0.23)',
              },
              '&:hover .MuiOutlinedInput-notchedOutline': {
                borderColor: 'rgba(255, 255, 255, 0.87)',
              },
            }
          }}
        />
      </Box>

      {/* 创建新流程图按钮 */}
      <Box sx={{ mb: 2 }}>
        <Button
          fullWidth
          variant="outlined"
          startIcon={<AddIcon />}
          onClick={onCreateNew}
          disabled={loading}
          sx={{
            color: 'white',
            borderColor: 'rgba(255, 255, 255, 0.23)',
            '&:hover': {
              borderColor: 'rgba(255, 255, 255, 0.87)',
              bgcolor: 'rgba(255, 255, 255, 0.08)'
            }
          }}
        >
          {t('flowSelect.createNew', '创建新流程图')}
        </Button>
      </Box>

      <Divider sx={{ borderColor: 'rgba(255, 255, 255, 0.12)', mb: 2 }} />
    </>
  );
};

export default SearchBar; 