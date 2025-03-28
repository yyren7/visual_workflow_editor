// visual_workflow_editor/frontend/src/components/ChatInterface.tsx
import React, { useState, useCallback, KeyboardEvent, ChangeEvent, useRef, useEffect } from 'react';
import { Box, TextField, Button, List, ListItem, ListItemText, Typography, CircularProgress, IconButton, Menu, MenuItem, Switch, FormControlLabel } from '@mui/material';
import { generateNode, updateNodeByLLM, processWorkflow, WorkflowProcessResponse, sendChatMessage, getChatConversations, deleteChatConversation, ChatResponse } from '../api/api';
import { useSnackbar } from 'notistack';
import { NodeData } from './FlowEditor';
import { useTranslation } from 'react-i18next';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';

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
  currentFlowId?: string; // 添加当前流程图ID属性
}

/**
 * ChatInterface Component
 *
 * This component provides a chat interface for interacting with the LLM to generate and update nodes.
 */
const ChatInterface: React.FC<ChatInterfaceProps> = ({ onAddNode, onUpdateNode, onConnectNodes, currentFlowId }) => {
  const { t } = useTranslation();
  const [message, setMessage] = useState<string>('');
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const { enqueueSnackbar } = useSnackbar();
  const chatListRef = useRef<HTMLUListElement>(null);
  
  // 会话管理
  const [sessionId, setSessionId] = useState<string | undefined>(undefined);
  const [useLangChain, setUseLangChain] = useState<boolean>(true);
  const [conversations, setConversations] = useState<Array<{conversation_id: string, updated_at: string}>>([]);
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const menuOpen = Boolean(anchorEl);
  
  // 加载会话列表
  useEffect(() => {
    if (useLangChain) {
      loadConversations();
    }
  }, [useLangChain]);

  // 加载会话列表的函数
  const loadConversations = async () => {
    try {
      const conversationsList = await getChatConversations();
      setConversations(conversationsList);
      
      // 如果有会话且当前未选择会话，选择最新的
      if (conversationsList.length > 0 && !sessionId) {
        // 按更新时间排序，选择最新的
        const sorted = [...conversationsList].sort((a, b) => 
          new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
        );
        setSessionId(sorted[0].conversation_id);
      }
    } catch (error) {
      console.error("加载会话列表失败:", error);
      enqueueSnackbar(t('chat.loadConversationsFailed'), { variant: 'error' });
    }
  };
  
  // 打开菜单
  const handleMenuClick = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };
  
  // 关闭菜单
  const handleMenuClose = () => {
    setAnchorEl(null);
  };
  
  // 创建新会话
  const handleNewConversation = () => {
    setSessionId(undefined);
    setChatHistory([]);
    handleMenuClose();
  };
  
  // 切换会话
  const handleSwitchConversation = (conversation_id: string) => {
    setSessionId(conversation_id);
    setChatHistory([]);
    handleMenuClose();
  };
  
  // 删除会话
  const handleDeleteConversation = async (conversation_id: string) => {
    try {
      await deleteChatConversation(conversation_id);
      await loadConversations();
      if (sessionId === conversation_id) {
        setSessionId(undefined);
        setChatHistory([]);
      }
      enqueueSnackbar(t('chat.conversationDeleted'), { variant: 'success' });
    } catch (error) {
      console.error("删除会话失败:", error);
      enqueueSnackbar(t('chat.deleteConversationFailed'), { variant: 'error' });
    }
    handleMenuClose();
  };

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

      // 构建结果描述信息
      let responseText = '';
      
      // 1. 如果有扩展提示，先显示
      if (result.expanded_prompt) {
        responseText += `我的理解:\n${result.expanded_prompt}\n\n`;
      }
      
      // 2. 显示LLM交互记录
      if (result.llm_interactions && result.llm_interactions.length > 0) {
        responseText += "处理过程:\n";
        
        result.llm_interactions.forEach((interaction, index) => {
          const stage = interaction.stage.replace(/_/g, ' ');
          responseText += `- ${stage}\n`;
          
          // 如果是工具调用，显示更详细信息
          if (interaction.tool_type) {
            responseText += `  工具: ${interaction.tool_type}\n`;
            
            // 显示工具执行结果
            if (interaction.output && interaction.output.success) {
              if (interaction.tool_type === 'node_creation' && interaction.output.data) {
                const data = interaction.output.data;
                responseText += `  创建节点: ${data.node_label} (${data.node_type})\n`;
              } else if (interaction.tool_type === 'node_connection' && interaction.output.data) {
                const data = interaction.output.data;
                responseText += `  连接节点: ${data.source_id} → ${data.target_id}\n`;
              } else if (interaction.tool_type === 'property_setting' && interaction.output.data) {
                responseText += `  设置属性成功\n`;
              }
            } else if (interaction.output) {
              responseText += `  结果: ${interaction.output.message || '执行失败'}\n`;
            }
          }
        });
        
        responseText += "\n";
      }
      
      // 3. 检查是否需要询问更多问题
      if (result.missing_info) {
        console.log("收到missing_info返回:", result.missing_info);
        
        // 优先使用已格式化的文本
        let missingInfoText = "";
        if (result.missing_info.data && result.missing_info.data.formatted_text) {
          missingInfoText = result.missing_info.data.formatted_text;
        } 
        // 如果有questions数组，构建问题列表
        else if (result.missing_info.data && Array.isArray(result.missing_info.data.questions) && result.missing_info.data.questions.length > 0) {
          const context = result.missing_info.data.context || "我需要以下额外信息来完成流程图设计：";
          const questions = result.missing_info.data.questions.map((q: string, i: number) => `${i+1}. ${q}`).join('\n');
          missingInfoText = `${context}\n\n${questions}`;
        }
        // 如果有成功状态和消息
        else if (result.missing_info.success && result.missing_info.message) {
          missingInfoText = result.missing_info.message;
        }
        // 如果直接是问题数组
        else if (Array.isArray(result.missing_info) && result.missing_info.length > 0) {
          missingInfoText = result.missing_info.join('\n');
        }
        // 如果是任何其他格式的missing_info，尝试转换为字符串
        else if (result.missing_info) {
          try {
            if (typeof result.missing_info === 'string') {
              missingInfoText = result.missing_info;
            } else {
              missingInfoText = JSON.stringify(result.missing_info);
            }
          } catch (e) {
            console.error("无法解析missing_info:", e);
            missingInfoText = "我需要更多信息来完成您的请求。";
          }
        }
        
        // 添加到响应文本
        if (missingInfoText) {
          responseText += missingInfoText;
          return responseText;
        }
      }
      
      // 查找步骤中是否有ask_more_info工具调用
      const askMoreInfoStep = result.step_results.find(
        step => step.tool_action && step.tool_action.tool_type === 'ask_more_info' && step.tool_action.result.success
      );
      
      if (askMoreInfoStep && askMoreInfoStep.tool_action && askMoreInfoStep.tool_action.result.data) {
        const toolData = askMoreInfoStep.tool_action.result.data;
        
        // 处理工具返回的questions
        if (toolData.questions && Array.isArray(toolData.questions) && toolData.questions.length > 0) {
          const context = toolData.context || "我需要以下额外信息来完成流程图设计：";
          const questions = toolData.questions.map((q: string, i: number) => `${i+1}. ${q}`).join('\n');
          responseText += `${context}\n\n${questions}`;
          return responseText;
        }
      }
      
      // 如果有摘要直接使用
      if (result.summary) {
        responseText += result.summary;
        return responseText;
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
      
      responseText += summary;
      return responseText;
    } catch (error) {
      console.error("应用工作流结果失败:", error);
      return "处理结果时出错";
    }
  };

  /**
   * 使用LangChain Chat API发送消息
   * @param {string} userMessage - 用户消息
   * @returns {Promise<string>} - LLM的响应
   */
  const sendMessageToLangChain = async (userMessage: string): Promise<string> => {
    try {
      // 创建metadata，包含当前流程图ID
      const metadata: Record<string, any> = {
        source: 'chat_interface'
      };
      
      // 如果有当前流程图ID，加入到metadata中
      if (currentFlowId) {
        metadata.flow_id = currentFlowId;
        console.log(`将当前流程图ID添加到请求: ${currentFlowId}`);
      } else {
        console.warn('未提供当前流程图ID，将使用默认流程图');
      }
      
      const response = await sendChatMessage({
        message: userMessage,
        conversation_id: sessionId,
        metadata: metadata
      });
      
      // 保存新的会话ID
      if (response.conversation_id) {
        setSessionId(response.conversation_id);
        // 重新加载会话列表以获取最新状态
        loadConversations();
      }
      
      // 检查响应中是否包含刷新流程图标记
      if (response.metadata && response.metadata.refresh_flow) {
        console.log('检测到刷新流程图标记，触发流程图刷新', response.metadata);
        
        // 触发流程图刷新
        const event = new CustomEvent('flow-refresh', { 
          detail: { 
            sourceAction: 'chatbot',
            metadata: response.metadata 
          } 
        });
        window.dispatchEvent(event);
        
        // 添加提示通知
        enqueueSnackbar('流程图已更新', { variant: 'info' });
      }
      
      return response.message;
    } catch (error) {
      console.error("发送消息到LangChain失败:", error);
      throw error;
    }
  };

  /**
   * 发送消息到LLM并更新聊天历史
   * @param {string} userMessage - 要发送的消息
   * @returns {Promise<string>} - LLM的响应
   */
  const sendMessage = useCallback(async (userMessage: string): Promise<string> => {
    try {
      // 处理特殊情况："movel"节点
      if (userMessage.toLowerCase().includes("参数") && 
          chatHistory.length > 0 &&
          chatHistory.some(msg => msg.text.toLowerCase().includes("model") ||
                              msg.text.toLowerCase().includes("机器人") ||
                              msg.text.toLowerCase().includes("节点参数"))) {
        
        // 查找先前涉及model的消息位置
        const modelMsgIndex = chatHistory.findIndex(msg =>
          msg.text.toLowerCase().includes("model") ||
          msg.text.toLowerCase().includes("机器人") ||
          msg.text.toLowerCase().includes("节点参数")
        );
        
        if (modelMsgIndex !== -1 && modelMsgIndex < chatHistory.length - 1) {
          return "请提供更多关于参数的详细信息，比如参数名称和类型等。";
        }
      }
      
      // 选择使用哪个API
      if (useLangChain) {
        // 使用LangChain Chat API
        return await sendMessageToLangChain(userMessage);
      } else {
        // 使用原有的工作流处理API
        const result = await processUserWorkflow(userMessage);
        return applyWorkflowResult(result);
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : "未知错误";
      enqueueSnackbar(`${t('chat.error')} ${errorMessage}`, { variant: 'error' });
      return `${t('chat.error')} ${errorMessage}`;
    }
  }, [enqueueSnackbar, onAddNode, onUpdateNode, onConnectNodes, t, chatHistory, useLangChain, sessionId]);

  /**
   * 处理发送消息事件
   */
  const handleSendMessage = async (): Promise<void> => {
    const userMessage = message.trim();
    if (!userMessage) return;

    const userMsg: ChatMessage = { type: 'user', text: message };
    const loadingMessage: ChatMessage = { type: 'bot', text: '正在处理...', isLoading: true };
    
    setMessage('');
    setChatHistory(prev => [...prev, userMsg, loadingMessage]);
    
    setIsProcessing(true);
    try {
      const response = await sendMessage(userMsg.text);
      
      // 更新聊天历史中的加载消息
      setChatHistory(prev => {
        const newHistory = [...prev];
        const loadingIndex = newHistory.findIndex(msg => msg.isLoading);
        if (loadingIndex !== -1) {
          newHistory[loadingIndex] = { type: 'bot', text: response };
        }
        return newHistory;
      });
    } catch (error) {
      // 更新聊天历史中的加载消息为错误消息
      setChatHistory(prev => {
        const newHistory = [...prev];
        const loadingIndex = newHistory.findIndex(msg => msg.isLoading);
        if (loadingIndex !== -1) {
          const errorMessage = error instanceof Error ? error.message : "处理请求时出错";
          newHistory[loadingIndex] = { type: 'bot', text: `错误: ${errorMessage}` };
        }
        return newHistory;
      });
    } finally {
      setIsProcessing(false);
    }
  };

  /**
   * 处理按键事件，如果是回车则发送消息
   */
  const handleKeyPress = (event: KeyboardEvent<HTMLDivElement>): void => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      handleSendMessage();
    }
  };

  /**
   * 处理消息输入变化
   */
  const handleMessageChange = (event: ChangeEvent<HTMLInputElement>): void => {
    setMessage(event.target.value);
  };

  /**
   * 获取格式化的聊天历史
   */
  const getChatHistory = (): ChatMessage[] => {
    return chatHistory;
  };

  return (
    <Box 
      sx={{ 
        display: 'flex', 
        flexDirection: 'column', 
        height: '100%',
        width: '100%',
        maxWidth: '500px',
        bgcolor: 'background.paper',
        borderRadius: 1,
        boxShadow: 3,
        overflow: 'hidden'
      }}
    >
      <Box 
        sx={{ 
          p: 2, 
          borderBottom: 1, 
          borderColor: 'divider',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}
      >
        <Typography variant="h6">{t('chat.title')}</Typography>
        <Box sx={{ display: 'flex', alignItems: 'center' }}>
          <FormControlLabel
            control={
              <Switch
                checked={useLangChain}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setUseLangChain(e.target.checked)}
                size="small"
              />
            }
            label={<Typography variant="caption">LangChain</Typography>}
            sx={{ mr: 1 }}
          />
          <IconButton
            aria-label="更多选项"
            size="small"
            onClick={handleMenuClick}
          >
            <MoreVertIcon fontSize="small" />
          </IconButton>
          <Menu
            anchorEl={anchorEl}
            open={menuOpen}
            onClose={handleMenuClose}
            MenuListProps={{
              'aria-labelledby': 'basic-button',
            }}
          >
            <MenuItem onClick={handleNewConversation}>
              <AddIcon fontSize="small" sx={{ mr: 1 }} />
              {t('chat.newConversation')}
            </MenuItem>
            {useLangChain && conversations.map((conv) => (
              <MenuItem 
                key={conv.conversation_id}
                onClick={() => handleSwitchConversation(conv.conversation_id)}
                sx={{ 
                  display: 'flex', 
                  justifyContent: 'space-between',
                  bgcolor: sessionId === conv.conversation_id ? 'action.selected' : 'inherit'
                }}
              >
                <Typography variant="body2" noWrap sx={{ maxWidth: '160px' }}>
                  {new Date(conv.updated_at).toLocaleString()}
                </Typography>
                <IconButton 
                  size="small"
                  onClick={(e: React.MouseEvent<HTMLButtonElement>) => {
                    e.stopPropagation();
                    handleDeleteConversation(conv.conversation_id);
                  }}
                >
                  <DeleteIcon fontSize="small" />
                </IconButton>
              </MenuItem>
            ))}
          </Menu>
        </Box>
      </Box>
      
      <List 
        ref={chatListRef as React.RefObject<HTMLUListElement>}
        sx={{ 
          flex: 1, 
          overflow: 'auto',
          p: 2
        }}
      >
        {getChatHistory().map((msg, index) => (
          <ListItem
            key={index}
            alignItems="flex-start"
            sx={{
              flexDirection: msg.type === 'user' ? 'row-reverse' : 'row',
              px: 1,
              py: 0.5
            }}
          >
            <ListItemText
              primary={
                <Typography 
                  variant="body1"
                  align={msg.type === 'user' ? 'right' : 'left'}
                  sx={{
                    display: 'inline-block',
                    maxWidth: '80%',
                    p: 1.5,
                    borderRadius: 2,
                    bgcolor: msg.type === 'user' ? 'primary.light' : '#f5f5f5',
                    color: msg.type === 'user' ? 'primary.contrastText' : '#333333',
                    wordBreak: 'break-word',
                    whiteSpace: 'pre-wrap'
                  }}
                >
                  {msg.isLoading ? (
                    <Box sx={{ display: 'flex', alignItems: 'center' }}>
                      <CircularProgress size={16} sx={{ mr: 1 }} />
                      {msg.text}
                    </Box>
                  ) : (
                    msg.text
                  )}
                </Typography>
              }
            />
          </ListItem>
        ))}
      </List>
      
      <Box sx={{ p: 2, borderTop: 1, borderColor: 'divider' }}>
        <TextField
          fullWidth
          multiline
          maxRows={4}
          placeholder={t('chat.placeholder')}
          variant="outlined"
          value={message}
          onChange={handleMessageChange}
          onKeyPress={handleKeyPress}
          disabled={isProcessing}
          InputProps={{
            endAdornment: (
              <Button 
                variant="contained" 
                color="primary" 
                disabled={isProcessing || !message.trim()} 
                onClick={handleSendMessage}
                sx={{ ml: 1 }}
              >
                {t('chat.send')}
              </Button>
            )
          }}
        />
      </Box>
    </Box>
  );
};

export default ChatInterface;