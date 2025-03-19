// frontend/src/components/FlowEditor.tsx
import React, { useState, useCallback, useRef, useEffect } from 'react';
import ReactFlow, {
  ReactFlowProvider,
  addEdge,
  useNodesState,
  useEdgesState,
  Controls,
  Background,
  useReactFlow,
  Node,
  Edge,
  Connection,
  NodeMouseHandler,
  ReactFlowInstance,
  NodeTypes,
  XYPosition,
  BackgroundVariant,
} from 'reactflow';
import 'reactflow/dist/style.css';
import {
  Box,
  Button,
  TextField,
  IconButton,
  Tooltip,
  Paper,
  Menu,
  MenuItem,
  Divider,
  Typography
} from '@mui/material';
import { useSnackbar } from 'notistack';
import MenuIcon from '@mui/icons-material/Menu';
import AccountCircleIcon from '@mui/icons-material/AccountCircle';
import AddIcon from '@mui/icons-material/Add';
import ChatIcon from '@mui/icons-material/Chat';
import CodeIcon from '@mui/icons-material/Code';
import CloseIcon from '@mui/icons-material/Close';
import InfoIcon from '@mui/icons-material/Info';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
// 导入自定义节点和组件
import InputNode from './nodes/InputNode';
import OutputNode from './nodes/OutputNode';
import ProcessNode from './nodes/ProcessNode';
import DecisionNode from './nodes/DecisionNode';
import NodeProperties from './NodeProperties';
import GlobalVariables from './GlobalVariables';
import ChatInterface from './ChatInterface';
import NodeSelector from './NodeSelector';
import { createFlow, getFlow, updateFlow, deleteFlow } from '../api/api';
import { useTranslation } from 'react-i18next';
import LanguageSelector from './LanguageSelector';
import VersionInfo from './VersionInfo';
import FlowSelect from './FlowSelect';

// 节点数据接口定义
export interface NodeData {
  label: string;
  description?: string;
  [key: string]: any;
}

// 节点类型接口
export interface AddNodeParams {
  type: string;
  data: NodeData;
}

// 节点更新接口
export interface UpdateNodeData {
  id: string;
  data: NodeData;
}

// 流程编辑器属性接口
interface FlowEditorProps {
  flowId?: string;
}

// 自定义节点类型
const nodeTypes: NodeTypes = {
  input: InputNode,
  output: OutputNode,
  process: ProcessNode,
  decision: DecisionNode,
};

const FlowEditor: React.FC<FlowEditorProps> = ({ flowId }) => {
  const { t } = useTranslation();
  const reactFlowWrapper = useRef<HTMLDivElement>(null);
  const [nodes, setNodes, onNodesChange] = useNodesState<NodeData>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [selectedNode, setSelectedNode] = useState<Node<NodeData> | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState<boolean>(false);
  const [nodeInfoOpen, setNodeInfoOpen] = useState<boolean>(false);
  const [globalVarsOpen, setGlobalVarsOpen] = useState<boolean>(false);
  const [chatOpen, setChatOpen] = useState<boolean>(false);
  const [toggleMenuAnchorEl, setToggleMenuAnchorEl] = useState<null | HTMLElement>(null);
  const [flowName, setFlowName] = useState<string>(t('flowEditor.untitledFlow'));
  const { enqueueSnackbar } = useSnackbar();
  const { fitView } = useReactFlow();
  const [reactFlowInstance, setReactFlowInstance] = useState<ReactFlowInstance | null>(null);
  const { isAuthenticated, logout } = useAuth();
  const navigate = useNavigate();
  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null);
  const [flowSelectOpen, setFlowSelectOpen] = useState<boolean>(false);

  useEffect(() => {
    if (flowId) {
      loadFlow(flowId);
    }
  }, [flowId]);

  // 在FlowEditor组件内添加自动保存功能
  // 使用useEffect监听nodes和edges变化并自动保存
  useEffect(() => {
    // 创建防抖函数确保不会频繁调用API
    type DebouncedFunction = {
      (...args: any[]): void;
      flush?: () => void;
    };
    
    const debounce = (func: Function, delay: number): DebouncedFunction => {
      let timer: NodeJS.Timeout;
      const debouncedFunc = (...args: any) => {
        clearTimeout(timer);
        timer = setTimeout(() => func(...args), delay);
      };
      
      // 添加flush方法
      debouncedFunc.flush = () => {
        clearTimeout(timer);
        func();
      };
      
      return debouncedFunc;
    };

    // 如果还没有加载完成或者没有flowId，则不保存
    if (!flowId || !reactFlowInstance || nodes.length === 0) {
      return;
    }

    // 创建防抖的保存函数
    const debouncedSave = debounce(async () => {
      try {
        const flowData = reactFlowInstance.toObject();
        await updateFlow(flowId, { flow_data: flowData, name: flowName });
        console.log('流程图已自动保存');
        // 使用简单的通知而不是弹出提示，避免打扰用户
        // enqueueSnackbar(t('flowEditor.autoSaveSuccess'), { variant: 'success' });
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : t('common.unknown');
        console.error('自动保存失败:', errorMessage);
        enqueueSnackbar(`${t('flowEditor.autoSaveError')} ${errorMessage}`, { variant: 'error' });
      }
    }, 2000); // 设置2秒延迟，避免频繁保存

    // 只要nodes或edges变化，就触发自动保存
    debouncedSave();

    // 清理函数
    return () => {
      // 组件卸载时如果有待处理的保存，立即执行
      debouncedSave.flush?.();
    };
  }, [nodes, edges, flowId, reactFlowInstance, flowName, enqueueSnackbar, t]);

  // 在现有useEffect之后添加一个新的useEffect来监听自定义事件
  useEffect(() => {
    // 监听流程图改名事件
    const handleFlowRenamed = (event: CustomEvent) => {
      if (event.detail && event.detail.flowId === flowId && event.detail.newName) {
        setFlowName(event.detail.newName);
        console.log('流程图名称已更新:', event.detail.newName);
        // 可选: 显示一个简单提示
        enqueueSnackbar(t('flowEditor.nameUpdated', '流程图名称已更新'), { 
          variant: 'success',
          autoHideDuration: 3000
        });
      }
    };

    // 添加事件监听器
    window.addEventListener('flow-renamed', handleFlowRenamed as EventListener);

    // 清理函数
    return () => {
      window.removeEventListener('flow-renamed', handleFlowRenamed as EventListener);
    };
  }, [flowId, enqueueSnackbar, t]);

  const onConnect = useCallback(
    (params: Connection) => setEdges((eds) => addEdge(params, eds)),
    [setEdges]
  );

  const onNodeClick: NodeMouseHandler = useCallback(
    (event, node) => {
      setSelectedNode(node as Node<NodeData>);
      setNodeInfoOpen(true);
    },
    [setSelectedNode]
  );

  const onNodePropertyChange = (updatedNode: UpdateNodeData) => {
    setNodes((nds) =>
      nds.map((node) => {
        if (node.id === updatedNode.id) {
          return { ...node, data: updatedNode.data };
        }
        return node;
      })
    );
  };

  const loadFlow = async (flowId: string) => {
    try {
      const flowData = await getFlow(flowId);
      if (flowData && flowData.flow_data) {
        setNodes(flowData.flow_data.nodes || []);
        setEdges(flowData.flow_data.edges || []);
        setFlowName(flowData.name || t('flowEditor.untitledFlow'));
        enqueueSnackbar(t('flowEditor.loadSuccess'), { variant: 'success' });
      } else {
        enqueueSnackbar(t('flowEditor.invalidFlowData'), { variant: 'error' });
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : t('common.unknown');
      enqueueSnackbar(`${t('flowEditor.loadError')} ${errorMessage}`, { variant: 'error' });
    }
  };

  const deleteCurrentFlow = async () => {
    if (flowId) {
      try {
        await deleteFlow(flowId);
        enqueueSnackbar(t('flowEditor.deleteSuccess'), { variant: 'success' });
        const userId = localStorage.getItem('user_id');
        navigate('/flow', { replace: true });
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : t('common.unknown');
        enqueueSnackbar(`${t('flowEditor.deleteError')} ${errorMessage}`, { variant: 'error' });
      }
    } else {
      enqueueSnackbar(t('flowEditor.noFlowToDelete'), { variant: 'warning' });
    }
  };

  // 计算节点的默认位置，避免重叠
  const getNextNodePosition = (): XYPosition => {
    // 基于现有节点数量计算新位置
    const offset = nodes.length * 50;
    return {
      x: 100 + (nodes.length % 3) * 250,
      y: 100 + Math.floor(nodes.length / 3) * 150 + offset % 50
    };
  };

  const onAddNode = (nodeData: AddNodeParams) => {
    const id = `${nodeData.type}-${Date.now()}`; // Generate a unique ID
    const newNode: Node<NodeData> = {
      id: id,
      type: nodeData.type,
      data: nodeData.data,
      position: getNextNodePosition(), // 动态计算位置
    };
    setNodes((nds) => [...nds, newNode]);
  };

  // 处理拖拽操作
  const onDragOver = useCallback((event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
    console.log(t('nodeDrag.hover'));
  }, [t]);

  const onDrop = useCallback(
    (event: React.DragEvent<HTMLDivElement>) => {
      event.preventDefault();
      console.log(t('flowEditor.processingDrop'));

      // 检查是否在ReactFlow区域内
      if (!reactFlowWrapper.current || !reactFlowInstance) {
        console.error(t('flowEditor.invalidReactFlowReference'));
        return;
      }

      // 获取ReactFlow边界
      const reactFlowBounds = reactFlowWrapper.current.getBoundingClientRect();

      // 获取拖拽的节点类型数据
      const nodeType = event.dataTransfer.getData('application/reactflow-node');
      console.log(t('flowEditor.droppedNodeType'), nodeType);

      if (!nodeType) {
        console.error(t('flowEditor.nodeTypeNotFound'));
        return;
      }

      // 计算鼠标位置相对于ReactFlow区域的坐标
      const position = reactFlowInstance.project({
        x: event.clientX - reactFlowBounds.left,
        y: event.clientY - reactFlowBounds.top,
      });

      console.log(t('flowEditor.calculatedPosition'), position);

      // 创建一个基于类型的默认标签
      let label = t('nodeTypes.unknown');
      switch (nodeType) {
        case 'input': label = t('nodeTypes.input'); break;
        case 'process': label = t('nodeTypes.process'); break;
        case 'output': label = t('nodeTypes.output'); break;
        case 'decision': label = t('nodeTypes.decision'); break;
      }

      // 创建新节点
      const newNode: Node<NodeData> = {
        id: `${nodeType}-${Date.now()}`,
        type: nodeType,
        position,
        data: { label },
      };

      // 添加节点到流程图
      setNodes((nds) => [...nds, newNode]);
      console.log(t('flowEditor.nodeAddSuccess'), newNode);
    },
    [reactFlowInstance, setNodes, t]
  );

  const onUpdateNode = (nodeId: string, updatedNodeData: { data: NodeData }) => {
    setNodes((nds) =>
      nds.map((node) => {
        if (node.id === nodeId) {
          return { ...node, data: updatedNodeData.data };
        }
        return node;
      })
    );
  };

  const onInit = (_reactFlowInstance: ReactFlowInstance) => {
    setReactFlowInstance(_reactFlowInstance);
  };

  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
  };

  const handleLogout = () => {
    logout();
    handleMenuClose();
  };

  const handleToggleMenuOpen = (event: React.MouseEvent<HTMLButtonElement>) => {
    setToggleMenuAnchorEl(event.currentTarget);
  };

  const handleToggleMenuClose = () => {
    setToggleMenuAnchorEl(null);
  };

  const handleOpenFlowSelect = () => {
    handleMenuClose();
    setFlowSelectOpen(true);
  };

  return (
    <Box sx={{
      height: '100vh',
      width: '100vw',
      display: 'flex',
      flexDirection: 'column',
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      m: 0,
      p: 0,
      boxSizing: 'border-box',
      bgcolor: '#1e1e1e',
      overflow: 'hidden'
    }}>
      {/* 合并后的顶部工具栏 */}
      <Paper elevation={2} sx={{
        p: 0.75,
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        borderRadius: 0,
        minHeight: '48px',
        bgcolor: '#1e1e1e',
        borderBottom: '1px solid #333',
        color: 'white',
        flexShrink: 0,
        zIndex: 10
      }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexGrow: 0 }}>
          {/* 侧边栏切换按钮和流程名称区域 */}
          <Tooltip title={t('flowEditor.toggleMenu')}>
            <IconButton
              color="inherit"
              onClick={handleToggleMenuOpen}
              size="small"
            >
              <MenuIcon />
            </IconButton>
          </Tooltip>
          <Menu
            anchorEl={toggleMenuAnchorEl}
            open={Boolean(toggleMenuAnchorEl)}
            onClose={handleToggleMenuClose}
            anchorOrigin={{
              vertical: 'bottom',
              horizontal: 'left',
            }}
            transformOrigin={{
              vertical: 'top',
              horizontal: 'left',
            }}
            PaperProps={{
              sx: {
                bgcolor: '#333',
                color: 'white',
                '& .MuiMenuItem-root:hover': {
                  bgcolor: 'rgba(255, 255, 255, 0.1)',
                },
                '& .MuiDivider-root': {
                  borderColor: 'rgba(255, 255, 255, 0.12)',
                },
              },
            }}
          >
            <MenuItem
              onClick={() => {
                setGlobalVarsOpen(!globalVarsOpen);
                handleToggleMenuClose();
              }}
            >
              {globalVarsOpen ? t('flowEditor.closeGlobalVars') : t('flowEditor.openGlobalVars')}
            </MenuItem>
            <MenuItem
              onClick={() => {
                setChatOpen(!chatOpen);
                handleToggleMenuClose();
              }}
            >
              {chatOpen ? t('flowEditor.closeChat') : t('flowEditor.openChat')}
            </MenuItem>
          </Menu>

          <Tooltip title={t('flowEditor.addNode')}>
            <IconButton
              color="inherit"
              onClick={() => setSidebarOpen(!sidebarOpen)}
              size="small"
            >
              <AddIcon />
            </IconButton>
          </Tooltip>

          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <TextField
              label={t('flowEditor.flowName')}
              variant="outlined"
              size="small"
              value={flowName}
              InputProps={{
                readOnly: true,
              }}
              sx={{
                width: '250px',
                '& .MuiOutlinedInput-root': {
                  color: 'white',
                  height: '36px',
                  '& fieldset': {
                    borderColor: 'rgba(255, 255, 255, 0.23)',
                  },
                  '&:hover fieldset': {
                    borderColor: 'rgba(255, 255, 255, 0.23)',
                  },
                },
                '& .MuiInputLabel-root': {
                  color: 'rgba(255, 255, 255, 0.7)',
                  transform: 'translate(14px, 9px) scale(0.75)',
                  '&.MuiInputLabel-shrink': {
                    transform: 'translate(14px, -6px) scale(0.75)',
                  }
                },
              }}
            />
          </Box>
        </Box>

        <Box sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexGrow: 1
        }}>
        </Box>

        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexGrow: 0 }}>
          {flowId && (
            <Button
              variant="outlined"
              color="error"
              size="small"
              onClick={deleteCurrentFlow}
            >
              {t('flowEditor.delete')}
            </Button>
          )}

          <LanguageSelector />

          {isAuthenticated && (
            <>
              <IconButton
                color="inherit"
                onClick={handleMenuOpen}
                size="small"
              >
                <AccountCircleIcon />
              </IconButton>
              <Menu
                anchorEl={anchorEl}
                open={Boolean(anchorEl)}
                onClose={handleMenuClose}
                anchorOrigin={{
                  vertical: 'bottom',
                  horizontal: 'right',
                }}
                transformOrigin={{
                  vertical: 'top',
                  horizontal: 'right',
                }}
                PaperProps={{
                  sx: {
                    bgcolor: '#333',
                    color: 'white',
                    '& .MuiMenuItem-root:hover': {
                      bgcolor: 'rgba(255, 255, 255, 0.1)',
                    },
                    '& .MuiDivider-root': {
                      borderColor: 'rgba(255, 255, 255, 0.12)',
                    },
                  },
                }}
              >
                <MenuItem onClick={handleOpenFlowSelect}>
                  {t('nav.flowSelect', '选择流程图')}
                </MenuItem>
                <Divider />
                <MenuItem onClick={handleLogout}>{t('nav.logout')}</MenuItem>
              </Menu>
            </>
          )}
        </Box>
      </Paper>

      {/* 主要内容区域 */}
      <Box sx={{
        flexGrow: 1,
        display: 'flex',
        overflow: 'hidden',
        height: 'calc(100vh - 48px)',  // 减去顶部工具栏的高度
        width: '100%',
        position: 'relative'
      }}>
        {/* 节点选择器面板 - 可关闭 */}
        {sidebarOpen && (
          <Box
            sx={{
              position: 'absolute',
              top: '12px',
              left: '12px',
              width: '220px',
              height: 'auto',
              maxHeight: '60%',
              bgcolor: '#2d2d2d',
              borderRadius: '4px',
              boxShadow: '0 4px 20px rgba(0,0,0,0.5)',
              zIndex: 5,
              display: 'flex',
              flexDirection: 'column',
              border: '1px solid #444',
              overflow: 'hidden'
            }}
          >
            <Box sx={{
              p: 1,
              bgcolor: '#333',
              display: 'flex',
              justifyContent: 'center',
              alignItems: 'center',
              borderBottom: '1px solid #444'
            }}>
              <Typography variant="subtitle2">
                {t('sidebar.title')}
              </Typography>
            </Box>
            <Box sx={{ p: 1.5, overflowY: 'auto', flexGrow: 1 }}>
              <Typography
                variant="body2"
                sx={{
                  mb: 1.5,
                  color: '#aaa',
                  fontStyle: 'italic',
                  fontSize: '0.8rem'
                }}
              >
                {t('sidebar.dragHint')}
              </Typography>
              <NodeSelector />
            </Box>
          </Box>
        )}
        <Box
          ref={reactFlowWrapper}
          sx={{
            flexGrow: 1,
            position: 'relative',
            height: '100%',
            width: '100%',
            '& .react-flow': {
              background: '#1e1e1e',
              width: '100%',
              height: '100%'
            },
            '& .react-flow__container': {
              width: '100%',
              height: '100%'
            },
            '& .react-flow__controls': {
              position: 'fixed',
              left: '20px',
              bottom: '20px',
              zIndex: 5,
            },
            '& .react-flow__attribution': {
              display: 'none'  // 隐藏原有的ReactFlow标识
            },
            '& .version-info': {
              position: 'fixed',
              right: '10px',
              bottom: '10px',
              zIndex: 4,
              backgroundColor: 'transparent',
            }
          }}
        >
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeClick={onNodeClick}
            onInit={onInit}
            onDragOver={onDragOver}
            onDrop={onDrop}
            nodeTypes={nodeTypes}
            deleteKeyCode="Delete"
            multiSelectionKeyCode="Control"
            selectionOnDrag={false}
            zoomOnScroll={true}
            snapToGrid={true}
            snapGrid={[15, 15]}
            fitView
            style={{
              width: '100%',
              height: '100%',
              background: '#1e1e1e'
            }}
            className="fullscreen-flow"
          >
            <Controls
              showInteractive={true}
              style={{
                backgroundColor: '#2d2d2d',
                color: '#fff',
                border: '1px solid #444',
                borderRadius: '4px',
                padding: '4px',
              }}
            />
            <Background color="#444" gap={12} size={1} variant={BackgroundVariant.Dots} />
            <div className="version-info">
              <VersionInfo />
            </div>
          </ReactFlow>
        </Box>

        {/* 节点信息面板 - 可关闭 */}
        {nodeInfoOpen && selectedNode && (
          <Box
            sx={{
              position: 'absolute',
              top: '12px',
              right: '12px',
              width: '350px',
              maxHeight: 'calc(100% - 24px)',
              bgcolor: '#2d2d2d',
              borderRadius: '4px',
              boxShadow: '0 4px 20px rgba(0,0,0,0.5)',
              zIndex: 5,
              display: 'flex',
              flexDirection: 'column',
              border: '1px solid #444',
              overflow: 'hidden'
            }}
          >
            <Box sx={{
              p: 1,
              bgcolor: '#333',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              borderBottom: '1px solid #444'
            }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <InfoIcon fontSize="small" />
                <Typography variant="subtitle2">
                  {t('flowEditor.nodeProperties')}
                </Typography>
              </Box>
              <IconButton
                size="small"
                color="inherit"
                onClick={() => setNodeInfoOpen(false)}
              >
                <CloseIcon fontSize="small" />
              </IconButton>
            </Box>
            <Box sx={{ p: 2, overflowY: 'auto', flexGrow: 1 }}>
              <NodeProperties node={selectedNode} onNodePropertyChange={onNodePropertyChange} />
            </Box>
          </Box>
        )}

        {/* 全局变量面板 - 可关闭 */}
        {globalVarsOpen && (
          <Box
            sx={{
              position: 'absolute',
              top: nodeInfoOpen && selectedNode ? '50%' : '12px',
              right: '12px',
              width: '350px',
              maxHeight: nodeInfoOpen && selectedNode ? 'calc(50% - 36px)' : 'calc(100% - 24px)',
              bgcolor: '#2d2d2d',
              borderRadius: '4px',
              boxShadow: '0 4px 20px rgba(0,0,0,0.5)',
              zIndex: 5,
              display: 'flex',
              flexDirection: 'column',
              border: '1px solid #444',
              overflow: 'hidden'
            }}
          >
            <Box sx={{
              p: 1,
              bgcolor: '#333',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              borderBottom: '1px solid #444'
            }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <CodeIcon fontSize="small" />
                <Typography variant="subtitle2">
                  {t('flowEditor.globalVariables')}
                </Typography>
              </Box>
              <IconButton
                size="small"
                color="inherit"
                onClick={() => setGlobalVarsOpen(false)}
              >
                <CloseIcon fontSize="small" />
              </IconButton>
            </Box>
            <Box sx={{ p: 2, overflowY: 'auto', flexGrow: 1 }}>
              <GlobalVariables />
            </Box>
          </Box>
        )}

        {/* 聊天界面 - 可关闭 */}
        {chatOpen && (
          <Box
            sx={{
              position: 'absolute',
              bottom: '12px',
              right: '12px',
              width: '350px',
              height: '300px',
              maxHeight: 'calc(100% - 24px)',
              bgcolor: '#2d2d2d',
              borderRadius: '4px',
              boxShadow: '0 4px 20px rgba(0,0,0,0.5)',
              zIndex: 5,
              display: 'flex',
              flexDirection: 'column',
              border: '1px solid #444',
              overflow: 'hidden'
            }}
          >
            <Box sx={{
              p: 1,
              bgcolor: '#333',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              borderBottom: '1px solid #444'
            }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <ChatIcon fontSize="small" />
                <Typography variant="subtitle2">
                  {t('flowEditor.chatAssistant')}
                </Typography>
              </Box>
              <IconButton
                size="small"
                color="inherit"
                onClick={() => setChatOpen(false)}
              >
                <CloseIcon fontSize="small" />
              </IconButton>
            </Box>
            <Box sx={{ overflowY: 'hidden', flexGrow: 1, display: 'flex', flexDirection: 'column' }}>
              <ChatInterface onAddNode={onAddNode} onUpdateNode={onUpdateNode} />
            </Box>
          </Box>
        )}

        {/* 流程图选择对话框 */}
        <FlowSelect
          open={flowSelectOpen}
          onClose={() => setFlowSelectOpen(false)}
        />
      </Box>
    </Box>
  );
};

// FlowEditorWrapper组件属性接口
interface FlowEditorWrapperProps {
  flowId?: string;
}

const FlowEditorWrapper: React.FC<FlowEditorWrapperProps> = ({ flowId }) => (
  <ReactFlowProvider>
    <FlowEditor flowId={flowId} />
  </ReactFlowProvider>
);

export default FlowEditorWrapper;