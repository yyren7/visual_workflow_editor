import React from 'react';
import {
  Box,
  // CircularProgress, // Removed
  // Typography // Removed
} from '@mui/material';
import ChatInterface from '../ChatInterface'; // Assuming ChatInterface is in parent dir
import DraggableResizableContainer from '../DraggableResizableContainer'; // Import container
import { useTranslation } from 'react-i18next'; // Import hook
import ChatIcon from '@mui/icons-material/Chat'; // Import icon

interface ChatPanelProps {
  // flowId: string | undefined; // Keep flowId
  flowId: string; // Should be guaranteed non-null if panel is open
  // isLoading: boolean; // Removed
  // onChatCreated: (newChatId: string) => void; // Removed
  isOpen: boolean;
  onClose: () => void;
  initialPosition: { x: number; y: number };
  onNodeSelect: (nodeId: string, position?: { x: number; y: number }) => void;
}

const ChatPanel: React.FC<ChatPanelProps> = ({
  flowId,
  // isLoading,
  // onChatCreated,
  isOpen,
  onClose,
  initialPosition,
  onNodeSelect
}) => {
  const { t } = useTranslation(); // Use hook

  if (!isOpen) { // Don't render if closed
    return null;
  }

  return (
      <DraggableResizableContainer
        title={t('flowEditor.chatAssistant')}
        icon={<ChatIcon fontSize="small" />}
        isOpen={isOpen}
        onClose={onClose}
        defaultPosition={initialPosition}
        defaultSize={{ width: 700, height: 600 }} // Define default size
        zIndex={5}
        resizable={true}
      >
        {/* ChatInterface content goes inside */}
        <Box sx={{ height: '100%', width: '100%', display: 'flex', flexDirection: 'column', bgcolor: '#222' /* Ensure bg for content */ }}>
          {/* Remove loading state from here */}
          {/* Pass required props to ChatInterface */}
           <ChatInterface
             flowId={flowId}
             onNodeSelect={onNodeSelect} // Pass selection handler
             // onChatCreated is likely handled internally now or via Redux
           />
        </Box>
      </DraggableResizableContainer>

    // <Box sx={{ height: '100%', width: '100%', display: 'flex', flexDirection: 'column' }}>
    //   {isLoading ? (
    //     {/* ... loading removed ... */}
    //   ) : (
    //     <ChatInterface
    //       flowId={flowId}
    //       onChatCreated={onChatCreated}
    //       onNodeSelect={onNodeSelect} // Need to add this prop to ChatInterface definition
    //     />
    //   )}
    // </Box>
  );
};

export default ChatPanel; 