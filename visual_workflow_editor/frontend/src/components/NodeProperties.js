import React, { useState, useEffect } from 'react';
import { Box, TextField, Typography, Accordion, AccordionSummary, AccordionDetails } from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import PropTypes from 'prop-types';

/**
 * NodeProperties Component
 *
 * This component displays and allows editing of the properties of a selected node.
 */
const NodeProperties = ({ node, onNodePropertyChange }) => {
  const [properties, setProperties] = useState({});

  useEffect(() => {
    if (node && node.data) {
      setProperties(node.data);
    } else {
      setProperties({});
    }
  }, [node]);

  /**
   * Updates a node property.
   * @param {string} property - The name of the property to update.
   * @param {any} value - The new value of the property.
   */
  const updateNodeProperty = (property, value) => {
    const newProperties = { ...properties, [property]: value };
    setProperties(newProperties);
    if (onNodePropertyChange) {
      onNodePropertyChange({ ...node, data: newProperties });
    }
  };

  const handleChange = (event) => {
    const { name, value } = event.target;
    updateNodeProperty(name, value);
  };

  if (!node) {
    return <Typography>No node selected.</Typography>;
  }

  return (
    <Box sx={{ padding: 2 }}>
      <Typography variant="h6">Node Properties</Typography>
      <Typography variant="subtitle1">Node ID: {node.id}</Typography>
      <Typography variant="subtitle1">Node Type: {node.type}</Typography>

      <Accordion defaultExpanded>
        <AccordionSummary
          expandIcon={<ExpandMoreIcon />}
          aria-controls="properties-content"
          id="properties-header"
        >
          <Typography>Data Properties</Typography>
        </AccordionSummary>
        <AccordionDetails>
          {Object.entries(properties).map(([key, value]) => (
            <TextField
              key={key}
              label={key}
              name={key}
              value={value || ''} // Ensure a default value to avoid uncontrolled component warning
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

NodeProperties.propTypes = {
  node: PropTypes.shape({
    id: PropTypes.string.isRequired,
    type: PropTypes.string.isRequired,
    data: PropTypes.object,
  }),
  onNodePropertyChange: PropTypes.func.isRequired,
};

export default NodeProperties;
