import { useEffect, useCallback } from 'react';
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
  subgraph_completion_status?: string;
}

export const useLangGraphNodes = (agentState?: AgentState) => {
  const dispatch = useDispatch<AppDispatch>();
  const currentFlowId = useSelector(selectCurrentFlowId);
  const nodesFromStore = useSelector(selectNodes);
  const edgesFromStore = useSelector(selectEdges);

  const generateLangGraphNodes = useCallback((state: AgentState, flowId: string): { nodes: Node[], edges: Edge[] } => {
    const newNodes: Node[] = [];
    const newEdges: Edge[] = [];

    // 节点尺寸定义
    const INPUT_NODE_WIDTH = 600;
    const INPUT_NODE_HEIGHT = 400;
    const TASK_NODE_WIDTH = 400;
    const TASK_NODE_HEIGHT = 300;
    const DETAIL_NODE_WIDTH = TASK_NODE_WIDTH; // Detail node usually aligns with task node width
    const DETAIL_NODE_HEIGHT = 250; 
    
    // 间距定义
    const VERTICAL_SPACING = 100; // 垂直间距
    const HORIZONTAL_SPACING = 50; // 水平间距
    
    // Always create input node - 居中放置
    const inputNode: Node = {
      id: `langgraph_input_${flowId}`,
      type: 'langgraph_input',
      position: { x: 100, y: 50 }, // 从左侧开始，给任务节点留出扩展空间
      data: {
        label: '机器人任务描述',
        flowId: flowId,
        currentUserRequest: state.current_user_request || '',
      },
      width: INPUT_NODE_WIDTH,
      height: INPUT_NODE_HEIGHT,
    };
    newNodes.push(inputNode);

    // Create task nodes
    const tasks = state.sas_step1_generated_tasks || [];
    // 计算任务节点的Y位置 = 输入节点Y + 输入节点高度 + 垂直间距
    const taskYOffset = inputNode.position.y + INPUT_NODE_HEIGHT + VERTICAL_SPACING;
    
    tasks.forEach((task, i) => {
      // 计算任务节点的水平位置
      // 每个任务节点占用的宽度 = 节点宽度 + 水平间距
      const taskSlotWidth = TASK_NODE_WIDTH + HORIZONTAL_SPACING;
      
      // 计算居中起始位置
      const totalTasksWidth = tasks.length * taskSlotWidth - HORIZONTAL_SPACING; // 最后一个节点不需要额外间距
      const inputCenterX = inputNode.position.x + INPUT_NODE_WIDTH / 2; // 输入节点的中心X坐标
      const tasksStartX = inputCenterX - totalTasksWidth / 2; // 任务节点组的起始X坐标
      
      // 当前任务节点的X位置
      const taskX = tasksStartX + (i * taskSlotWidth);
      
      const taskNode: Node = {
        id: `langgraph_task_${flowId}_${i}`,
        type: 'langgraph_task',
        position: { x: taskX, y: taskYOffset },
        data: {
          label: `Task ${i + 1}`,
          flowId: flowId,
          taskIndex: i,
          task: task,
        },
        width: TASK_NODE_WIDTH,
        height: TASK_NODE_HEIGHT,
      };
      newNodes.push(taskNode);

      // Create edge from input to task
      const edgeId = `edge_input_to_task_${i}`;
      newEdges.push({
        id: edgeId,
        source: `langgraph_input_${flowId}`,
        target: taskNode.id,
        type: 'smoothstep',
      });

      // Create detail nodes for this task
      // 直接从任务对象的details字段获取模块步骤数据
      const details = task.details || [];

      if (details.length > 0) {
        // 详情节点位置 = 任务节点Y + 任务节点高度 + 垂直间距
        const detailY = taskYOffset + TASK_NODE_HEIGHT + VERTICAL_SPACING;
        
        const detailNode: Node = {
          id: `langgraph_detail_${flowId}_${i}`,
          type: 'langgraph_detail',
          position: { x: taskX, y: detailY }, // 与对应的任务节点对齐
          data: {
            label: `${task.name} - Steps`,
            flowId: flowId,
            taskIndex: i,
            taskName: task.name,
            details: details,
          },
          width: DETAIL_NODE_WIDTH,
          height: DETAIL_NODE_HEIGHT,
        };
        newNodes.push(detailNode);

        // Create edge from task to detail
        const detailEdgeId = `edge_task_${i}_to_detail`;
        newEdges.push({
          id: detailEdgeId,
          source: taskNode.id,
          target: detailNode.id,
          type: 'smoothstep',
        });
      }
    });

    return { nodes: newNodes, edges: newEdges };
  }, []);

  const syncLangGraphNodes = useCallback(() => {
    if (!agentState || !currentFlowId) {
        // console.log('SYNC: Aborting, no agentState or currentFlowId');
        return;
    }

    const { nodes: langGraphNodesGenerated, edges: langGraphEdgesGenerated } = generateLangGraphNodes(agentState, currentFlowId);
    
    const finalEnhancedLangGraphNodes = langGraphNodesGenerated.map(genNode => {
        const existingNode = nodesFromStore?.find(n => n.id === genNode.id);
        if (existingNode) {
            // Node exists: Start with the existing node from the store to preserve all its React Flow managed properties
            // (like position, width, height, selected, dragging, positionAbsolute etc.).
            // Then, only update the data and type from the agentState-driven generation.
            return {
                ...existingNode, // Preserves React Flow's state for position, width, height etc.
                data: genNode.data, // Update data from agentState generation
                type: genNode.type  // Update type from agentState generation (if it can change)
            };
        } else {
            // New node: use the generated node as is. 
            // This includes its initial position, width, and height as defined in generateLangGraphNodes.
            return genNode; 
        }
    });
    
    const nonLangGraphNodes = nodesFromStore?.filter(node => !node.id.startsWith('langgraph_')) || [];
    const nonLangGraphEdges = edgesFromStore?.filter(edge => 
      !edge.source.startsWith('langgraph_') && !edge.target.startsWith('langgraph_')
    ) || [];

    const updatedNodes = [...nonLangGraphNodes, ...finalEnhancedLangGraphNodes];
    const updatedEdges = [...nonLangGraphEdges, ...langGraphEdgesGenerated]; 

    let changed = false;
    if (!_isEqual(updatedNodes, nodesFromStore)) {
        dispatch(setNodes(updatedNodes));
        changed = true;
    }

    if (!_isEqual(updatedEdges, edgesFromStore)) {
        dispatch(setEdges(updatedEdges));
        changed = true;
    }

    if (changed) {
        console.log('SYNC: Dispatched node/edge updates because content changed.');
    } else {
        // console.log('SYNC: No actual content change in nodes/edges, dispatch skipped.');
    }

  }, [agentState, currentFlowId, nodesFromStore, edgesFromStore, generateLangGraphNodes, dispatch]);

  // Auto-sync when agent state changes
  useEffect(() => {
    if (agentState && currentFlowId) {
      syncLangGraphNodes();
    }
  }, [agentState, currentFlowId, syncLangGraphNodes]);

  return {
    syncLangGraphNodes,
    generateLangGraphNodes,
  };
}; 