import React from 'react';
import FlowVariables from '../FlowVariables'; // Assuming FlowVariables is in parent dir
import DraggableResizableContainer from '../DraggableResizableContainer'; // Import container
import { useTranslation } from 'react-i18next'; // Import hook
import CodeIcon from '@mui/icons-material/Code'; // Import icon
import { Box } from '@mui/material';

// Define props
interface FlowVariablesPanelProps {
  isOpen: boolean;
  onClose: () => void;
  initialPosition: { x: number; y: number };
}

const FlowVariablesPanel: React.FC<FlowVariablesPanelProps> = ({ isOpen, onClose, initialPosition }) => {
  const { t } = useTranslation(); // Use hook

  if (!isOpen) { // Don't render if closed
    return null;
  }

  return (
      <DraggableResizableContainer
        title={t('flowEditor.flowVariables')}
        icon={<CodeIcon fontSize="small" />}
        isOpen={isOpen}
        onClose={onClose}
        defaultPosition={initialPosition}
        defaultSize={{ width: 600, height: 320 }} // Define default size
        zIndex={5}
        resizable={true} // Allow resizing
      >
        {/* FlowVariables content goes inside */}
        <Box sx={{ p: 1, height: '100%', width: '100%', overflow: 'auto' }}>
             <FlowVariables />
        </Box>
      </DraggableResizableContainer>
  );
};

export default FlowVariablesPanel; 