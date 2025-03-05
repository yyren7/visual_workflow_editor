// frontend/src/components/GlobalVariables.tsx
import React, { useState, useCallback } from 'react';
import { Box, TextField, Button, Typography, List, ListItem, ListItemText, IconButton, Divider } from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import AddIcon from '@mui/icons-material/Add';
import SaveIcon from '@mui/icons-material/Save';
import UploadIcon from '@mui/icons-material/Upload';
import { useSnackbar, VariantType } from 'notistack';
import { saveAs } from 'file-saver';

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
            enqueueSnackbar('Global variables loaded successfully!', { variant: 'success' });
          } else {
            enqueueSnackbar('Invalid JSON format in file.', { variant: 'error' });
          }
        }
      } catch (error) {
        enqueueSnackbar('Error parsing JSON file.', { variant: 'error' });
        console.error("Error loading variables:", error);
      }
    };
    reader.onerror = () => {
      enqueueSnackbar('Error reading the file.', { variant: 'error' });
    };
    reader.readAsText(file);
  }, [enqueueSnackbar]);

  /**
   * Saves variables to a JSON file.
   */
  const saveVariables = useCallback(() => {
    const jsonString = JSON.stringify(variables, null, 2);
    const blob = new Blob([jsonString], { type: 'application/json' });
    saveAs(blob, 'global_variables.json');
    enqueueSnackbar('Global variables saved successfully!', { variant: 'success' });
  }, [variables, enqueueSnackbar]);

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
      enqueueSnackbar('Variable name already exists.', { variant: 'error' });
    } else {
      enqueueSnackbar('Please enter a variable name.', { variant: 'warning' });
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
      <Typography variant="h6">Global Variables</Typography>
      <Divider />

      <Box sx={{ mt: 2, display: 'flex', alignItems: 'center' }}>
        <TextField
          label="New Variable Name"
          variant="outlined"
          size="small"
          value={newVariableName}
          onChange={(e) => setNewVariableName(e.target.value)}
          sx={{ mr: 1 }}
        />
        <Button variant="contained" color="primary" size="small" startIcon={<AddIcon />} onClick={handleAddVariable}>
          Add
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
                  label="Variable Value"
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
            Upload Variables
            <input type="file" hidden onChange={handleFileUpload} accept=".json" />
          </Button>
        </Box>
        <Button variant="contained" color="success" size="small" startIcon={<SaveIcon />} onClick={saveVariables}>
          Save Variables
        </Button>
      </Box>
    </Box>
  );
};

export default GlobalVariables;