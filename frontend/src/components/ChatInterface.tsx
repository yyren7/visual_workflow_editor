// visual_workflow_editor/frontend/src/components/ChatInterface.tsx
import React, { useState, useCallback, KeyboardEvent, ChangeEvent, useRef, useEffect } from 'react';
import { Box, TextField, Button, List, ListItem, ListItemText, Typography, CircularProgress } from '@mui/material';
import { generateNode, updateNodeByLLM, processWorkflow, WorkflowProcessResponse } from '../api/api';
import { useSnackbar } from 'notistack';
import { NodeData } from './FlowEditor';
import { useTranslation } from 'react-i18next';

// 聊天消息接口
interface ChatMessage {
  type: 'user' | 'bot';
  text: string;
  isLoading?: boolean;
  data?: any; // 存储API返回的数据
}

// 组件属性接口
interface ChatInterfaceProps {
  onAddNode: (nodeData: any) => void;
  onUpdateNode: (nodeId: string, updatedNodeData: { data: NodeData }) => void;
  onConnectNodes: (sourceId: string, targetId: string, label?: string) => void;
}

/**
 * ChatInterface Component
 *
 * This component provides a chat interface for interacting with the LLM to generate and update nodes.
 */
const ChatInterface: React.FC<ChatInterfaceProps> = ({ onAddNode, onUpdateNode, onConnectNodes }) => {
  const { t } = useTranslation();
  const [message, setMessage] = useState<string>('');
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const { enqueueSnackbar } = useSnackbar();
  const chatListRef = useRef<HTMLDivElement>(null);
  const [sessionId, setSessionId] = useState<string | undefined>(undefined);

  // 滚动到底部
  useEffect(() => {
    if (chatListRef.current) {
      chatListRef.current.scrollTop = chatListRef.current.scrollHeight;
    }
  }, [chatHistory]);

  /**
   * 处理工作流
   * @param {string} userMessage - 用户消息
   * @returns {Promise<WorkflowProcessResponse>} - 处理结果
   */
  const processUserWorkflow = async (userMessage: string): Promise<WorkflowProcessResponse> => {
    try {
      const response = await processWorkflow({
        prompt: userMessage,
        session_id: sessionId
      });
      
      // 更新会话ID
      if (response.session_id) {
        setSessionId(response.session_id);
      }
      
      return response;
    } catch (error) {
      console.error("处理工作流失败:", error);
      throw error;
    }
  };

  /**
   * 应用工作流结果
   * @param {WorkflowProcessResponse} result - 工作流处理结果
   * @returns {string} - 处理结果描述
   */
  const applyWorkflowResult = (result: WorkflowProcessResponse): string => {
    try {
      // 处理已创建的节点
      const createdNodes = result.created_nodes || {};
      const nodeIds = Object.keys(createdNodes);
      
      // 添加创建的节点
      nodeIds.forEach(nodeId => {
        const nodeData = createdNodes[nodeId];
        if (nodeData) {
          onAddNode({
            id: nodeId,
            type: nodeData.node_type,
            data: {
              label: nodeData.node_label,
              ...nodeData.properties
            }
          });
        }
      });
      
      // 处理节点连接
      result.step_results.forEach(step => {
        if (step.tool_action && step.tool_action.tool_type === 'node_connection' && step.tool_action.result.success) {
          const connectionData = step.tool_action.result.data;
          if (connectionData && connectionData.source && connectionData.target) {
            onConnectNodes(
              connectionData.source,
              connectionData.target,
              connectionData.label
            );
          }
        }
      });
      
      // 检查是否需要询问更多问题
      if (result.missing_info) {
        if (result.missing_info.data && result.missing_info.data.formatted_text) {
          return result.missing_info.data.formatted_text;
        } else if (Array.isArray(result.missing_info) && result.missing_info.length > 0) {
          // 直接显示问题列表
          return result.missing_info.join('\n');
        }
      }
      
      // 如果有摘要直接使用
      if (result.summary) {
        return result.summary;
      }
      
      // 返回操作结果摘要
      const nodeCount = nodeIds.length;
      const connectionCount = result.step_results.filter(
        step => step.tool_action && step.tool_action.tool_type === 'node_connection' && step.tool_action.result.success
      ).length;
      
      let summary = '';
      if (nodeCount > 0) {
        summary += `已创建 ${nodeCount} 个节点。`;
      }
      if (connectionCount > 0) {
        summary += `已建立 ${connectionCount} 个连接。`;
      }
      
      if (summary === '') {
        summary = '我已理解您的请求，但未执行任何节点操作。';
      }
      
      return summary;
    } catch (error) {
      console.error("应用工作流结果失败:", error);
      return "处理结果时出错";
    }
  };

  /**
   * 发送消息到LLM并更新聊天历史
   * @param {string} userMessage - 要发送的消息
   * @returns {Promise<string>} - LLM的响应
   */
  const sendMessage = useCallback(async (userMessage: string): Promise<string> => {
    try {
      // 优先使用新的工作流处理API
      const result = await processUserWorkflow(userMessage);
      
      // 应用工作流结果
      const responseMessage = applyWorkflowResult(result);
      
      return responseMessage;
    } catch (error) {
      // 如果新API失败，尝试使用旧的API
      try {
        // 检查是否为生成节点或更新节点的命令
        if (userMessage.toLowerCase().startsWith('generate node')) {
          const nodeData = await generateNode(userMessage);
          onAddNode(nodeData);
          return t('chat.nodeGenerated');
        } else if (userMessage.toLowerCase().startsWith('update node')) {
          // 提取节点ID和提示
          const parts = userMessage.split(' ');
          const nodeId = parts[2]; // 假设节点ID是第三个词
          const prompt = parts.slice(3).join(' '); // 消息的其余部分是提示

          if (!nodeId || !prompt) {
            enqueueSnackbar(t('chat.invalidUpdateCommand'), { variant: 'error' });
            return t('chat.invalidUpdateCommand');
          }

          const updatedNodeData = await updateNodeByLLM(nodeId, prompt);
          onUpdateNode(nodeId, updatedNodeData);
          return t('chat.nodeUpdated');
        } else {
          return "我理解您的请求，但无法执行。请尝试描述您希望创建的流程图。";
        }
      } catch (innerError) {
        const errorMessage = innerError instanceof Error ? innerError.message : t('common.unknown');
        enqueueSnackbar(`${t('chat.error')} ${errorMessage}`, { variant: 'error' });
        return `${t('chat.error')} ${errorMessage}`;
      }
    }
  }, [enqueueSnackbar, onAddNode, onUpdateNode, onConnectNodes, t]);

  /**
   * 处理发送消息
   */
  const handleSendMessage = async (): Promise<void> => {
    if (message.trim() !== '') {
      const userMessage: ChatMessage = { type: 'user', text: message };
      const loadingMessage: ChatMessage = { type: 'bot', text: '正在处理...', isLoading: true };
      
      // 添加用户消息和加载消息
      setChatHistory(prev => [...prev, userMessage, loadingMessage]);
      setMessage('');
      setIsProcessing(true);
      
      try {
        const response = await sendMessage(userMessage.text);
        
        // 替换加载消息为实际响应
        setChatHistory(prev => {
          const newHistory = [...prev];
          const loadingIndex = newHistory.length - 1;
          newHistory[loadingIndex] = { type: 'bot', text: response };
          return newHistory;
        });
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : '未知错误';
        
        // 替换加载消息为错误消息
        setChatHistory(prev => {
          const newHistory = [...prev];
          const loadingIndex = newHistory.length - 1;
          newHistory[loadingIndex] = { type: 'bot', text: `错误: ${errorMessage}` };
          return newHistory;
        });
      } finally {
        setIsProcessing(false);
      }
    }
  };

  /**
   * 获取聊天历史
   * @returns {Array<ChatMessage>} - 聊天消息数组
   */
  const getChatHistory = (): ChatMessage[] => {
    return chatHistory;
  };

  return (
    <Box sx={{
      padding: 2,
      display: 'flex',
      flexDirection: 'column',
      height: '100%',
      bgcolor: '#1e1e1e',
      color: '#eee'
    }}>
      <Box 
        ref={chatListRef}
        sx={{ 
          flexGrow: 1, 
          overflowY: 'auto', 
          mb: 2,
          display: 'flex',
          flexDirection: 'column'
        }}
      >
        <List>
          {getChatHistory().map((chat, index) => (
            <ListItem
              key={index}
              alignItems="flex-start"
              sx={{
                bgcolor: chat.type === 'user' ? 'rgba(25, 118, 210, 0.1)' : 'rgba(255, 255, 255, 0.05)',
                borderRadius: 1,
                mb: 1
              }}
            >
              <ListItemText
                primary={
                  <Typography
                    variant="subtitle2"
                    sx={{
                      color: chat.type === 'user' ? '#90caf9' : '#f48fb1'
                    }}
                  >
                    {chat.type === 'user' ? t('chat.you') : t('chat.bot')}
                  </Typography>
                }
                secondary={
                  <Box sx={{ display: 'flex', alignItems: 'center' }}>
                    {chat.isLoading ? (
                      <CircularProgress size={16} sx={{ mr: 1, color: '#f48fb1' }} />
                    ) : null}
                    <Typography variant="body2" sx={{ color: '#eee', whiteSpace: 'pre-wrap' }}>
                      {chat.text}
                    </Typography>
                  </Box>
                }
              />
            </ListItem>
          ))}
        </List>
      </Box>

      <Box sx={{ display: 'flex', alignItems: 'center' }}>
        <TextField
          label={t('chat.message')}
          variant="outlined"
          fullWidth
          value={message}
          onChange={(e: ChangeEvent<HTMLInputElement>) => setMessage(e.target.value)}
          onKeyPress={(e: KeyboardEvent<HTMLDivElement>) => {
            if (e.key === 'Enter' && !isProcessing) {
              handleSendMessage();
            }
          }}
          disabled={isProcessing}
          sx={{
            '& .MuiOutlinedInput-root': {
              color: '#eee',
              '& fieldset': {
                borderColor: '#555',
              },
              '&:hover fieldset': {
                borderColor: '#777',
              },
              '&.Mui-focused fieldset': {
                borderColor: '#90caf9',
              }
            },
            '& .MuiInputLabel-root': {
              color: '#aaa'
            }
          }}
        />
        <Button 
          variant="contained" 
          color="primary" 
          sx={{ ml: 1 }} 
          onClick={handleSendMessage}
          disabled={isProcessing}
        >
          {isProcessing ? <CircularProgress size={24} color="inherit" /> : t('chat.send')}
        </Button>
      </Box>
    </Box>
  );
};

export default ChatInterface;