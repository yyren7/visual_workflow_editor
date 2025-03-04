// frontend/src/components/NodeSelector.js
import React from 'react';
import { Box, List, ListItem, ListItemButton, ListItemText } from '@mui/material';
import PropTypes from 'prop-types';

const nodeTypes = [
  {
    id: 'input',
    label: 'Input Node',
  },
  {
    id: 'output',
    label: 'Output Node',
  },
  {
    id: 'process',
    label: 'Process Node',
  },
  {
    id: 'decision',
    label: 'Decision Node',
  },
];

/**
 * NodeSelector Component
 *
 * This component displays a list of available node types that can be added to the flow.
 * It provides a method to retrieve the available node types.
 */
const NodeSelector = ({ onNodeSelect }) => {
  /**
   * Gets the available node types.
   * @returns {Array<object>} - An array of node type objects.
   */
  const getNodeTypes = () => {
    return nodeTypes;
  };

  return (
    <Box sx={{ width: '100%', bgcolor: 'background.paper' }}>
      <nav aria-label="node types">
        <List>
          {getNodeTypes().map((nodeType) => (
            <ListItem disablePadding key={nodeType.id}>
              <ListItemButton onClick={() => onNodeSelect(nodeType.id)}>
                <ListItemText primary={nodeType.label} />
              </ListItemButton>
            </ListItem>
          ))}
        </List>
      </nav>
    </Box>
  );
};

NodeSelector.propTypes = {
  onNodeSelect: PropTypes.func.isRequired,
};

export default NodeSelector;
