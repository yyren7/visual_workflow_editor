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
}

export const useLangGraphNodes = (agentState?: AgentState) => {
  const dispatch = useDispatch<AppDispatch>();
  const currentFlowId = useSelector(selectCurrentFlowId);
  const nodes = useSelector(selectNodes);
  const edges = useSelector(selectEdges);

  const generateLangGraphNodes = useCallback((state: AgentState, flowId: string): { nodes: Node[], edges: Edge[] } => {
    const newNodes: Node[] = [];
    const newEdges: Edge[] = [];

    // Always create input node
    const inputNode: Node = {
      id: `langgraph_input_${flowId}`,
      type: 'langgraph_input',
      position: { x: 400, y: 50 },
      data: {
        label: '机器人任务描述',
        flowId: flowId,
        currentUserRequest: state.current_user_request || '',
      },
    };
    newNodes.push(inputNode);

    // Create task nodes
    const tasks = state.sas_step1_generated_tasks || [];
    const taskYOffset = 250;
    
    tasks.forEach((task, i) => {
      // 计算居中位置，让多个任务节点在input节点下方居中排列
      const totalWidth = tasks.length * 350; // 每个任务节点350px宽度间隔
      const startX = 400 - totalWidth / 2 + 175; // 从中央开始，向左偏移一半总宽度，再加上节点宽度的一半
      
      const taskNode: Node = {
        id: `langgraph_task_${flowId}_${i}`,
        type: 'langgraph_task',
        position: { x: startX + (i * 350), y: taskYOffset }, // 居中排列
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
        const detailNode: Node = {
          id: `langgraph_detail_${flowId}_${i}`,
          type: 'langgraph_detail',
          position: { x: startX + (i * 350), y: taskYOffset + 200 }, // 在对应task节点下方
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
    if (agentState && currentFlowId) {
      console.log('useLangGraphNodes: Agent state changed, syncing nodes...', {
        currentFlowId,
        hasTasks: !!(agentState.sas_step1_generated_tasks?.length),
        taskCount: agentState.sas_step1_generated_tasks?.length || 0
      });
      syncLangGraphNodes();
    }
  }, [agentState, currentFlowId]); // Remove syncLangGraphNodes from deps to avoid infinite loop

  return {
    syncLangGraphNodes,
    generateLangGraphNodes,
  };
}; 