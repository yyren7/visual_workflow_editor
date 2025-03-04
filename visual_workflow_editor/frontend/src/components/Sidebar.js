## frontend/src/components/Sidebar.js
import React, { useCallback } from 'react';
import { Box, Drawer, Divider } from '@mui/material';
import NodeSelector from './NodeSelector';
import PropTypes from 'prop-types';
import { useReactFlow } from 'reactflow';

/**
 * Sidebar Component
 *
 * This component provides a sidebar with a NodeSelector for adding nodes to the flow.
 */
const Sidebar = ({ isOpen, toggleSidebar }) => {
  const { addNode } = useReactFlow();

  /**
   * Adds a node of the specified type to the flow.
   * @param {string} nodeType - The type of node to add.
   */
  const addNodeByType = useCallback((nodeType) => {
    const id = `${nodeType}-${Date.now()}`; // Generate a unique ID
    const newNode = {
      id: id,
      type: nodeType,
      data: { label: `${nodeType} Node` }, // Default label, can be customized
      position: { x: 100, y: 100 }, // Default position
    };
    addNode(newNode);
  }, [addNode]);

  const handleNodeSelect = (nodeType) => {
    addNodeByType(nodeType);
  };

  return (
    <Drawer
      anchor="left"
      open={isOpen}
      onClose={toggleSidebar}
      variant="persistent"
      sx={{
        width: 240,
        flexShrink: 0,
        '& .MuiDrawer-paper': {
          width: 240,
          boxSizing: 'border-box',
        },
      }}
    >
      <Box sx={{ overflow: 'auto' }}>
        <Divider />
        <NodeSelector onNodeSelect={handleNodeSelect} />
      </Box>
    </Drawer>
  );
};

Sidebar.propTypes = {
  isOpen: PropTypes.bool.isRequired,
  toggleSidebar: PropTypes.func.isRequired,
};

export default Sidebar;
