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
          {Object.entries(node.data || {}).map(([key, value]) => (
            <TextField
              key={key}
              label={key}
              name={key}
              value={value || ''}
              onChange={handleChange}
              fullWidth
              margin="normal"
              variant="outlined"
            />
          ))}
        </AccordionDetails>
      </Accordion>
    </Box>
  );
};

export default NodeProperties;