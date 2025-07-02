import { useRef, useCallback } from 'react';
import { 
  OnChatEventCallback, 
  OnChatErrorCallback, 
  OnChatCloseCallback 
} from '../../api/chatApi';
import { DisplayMessage } from './types';

export const useSSEHandler = () => {
  const streamingAssistantMsgIdRef = useRef<string | null>(null);
  const closeEventSourceRef = useRef<(() => void) | null>(null);

  // Create SSE event handler for sending messages
  const createSendMessageHandler = useCallback((
    setMessages: React.Dispatch<React.SetStateAction<DisplayMessage[]>>,
    setError: React.Dispatch<React.SetStateAction<string | null>>,
    setIsSending: React.Dispatch<React.SetStateAction<boolean>>
  ): OnChatEventCallback => {
    return (event) => {
      console.log("Received SSE Event:", JSON.stringify(event));

      let capturedStreamEndId: string | null = null;
      if (event.type === 'stream_end') {
        capturedStreamEndId = streamingAssistantMsgIdRef.current;
      }

      setMessages(prevMessages => {
        const newMessages = [...prevMessages];
        const currentStreamingMsgIndex = newMessages.findIndex(
          msg => msg.timestamp === streamingAssistantMsgIdRef.current && msg.type === 'text'
        );

        switch (event.type) {
          case 'user_message_saved':
            const { client_message_id, server_message_timestamp } = event.data as { 
              client_message_id: string, 
              server_message_timestamp: string, 
              content: string 
            };
            const userMsgIndex = newMessages.findIndex(
              msg => msg.timestamp === client_message_id && msg.role === 'user'
            );
            if (userMsgIndex !== -1) {
              newMessages[userMsgIndex] = {
                ...newMessages[userMsgIndex],
                timestamp: server_message_timestamp,
              };
            }
            break;

          case 'token':
            const token = event.data;
            const currentStreamingId = streamingAssistantMsgIdRef.current;
            const streamingMsgIndex = newMessages.findIndex(
              msg => msg.timestamp === currentStreamingId && msg.type === 'text'
            );

            if (streamingMsgIndex !== -1) {
              newMessages[streamingMsgIndex] = {
                ...newMessages[streamingMsgIndex],
                content: newMessages[streamingMsgIndex].content + token,
                isStreaming: true,
              };
            } else if (token) {
              const assistantMessageId = currentStreamingId || `assistant-${Date.now()}`;
              if (!currentStreamingId) {
                streamingAssistantMsgIdRef.current = assistantMessageId;
              }
              newMessages.push({
                role: 'assistant',
                content: token,
                timestamp: assistantMessageId,
                type: 'text',
                isStreaming: true,
              });
            }
            break;

          case 'tool_start':
            const toolStartMessage: DisplayMessage = {
              role: 'assistant',
              content: '',
              timestamp: `tool-${event.data.name}-${Date.now()}`,
              type: 'tool_status',
              toolName: event.data.name,
              toolInput: event.data.input,
              toolStatus: 'running',
              isStreaming: false,
            };
            if (currentStreamingMsgIndex !== -1) {
              newMessages.splice(currentStreamingMsgIndex, 0, toolStartMessage);
            } else {
              newMessages.push(toolStartMessage);
            }
            break;

          case 'tool_end':
            const toolEndMsgIndex = newMessages.findLastIndex(msg =>
              msg.type === 'tool_status' &&
              msg.toolName === event.data.name &&
              msg.toolStatus === 'running'
            );
            if (toolEndMsgIndex !== -1) {
              newMessages[toolEndMsgIndex] = {
                ...newMessages[toolEndMsgIndex],
                toolStatus: 'completed',
                toolOutputSummary: event.data.output_summary,
              };
            }
            break;

          case 'stream_end':
            const finishedMsgIndex = newMessages.findIndex(msg => msg.timestamp === capturedStreamEndId);
            if (finishedMsgIndex !== -1) {
              newMessages[finishedMsgIndex] = {
                ...newMessages[finishedMsgIndex],
                isStreaming: false
              };
            } else {
              const lastStreamingMsgIndex = newMessages.findLastIndex(msg =>
                msg.role === 'assistant' && msg.isStreaming === true
              );
              if (lastStreamingMsgIndex !== -1) {
                newMessages[lastStreamingMsgIndex] = { 
                  ...newMessages[lastStreamingMsgIndex], 
                  isStreaming: false 
                };
              }
            }
            break;

          case 'error':
            const errorData = event.data;
            const errorMessage = `错误: ${errorData.message || '未知错误'}`;
            setError(errorMessage);
            setIsSending(false);
            break;

          case 'ping':
            console.log("Received ping event from server.");
            break;

          default:
            console.warn("Received unknown event type:", event);
        }
        return newMessages;
      });
    };
  }, []);

  // Create error handler
  const createErrorHandler = useCallback((
    setError: React.Dispatch<React.SetStateAction<string | null>>,
    setIsSending: React.Dispatch<React.SetStateAction<boolean>>
  ): OnChatErrorCallback => {
    return (error) => {
      console.error("Chat API Error:", error);
      setError(error.message || "连接错误");
      setIsSending(false);
    };
  }, []);

  // Create close handler
  const createCloseHandler = useCallback((
    setIsSending: React.Dispatch<React.SetStateAction<boolean>>
  ): OnChatCloseCallback => {
    return () => {
      console.log("Chat EventSource closed.");
      setIsSending(false);
      streamingAssistantMsgIdRef.current = null;
      closeEventSourceRef.current = null;
    };
  }, []);

  // Close active connections
  const closeActiveConnection = useCallback(() => {
    if (closeEventSourceRef.current) {
      console.log("Closing active EventSource connection.");
      closeEventSourceRef.current();
      closeEventSourceRef.current = null;
    }
  }, []);

  return {
    streamingAssistantMsgIdRef,
    closeEventSourceRef,
    createSendMessageHandler,
    createErrorHandler, 
    createCloseHandler,
    closeActiveConnection,
  };
}; 