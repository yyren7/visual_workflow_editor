import { useEffect, useCallback, useRef } from 'react';
import { Node, Edge } from 'reactflow';
import { useSelector, useDispatch } from 'react-redux';
import _isEqual from 'lodash/isEqual';
import { AppDispatch } from '../store/store';
import {
  selectCurrentFlowId,
  selectNodes,
  selectEdges,
  setNodes,
  setEdges,
} from '../store/slices/flowSlice';

interface AgentState {
  current_user_request?: string;
  sas_step1_generated_tasks?: Array<{
    name: string;
    type: string;
    description?: string;
    sub_tasks?: string[];
    details?: string[]; // 添加details字段，包含模块步骤
  }>;
  dialog_state?: string;
  task_list_accepted?: boolean;
  module_steps_accepted?: boolean;
  input_processed?: boolean;
  task_route_decision?: any;
  revision_iteration?: number;
  completion_status?: string;
}

export const useLangGraphNodes = (agentState?: AgentState) => {
  const dispatch = useDispatch<AppDispatch>();
  const currentFlowId = useSelector(selectCurrentFlowId);
  const nodesFromStore = useSelector(selectNodes);
  const edgesFromStore = useSelector(selectEdges);
  
  // 用于跟踪InputNode之前的尺寸
  const previousInputNodeDimensions = useRef<{
    width?: number;
    height?: number;
    x?: number;
    y?: number;
  }>({});

  // 防抖标记，避免频繁更新
  const updateTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const lastUpdateTimeRef = useRef<number>(0);

  const generateLangGraphNodes = useCallback((state: AgentState, flowId: string): { nodes: Node[], edges: Edge[] } => {
    console.log('🔧 [DEBUG] generateLangGraphNodes: Starting generation');
    console.log('🔧 [DEBUG] State received:', state);
    console.log('🔧 [DEBUG] FlowId:', flowId);
    
    const newNodes: Node[] = [];
    const newEdges: Edge[] = [];

    const INPUT_NODE_WIDTH = 600;
    const INPUT_NODE_DEFAULT_HEIGHT = 400;
    const TASK_NODE_WIDTH = 400;
    const TASK_NODE_HEIGHT = 300;
    const DETAIL_NODE_WIDTH = TASK_NODE_WIDTH;
    const DETAIL_NODE_HEIGHT = 250; 
    
    const VERTICAL_SPACING = 120;
    const HORIZONTAL_SPACING = 50;
    
    const existingInputNode = nodesFromStore?.find(n => n.id === `langgraph_input_${flowId}`);
    const actualInputHeight = existingInputNode?.height || INPUT_NODE_DEFAULT_HEIGHT;
    const actualInputWidth = existingInputNode?.width || INPUT_NODE_WIDTH;
    
    const inputNode: Node = {
      id: `langgraph_input_${flowId}`,
      type: 'langgraph_input',
      position: existingInputNode?.position || { x: 100, y: 50 },
      data: {
        label: '机器人任务描述',
        flowId: flowId,
        currentUserRequest: state.current_user_request || '',
      },
      width: actualInputWidth,
      height: actualInputHeight,
    };
    newNodes.push(inputNode);
    console.log('🔧 [DEBUG] Added input node');

    const tasks = state.sas_step1_generated_tasks || [];
    console.log('🔧 [DEBUG] Tasks from state:', tasks);
    console.log('🔧 [DEBUG] Tasks count:', tasks.length);
    
    if (tasks.length === 0) {
      console.log('🔧 [DEBUG] No tasks found - returning only input node');
      return { nodes: newNodes, edges: newEdges };
    }

    if (tasks.length > 0) {
      const taskYOffset = inputNode.position.y + actualInputHeight + VERTICAL_SPACING;
      
      tasks.forEach((task, i) => {
        const taskSlotWidth = TASK_NODE_WIDTH + HORIZONTAL_SPACING;
        const totalTasksWidth = tasks.length * taskSlotWidth - HORIZONTAL_SPACING;
        const inputCenterX = inputNode.position.x + actualInputWidth / 2;
        const tasksStartX = inputCenterX - totalTasksWidth / 2;
        const taskX = tasksStartX + (i * taskSlotWidth);
        
        const taskNode: Node = {
          id: `langgraph_task_${flowId}_${i}`,
          type: 'langgraph_task',
          position: { x: taskX, y: taskYOffset },
          data: { label: `Task ${i + 1}`, flowId, taskIndex: i, task },
          width: TASK_NODE_WIDTH,
          height: TASK_NODE_HEIGHT,
        };
        newNodes.push(taskNode);

        newEdges.push({
          id: `edge_input_to_task_${i}`,
          source: `langgraph_input_${flowId}`,
          target: taskNode.id,
          type: 'smoothstep',
        });

        const details = task.details || [];
        if (details.length > 0) {
          const detailY = taskYOffset + TASK_NODE_HEIGHT + VERTICAL_SPACING;
          const detailNode: Node = {
            id: `langgraph_detail_${flowId}_${i}`,
            type: 'langgraph_detail',
            position: { x: taskX, y: detailY },
            data: { label: `${task.name} - Steps`, flowId, taskIndex: i, taskName: task.name, details },
            width: DETAIL_NODE_WIDTH,
            height: DETAIL_NODE_HEIGHT,
          };
          newNodes.push(detailNode);

          newEdges.push({
            id: `edge_task_${i}_to_detail`,
            source: taskNode.id,
            target: detailNode.id,
            type: 'smoothstep',
          });
        }
      });
    }

    return { nodes: newNodes, edges: newEdges };
  }, [nodesFromStore]);

  // 专门用于重新计算位置的函数，不改变节点数据
  const recalculatePositions = useCallback((
    flowId: string,
    inputNodeHeight: number,
    inputNodeWidth: number,
    inputNodePosition: { x: number; y: number }
  ): Node[] => {
    if (!nodesFromStore) return [];

    const VERTICAL_SPACING = 120;
    const HORIZONTAL_SPACING = 50;
    const TASK_NODE_WIDTH = 400;
    const TASK_NODE_HEIGHT = 300;
    const DETAIL_NODE_HEIGHT = 250;

    const updatedNodes = nodesFromStore.map(node => {
      if (!node.id.startsWith('langgraph_')) return node;
      
      if (node.id === `langgraph_input_${flowId}`) {
        // InputNode保持原始位置，不修改
        return node;
      }
      
      if (node.id.startsWith(`langgraph_task_${flowId}_`)) {
        // 重新计算task节点位置
        const taskIndex = parseInt(node.id.split('_').pop() || '0');
        const taskYOffset = inputNodePosition.y + inputNodeHeight + VERTICAL_SPACING;
        
        // 获取所有task节点来计算水平布局
        const allTaskNodes = nodesFromStore.filter(n => n.id.startsWith(`langgraph_task_${flowId}_`));
        const taskCount = allTaskNodes.length;
        
        const taskSlotWidth = TASK_NODE_WIDTH + HORIZONTAL_SPACING;
        const totalTasksWidth = taskCount * taskSlotWidth - HORIZONTAL_SPACING;
        const inputCenterX = inputNodePosition.x + inputNodeWidth / 2;
        const tasksStartX = inputCenterX - totalTasksWidth / 2;
        const taskX = tasksStartX + (taskIndex * taskSlotWidth);

        return {
          ...node,
          position: { x: taskX, y: taskYOffset }
        };
      }
      
      if (node.id.startsWith(`langgraph_detail_${flowId}_`)) {
        // 重新计算detail节点位置
        const taskIndex = parseInt(node.id.split('_').pop() || '0');
        const taskYOffset = inputNodePosition.y + inputNodeHeight + VERTICAL_SPACING;
        const detailY = taskYOffset + TASK_NODE_HEIGHT + VERTICAL_SPACING;
        
        // 获取对应的task节点位置
        const allTaskNodes = nodesFromStore.filter(n => n.id.startsWith(`langgraph_task_${flowId}_`));
        const taskCount = allTaskNodes.length;
        
        const taskSlotWidth = TASK_NODE_WIDTH + HORIZONTAL_SPACING;
        const totalTasksWidth = taskCount * taskSlotWidth - HORIZONTAL_SPACING;
        const inputCenterX = inputNodePosition.x + inputNodeWidth / 2;
        const tasksStartX = inputCenterX - totalTasksWidth / 2;
        const taskX = tasksStartX + (taskIndex * taskSlotWidth);

        return {
          ...node,
          position: { x: taskX, y: detailY }
        };
      }
      
      return node;
    });

    return updatedNodes;
  }, [nodesFromStore]);

  const syncLangGraphNodes = useCallback(() => {
    if (!agentState || !currentFlowId) {
        console.log('🔧 [DEBUG] syncLangGraphNodes: Missing agentState or currentFlowId');
        console.log('🔧 [DEBUG] agentState:', agentState);
        console.log('🔧 [DEBUG] currentFlowId:', currentFlowId);
        return;
    }

    console.log('🔧 [DEBUG] syncLangGraphNodes: Starting sync');
    console.log('🔧 [DEBUG] Full agentState:', agentState);
    console.log('🔧 [DEBUG] agentState.sas_step1_generated_tasks:', agentState.sas_step1_generated_tasks);
    console.log('🔧 [DEBUG] agentState.dialog_state:', agentState.dialog_state);

    const { nodes: langGraphNodesGenerated, edges: langGraphEdgesGenerated } = generateLangGraphNodes(agentState, currentFlowId);
    
    console.log('🔧 [DEBUG] Generated LangGraph nodes count:', langGraphNodesGenerated.length);
    console.log('🔧 [DEBUG] Generated LangGraph nodes:', langGraphNodesGenerated.map(n => ({ id: n.id, type: n.type })));
    
    const nonLangGraphNodes = nodesFromStore?.filter(node => !node.id.startsWith('langgraph_')) || [];
    
    // Edges need more careful filtering to not remove edges between non-langgraph nodes.
    const nonLangGraphEdges = edgesFromStore?.filter(edge => {
        const isLangGraphSource = edge.source.startsWith('langgraph_');
        const isLangGraphTarget = edge.target.startsWith('langgraph_');
        return !isLangGraphSource && !isLangGraphTarget;
    }) || [];

    const finalLangGraphNodes = langGraphNodesGenerated.map(genNode => {
        const existingNode = nodesFromStore?.find(n => n.id === genNode.id);
        if (existingNode) {
            return {
                ...existingNode,
                data: genNode.data,
                type: genNode.type,
                position: existingNode.position, 
            };
        }
        return genNode;
    });

    const updatedNodes = [...nonLangGraphNodes, ...finalLangGraphNodes];
    const updatedEdges = [...nonLangGraphEdges, ...langGraphEdgesGenerated]; 

    console.log('🔧 [DEBUG] Final updatedNodes count:', updatedNodes.length);
    console.log('🔧 [DEBUG] Final LangGraph nodes in update:', updatedNodes.filter(n => n.id.startsWith('langgraph_')).map(n => ({ id: n.id, type: n.type })));

    if (!_isEqual(updatedNodes, nodesFromStore)) {
        console.log('🔧 [DEBUG] Dispatching setNodes with updated nodes');
        dispatch(setNodes(updatedNodes));
    } else {
        console.log('🔧 [DEBUG] No node changes needed');
    }

    if (!_isEqual(updatedEdges, edgesFromStore)) {
        console.log('🔧 [DEBUG] Dispatching setEdges with updated edges');
        dispatch(setEdges(updatedEdges));
    } else {
        console.log('🔧 [DEBUG] No edge changes needed');
    }
  }, [agentState, currentFlowId, nodesFromStore, edgesFromStore, generateLangGraphNodes, dispatch]);

  // Auto-sync when agent state changes
  useEffect(() => {
    if (agentState && currentFlowId) {
      syncLangGraphNodes();
    }
  }, [agentState, currentFlowId, syncLangGraphNodes]);

  // 监听InputNode尺寸变化并实时更新后续节点位置 - 添加防抖和更严格的变化检测
  useEffect(() => {
    if (!currentFlowId || !nodesFromStore) return;

    const inputNodeId = `langgraph_input_${currentFlowId}`;
    const inputNode = nodesFromStore.find(n => n.id === inputNodeId);
    
    if (inputNode && inputNode.height && inputNode.width && inputNode.position) {
      const current = {
        width: inputNode.width,
        height: inputNode.height,
        x: inputNode.position.x,
        y: inputNode.position.y,
      };
      
      const previous = previousInputNodeDimensions.current;
      
      // 更严格的变化检测：使用更大的阈值来避免亚像素级变化
      const THRESHOLD = 5; // 5像素的变化阈值
      const dimensionsChanged = 
        Math.abs((previous.width || 0) - current.width) > THRESHOLD ||
        Math.abs((previous.height || 0) - current.height) > THRESHOLD ||
        Math.abs((previous.x || 0) - current.x) > THRESHOLD ||
        Math.abs((previous.y || 0) - current.y) > THRESHOLD;
      
      if (dimensionsChanged) {
        // 清除之前的定时器
        if (updateTimeoutRef.current) {
          clearTimeout(updateTimeoutRef.current);
        }
        
        // 限制更新频率
        const now = Date.now();
        const timeSinceLastUpdate = now - lastUpdateTimeRef.current;
        const MIN_UPDATE_INTERVAL = 300; // 最小更新间隔300ms
        
        if (timeSinceLastUpdate < MIN_UPDATE_INTERVAL) {
          console.log('🔧 [DEBUG] 更新过于频繁，使用防抖延迟');
          updateTimeoutRef.current = setTimeout(() => {
            processInputNodeChange(current);
          }, MIN_UPDATE_INTERVAL - timeSinceLastUpdate);
        } else {
          processInputNodeChange(current);
        }
      }
    }
    
    function processInputNodeChange(current: { width: number; height: number; x: number; y: number }) {
      // 检查必要的状态
      if (!currentFlowId || !nodesFromStore) return;
      
      const previous = previousInputNodeDimensions.current;
      console.log(`InputNode尺寸/位置变化: ${previous.width || 'undefined'}x${previous.height || 'undefined'} -> ${current.width}x${current.height}, 位置: (${previous.x || 'undefined'}, ${previous.y || 'undefined'}) -> (${current.x}, ${current.y})`);
      
      // 更新记录的尺寸
      previousInputNodeDimensions.current = current;
      lastUpdateTimeRef.current = Date.now();
      
      // 检查是否有task或detail节点需要重新定位
      const hasLangGraphChildren = nodesFromStore.some(n => 
        n.id.startsWith(`langgraph_task_${currentFlowId}_`) || 
        n.id.startsWith(`langgraph_detail_${currentFlowId}_`)
      );
      
      if (hasLangGraphChildren) {
        console.log('重新计算后续节点位置...');
        const recalculatedNodes = recalculatePositions(
          currentFlowId, 
          current.height, 
          current.width, 
          { x: current.x, y: current.y }
        );
        
        // 检查计算后的位置是否与现有位置不同
        const POSITION_THRESHOLD = 2; // 位置变化阈值
        const positionsChanged = recalculatedNodes.some(node => {
          const originalNode = nodesFromStore.find(n => n.id === node.id);
          return originalNode && (
            Math.abs((originalNode.position?.x || 0) - (node.position?.x || 0)) > POSITION_THRESHOLD ||
            Math.abs((originalNode.position?.y || 0) - (node.position?.y || 0)) > POSITION_THRESHOLD
          );
        });
        
        if (positionsChanged) {
          console.log('应用位置更新到后续节点');
          dispatch(setNodes(recalculatedNodes));
        } else {
          console.log('位置计算结果与现有位置相同，跳过更新');
        }
      }
    }
    
    // 清理函数
    return () => {
      if (updateTimeoutRef.current) {
        clearTimeout(updateTimeoutRef.current);
      }
    };
  }, [currentFlowId, nodesFromStore, recalculatePositions, dispatch]);

  return {
    syncLangGraphNodes,
    generateLangGraphNodes,
    recalculatePositions,
  };
}; 