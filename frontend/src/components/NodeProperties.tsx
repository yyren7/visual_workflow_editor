// visual_workflow_editor/frontend/src/components/NodeProperties.tsx
import React, { ChangeEvent } from 'react';
import { Box, TextField, Typography, Accordion, AccordionSummary, AccordionDetails } from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { Node } from 'reactflow';
import { NodeData } from './FlowEditor';
import { useTranslation } from 'react-i18next';

interface NodePropertiesProps {
  node: Node<NodeData> | null;
  onNodePropertyChange: (property: string, value: any) => void;
}

/**
 * NodeProperties Component
 *
 * This component displays and allows editing of the properties of a selected node.
 */
const NodeProperties: React.FC<NodePropertiesProps> = ({ node, onNodePropertyChange }) => {
  const { t } = useTranslation();

  const handleChange = (event: ChangeEvent<HTMLInputElement>): void => {
    const { name, value } = event.target;
    if (node && onNodePropertyChange) {
      onNodePropertyChange(name, value);
    }
  };

  if (!node) {
    return <Typography>{t('nodeProperties.noNode')}</Typography>;
  }

  return (
    <Box sx={{ padding: 2 }}>
      <Typography variant="h6">{t('nodeProperties.title')}</Typography>
      <Typography variant="subtitle1">{t('nodeProperties.nodeId')}: {node.id}</Typography>
      <Typography variant="subtitle1">{t('nodeProperties.nodeType')}: {node.type}</Typography>

      <Accordion defaultExpanded>
        <AccordionSummary
          expandIcon={<ExpandMoreIcon />}
          aria-controls="properties-content"
          id="properties-header"
        >
          <Typography>{t('nodeProperties.dataProperties')}</Typography>
        </AccordionSummary>
        <AccordionDetails>
          {/* Filter entries to only include simple types (string/number/boolean) for editing */}
          {Object.entries(node.data || {})
            .filter(([key, value]) => 
              typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean'
            )
            .map(([key, value]) => (
            <TextField
              key={key}
              label={key}
              name={key}
              // Handle boolean specifically if needed, e.g., with a Switch or Checkbox
              // For now, just display boolean as string, but ensure correct value is passed
              value={typeof value === 'boolean' ? String(value) : value || ''}
              onChange={handleChange} 
              fullWidth
              margin="normal"
              variant="outlined"
              // Disable editing for specific keys if necessary
              // disabled={key === 'id' || key === 'type'} 
            />
          ))}
          {/* Optionally, display complex properties (arrays/objects) in a read-only way */}
          {Object.entries(node.data || {})
            .filter(([key, value]) => 
              typeof value === 'object' && value !== null // Includes arrays and objects
            )
            .map(([key, value]) => (
              <Box key={key} sx={{ mt: 2, fontFamily: 'monospace', fontSize: '0.8rem' }}>
                <Typography variant="caption" sx={{ fontWeight: 'bold' }}>{key}: (Read-only)</Typography>
                <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-all', background: 'rgba(255,255,255,0.05)', padding: '5px', borderRadius: '3px' }}>
                  {JSON.stringify(value, null, 2)}
                </pre>
              </Box>
            ))}
        </AccordionDetails>
      </Accordion>
    </Box>
  );
};

export default NodeProperties;