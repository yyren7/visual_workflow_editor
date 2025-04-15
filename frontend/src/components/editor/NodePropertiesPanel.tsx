import React from 'react';
import {
  Box,
  Typography,
  IconButton
} from '@mui/material';
import InfoIcon from '@mui/icons-material/Info';
import CloseIcon from '@mui/icons-material/Close';
import NodeProperties from '../NodeProperties'; // Assuming NodeProperties is in parent dir
import { Node } from 'reactflow';
import { NodeData } from '../FlowEditor'; // Only NodeData needed now
import { useTranslation } from 'react-i18next'; // Import hook
import DraggableResizableContainer from '../DraggableResizableContainer'; // Import container

interface NodePropertiesPanelProps {
  node: Node<NodeData>; // Use 'node' instead of selectedNode
  isOpen: boolean;
  onClose: () => void;
  onNodeDataChange: (id: string, data: Partial<NodeData>) => void;
  initialPosition: { x: number; y: number };
}

const NodePropertiesPanel: React.FC<NodePropertiesPanelProps> = ({
  node,
  isOpen,
  onClose,
  onNodeDataChange,
  initialPosition,
}) => {
  const { t } = useTranslation(); // Use hook

  if (!isOpen || !node) { // Use renamed prop
    return null;
  }

  // 修改回调函数以接收 property 和 value
  const handlePropertyChange = (property: string, value: any) => {
    // 构建 { [property]: value } 结构并传递给上层
    onNodeDataChange(node.id, { [property]: value });
  };

  return (
    <DraggableResizableContainer
      title={t('flowEditor.nodeProperties')}
      icon={<InfoIcon fontSize="small" />}
      isOpen={isOpen} // Pass isOpen to container
      onClose={onClose} // Pass onClose to container
      defaultPosition={initialPosition} // Pass position
      defaultSize={{ width: 350, height: 450 }} // Define default size
      zIndex={6} // Ensure it's above other elements if needed
      resizable={true}
    >
      {/* Content goes inside the container */}
      <Box sx={{ p: 2, overflowY: 'auto', height: '100%', width: '100%' }}>
        {/* Pass node and the *new* adapted callback */}
        <NodeProperties node={node} onNodePropertyChange={handlePropertyChange} />
      </Box>
    </DraggableResizableContainer>
  );
};

export default NodePropertiesPanel; 