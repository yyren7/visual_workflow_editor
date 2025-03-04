## frontend/src/components/ChatInterface.js
import React, { useState, useCallback } from 'react';
import { Box, TextField, Button, List, ListItem, ListItemText, Typography } from '@mui/material';
import PropTypes from 'prop-types';
import { generateNode, updateNodeByLLM } from '../api/api';
import { useSnackbar } from 'notistack';

/**
 * ChatInterface Component
 *
 * This component provides a chat interface for interacting with the LLM to generate and update nodes.
 */
const ChatInterface = ({ onAddNode, onUpdateNode }) => {
  const [message, setMessage] = useState('');
  const [chatHistory, setChatHistory] = useState([]);
  const { enqueueSnackbar } = useSnackbar();

  /**
   * Sends a message to the LLM and updates the chat history.
   * @param {string} message - The message to send.
   * @returns {string} - The response from the LLM.
   */
  const sendMessage = useCallback(async (message) => {
    try {
      // Check if the message is for generating a new node or updating an existing one
      if (message.toLowerCase().startsWith('generate node')) {
        const nodeData = await generateNode(message);
        onAddNode(nodeData);
        return "Node generated successfully!";
      } else if (message.toLowerCase().startsWith('update node')) {
        // Extract node ID and prompt from the message
        const parts = message.split(' ');
        const nodeId = parts[2]; // Assuming the node ID is the third word
        const prompt = parts.slice(3).join(' '); // The rest of the message is the prompt

        if (!nodeId || !prompt) {
          enqueueSnackbar('Invalid update node command. Please specify node ID and prompt.', { variant: 'error' });
          return "Invalid update node command.";
        }

        const updatedNodeData = await updateNodeByLLM(nodeId, prompt);
        onUpdateNode(nodeId, updatedNodeData);
        return `Node ${nodeId} updated successfully!`;
      } else {
        enqueueSnackbar('Invalid command. Please use "generate node" or "update node" command.', { variant: 'warning' });
        return "Invalid command. Please use 'generate node' or 'update node' command.";
      }
    } catch (error) {
      enqueueSnackbar(`Error processing message: ${error.message}`, { variant: 'error' });
      return `Error processing message: ${error.message}`;
    }
  }, [enqueueSnackbar, onAddNode, onUpdateNode]);

  /**
   * Handles the sending of a message.
   */
  const handleSendMessage = async () => {
    if (message.trim() !== '') {
      const response = await sendMessage(message);
      setChatHistory([...chatHistory, { type: 'user', text: message }, { type: 'bot', text: response }]);
      setMessage('');
    }
  };

  /**
   * Gets the chat history.
   * @returns {Array<object>} - An array of chat messages.
   */
  const getChatHistory = () => {
    return chatHistory;
  };

  return (
    <Box sx={{ padding: 2, display: 'flex', flexDirection: 'column', height: '100%' }}>
      <Box sx={{ flexGrow: 1, overflowY: 'auto', mb: 2 }}>
        <List>
          {getChatHistory().map((chat, index) => (
            <ListItem key={index} alignItems="flex-start">
              <ListItemText
                primary={
                  <Typography variant="subtitle2" color={chat.type === 'user' ? 'primary' : 'secondary'}>
                    {chat.type === 'user' ? 'You:' : 'Bot:'}
                  </Typography>
                }
                secondary={
                  <Typography variant="body2" color="textPrimary">
                    {chat.text}
                  </Typography>
                }
              />
            </ListItem>
          ))}
        </List>
      </Box>

      <Box sx={{ display: 'flex', alignItems: 'center' }}>
        <TextField
          label="Message"
          variant="outlined"
          fullWidth
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyPress={(e) => {
            if (e.key === 'Enter') {
              handleSendMessage();
            }
          }}
        />
        <Button variant="contained" color="primary" sx={{ ml: 1 }} onClick={handleSendMessage}>
          Send
        </Button>
      </Box>
    </Box>
  );
};

ChatInterface.propTypes = {
  onAddNode: PropTypes.func.isRequired,
  onUpdateNode: PropTypes.func.isRequired,
};

export default ChatInterface;
