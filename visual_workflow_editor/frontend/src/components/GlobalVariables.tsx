// visual_workflow_editor/frontend/src/components/GlobalVariables.tsx
import React, { useState, useCallback } from 'react';
import { Box, TextField, Button, Typography, List, ListItem, ListItemText, IconButton, Divider } from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import AddIcon from '@mui/icons-material/Add';
import SaveIcon from '@mui/icons-material/Save';
import UploadIcon from '@mui/icons-material/Upload';
import { useSnackbar, VariantType } from 'notistack';
import { saveAs } from 'file-saver';
import { useTranslation } from 'react-i18next';

// 定义变量类型
interface VariablesType {
  [key: string]: string;
}

/**
 * GlobalVariables Component
 *
 * This component manages global variables, allowing users to load, save, edit, add, and delete variables.
 */
const GlobalVariables: React.FC = () => {
  const { t } = useTranslation();
  const [variables, setVariables] = useState<VariablesType>({});
  const [newVariableName, setNewVariableName] = useState<string>('');
  const { enqueueSnackbar } = useSnackbar();

  /**
   * Loads variables from a JSON file.
   * @param {File} file - The file to load variables from.
   */
  const loadVariables = useCallback((file: File) => {
    const reader = new FileReader();
    reader.onload = (e: ProgressEvent<FileReader>) => {
      try {
        if (e.target && e.target.result) {
          const loadedVariables = JSON.parse(e.target.result as string);
          if (typeof loadedVariables === 'object' && loadedVariables !== null) {
            setVariables(loadedVariables);
            enqueueSnackbar(t('globalVariables.loadSuccess'), { variant: 'success' });
          } else {
            enqueueSnackbar(t('globalVariables.invalidFormat'), { variant: 'error' });
          }
        }
      } catch (error) {
        enqueueSnackbar(t('globalVariables.loadError'), { variant: 'error' });
        console.error("Error loading variables:", error);
      }
    };
    reader.onerror = () => {
      enqueueSnackbar(t('globalVariables.readError'), { variant: 'error' });
    };
    reader.readAsText(file);
  }, [enqueueSnackbar, t]);

  /**
   * Saves variables to a JSON file.
   */
  const saveVariables = useCallback(() => {
    const jsonString = JSON.stringify(variables, null, 2);
    const blob = new Blob([jsonString], { type: 'application/json' });
    saveAs(blob, 'global_variables.json');
    enqueueSnackbar(t('globalVariables.saveSuccess'), { variant: 'success' });
  }, [variables, enqueueSnackbar, t]);

  /**
   * Gets a variable by name.
   * @param {string} name - The name of the variable.
   * @returns {string | undefined} - The value of the variable, or undefined if not found.
   */
  const getVariable = (name: string): string | undefined => {
    return variables[name];
  };

  /**
   * Sets a variable by name.
   * @param {string} name - The name of the variable.
   * @param {string} value - The value of the variable.
   */
  const setVariable = (name: string, value: string): void => {
    setVariables({ ...variables, [name]: value });
  };

  const handleVariableChange = (name: string, value: string): void => {
    setVariable(name, value);
  };

  const handleAddVariable = (): void => {
    if (newVariableName && !variables[newVariableName]) {
      setVariable(newVariableName, '');
      setNewVariableName('');
    } else if (variables[newVariableName]) {
      enqueueSnackbar(t('globalVariables.duplicateName'), { variant: 'error' });
    } else {
      enqueueSnackbar(t('globalVariables.emptyName'), { variant: 'warning' });
    }
  };

  const handleDeleteVariable = (name: string): void => {
    const { [name]: deleted, ...newVariables } = variables; // Destructure to remove the variable
    setVariables(newVariables);
  };

  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>): void => {
    const file = event.target.files?.[0];
    if (file) {
      loadVariables(file);
    }
  };

  return (
    <Box sx={{ padding: 2 }}>
      <Typography variant="h6">{t('globalVariables.title')}</Typography>
      <Divider />

      <Box sx={{ mt: 2, display: 'flex', alignItems: 'center' }}>
        <TextField
          label={t('globalVariables.newVariable')}
          variant="outlined"
          size="small"
          value={newVariableName}
          onChange={(e) => setNewVariableName(e.target.value)}
          sx={{ mr: 1 }}
        />
        <Button variant="contained" color="primary" size="small" startIcon={<AddIcon />} onClick={handleAddVariable}>
          {t('globalVariables.add')}
        </Button>
      </Box>

      <List sx={{ width: '100%', bgcolor: 'background.paper', mt: 2 }}>
        {Object.entries(variables).map(([name, value]) => (
          <ListItem
            key={name}
            secondaryAction={
              <IconButton edge="end" aria-label="delete" onClick={() => handleDeleteVariable(name)}>
                <DeleteIcon />
              </IconButton>
            }
          >
            <ListItemText
              primary={
                <TextField
                  label={t('globalVariables.variableValue')}
                  variant="outlined"
                  size="small"
                  value={value || ''}
                  onChange={(e) => handleVariableChange(name, e.target.value)}
                  fullWidth
                />
              }
              secondary={name}
            />
          </ListItem>
        ))}
      </List>

      <Divider sx={{ mt: 2, mb: 2 }} />

      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Box>
          <Button
            variant="contained"
            component="label"
            size="small"
            startIcon={<UploadIcon />}
          >
            {t('globalVariables.upload')}
            <input type="file" hidden onChange={handleFileUpload} accept=".json" />
          </Button>
        </Box>
        <Button variant="contained" color="success" size="small" startIcon={<SaveIcon />} onClick={saveVariables}>
          {t('globalVariables.save')}
        </Button>
      </Box>
    </Box>
  );
};

export default GlobalVariables;