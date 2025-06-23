import { useEffect, useCallback } from 'react';
import { Node, Edge } from 'reactflow';
import { useSelector, useDispatch } from 'react-redux';
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
  }>;
  sas_step2_generated_task_details?: {
    [taskIndex: string]: {
      details: string[];
    };
  };
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
  const nodes = useSelector(selectNodes);
  const edges = useSelector(selectEdges);

  const generateLangGraphNodes = useCallback((state: AgentState, flowId: string): { nodes: Node[], edges: Edge[] } => {
    const newNodes: Node[] = [];
    const newEdges: Edge[] = [];

    // 节点尺寸定义
    const INPUT_NODE_WIDTH = 600;
    const INPUT_NODE_HEIGHT = 400;
    const TASK_NODE_WIDTH = 400;
    const TASK_NODE_HEIGHT = 300;
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
      const taskDetails = state.sas_step2_generated_task_details?.[i.toString()];
      const details = taskDetails?.details || [];

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
    if (!agentState || !currentFlowId) return;

    const { nodes: langGraphNodes, edges: langGraphEdges } = generateLangGraphNodes(agentState, currentFlowId);
    
    // Filter out existing LangGraph nodes
    const nonLangGraphNodes = nodes.filter(node => !node.id.startsWith('langgraph_'));
    const nonLangGraphEdges = edges.filter(edge => 
      !edge.source.startsWith('langgraph_') && !edge.target.startsWith('langgraph_')
    );

    // Combine with new LangGraph nodes
    const updatedNodes = [...nonLangGraphNodes, ...langGraphNodes];
    const updatedEdges = [...nonLangGraphEdges, ...langGraphEdges];

    // Update the store
    dispatch(setNodes(updatedNodes));
    dispatch(setEdges(updatedEdges));
  }, [agentState, currentFlowId, nodes, edges, generateLangGraphNodes, dispatch]);

  // Auto-sync when agent state changes
  useEffect(() => {
    // Added detailed log
    console.log(
      `🔄 useLangGraphNodes: EFFECT TRIGGERED. Current Flow ID: ${currentFlowId}. AgentState tasks:`, 
      agentState?.sas_step1_generated_tasks || 'No tasks in agentState', 
      'Full agentState:', agentState
    );

    if (agentState && currentFlowId) {
      console.log('🔄 useLangGraphNodes: Agent state changed, analyzing...', {
        currentFlowId,
        hasTasks: !!(agentState.sas_step1_generated_tasks?.length),
        taskCount: agentState.sas_step1_generated_tasks?.length || 0,
        hasDetails: !!(agentState.sas_step2_generated_task_details && Object.keys(agentState.sas_step2_generated_task_details).length),
        detailCount: agentState.sas_step2_generated_task_details ? Object.keys(agentState.sas_step2_generated_task_details).length : 0,
        dialogState: agentState.dialog_state,
        currentUserRequest: agentState.current_user_request
      });
      
      // 详细记录任务信息
      if (agentState.sas_step1_generated_tasks?.length) {
        console.log('🔄 Tasks found:');
        agentState.sas_step1_generated_tasks.forEach((task, index) => {
          console.log(`🔄   Task ${index + 1}: ${task.name} (${task.type})`);
        });
      }
      
      // 详细记录任务详情信息
      if (agentState.sas_step2_generated_task_details && Object.keys(agentState.sas_step2_generated_task_details).length) {
        console.log('🔄 Task details found:');
        Object.entries(agentState.sas_step2_generated_task_details).forEach(([taskIdx, details]) => {
          if (details && details.details) {
            console.log(`🔄   Task ${taskIdx}: ${details.details.length} details`);
          }
        });
      }
      
      console.log('🔄 Current nodes count:', nodes.length);
      console.log('🔄 Current LangGraph nodes:', nodes.filter(node => node.id.startsWith('langgraph_')).map(n => n.id));
      
      // 同步节点
      console.log('🔄 Calling syncLangGraphNodes...');
      syncLangGraphNodes();
      
      // 验证同步结果
      setTimeout(() => {
        console.log('🔄 Node sync completed. Verifying results...');
        // 这个延迟确保Redux状态已经更新
      }, 50);
    } else {
      console.log('🔄 useLangGraphNodes: Conditions not met for syncing', {
        hasAgentState: !!agentState,
        hasCurrentFlowId: !!currentFlowId
      });
    }
  }, [agentState, currentFlowId, syncLangGraphNodes]); // Added syncLangGraphNodes back as it's a function used inside and should be a dependency if it's stable (useCallback)

  return {
    syncLangGraphNodes,
    generateLangGraphNodes,
  };
}; 