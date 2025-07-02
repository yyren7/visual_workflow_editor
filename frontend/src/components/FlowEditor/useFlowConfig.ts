import { useState, useEffect, useMemo, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useSnackbar } from 'notistack';
import { Node, Edge, MarkerType, DefaultEdgeOptions } from 'reactflow';
import { getNodeTemplates, NodeTemplatesResponse } from '../../api/nodeTemplates';
import { calculateDynamicViewport } from './viewportUtils';
import { generateNodeTypes, processNodes } from './nodeUtils';
import { ReactFlowConfig } from './types';

interface UseFlowConfigProps {
  nodes: Node[];
  edges: Edge[];
  agentState: any;
}

export const useFlowConfig = ({ nodes, edges, agentState }: UseFlowConfigProps) => {
  const { t } = useTranslation();
  const { enqueueSnackbar } = useSnackbar();

  // --- State for Node Templates ---
  const [nodeTemplates, setNodeTemplates] = useState<NodeTemplatesResponse | null>(null);
  const [templatesLoading, setTemplatesLoading] = useState<boolean>(true);
  const [templatesError, setTemplatesError] = useState<string | null>(null);

  // --- Effect to fetch Node Templates ---
  useEffect(() => {
    const fetchTemplates = async () => {
      try {
        setTemplatesLoading(true);
        setTemplatesError(null);
        const templates = await getNodeTemplates();
        setNodeTemplates(templates);
        console.log("FlowEditor: Node templates fetched successfully.", templates);
      } catch (error: any) {
        console.error("FlowEditor: Failed to fetch node templates:", error);
        setTemplatesError(error.message || 'Failed to load node templates');
        enqueueSnackbar(t('flowEditor.errorLoadingTemplates'), { variant: 'error' });
      } finally {
        setTemplatesLoading(false);
      }
    };
    fetchTemplates();
  }, [enqueueSnackbar, t]);

  // --- Dynamically generate nodeTypes using useMemo ---
  const nodeTypes = useMemo(() => {
    return generateNodeTypes(nodeTemplates);
  }, [nodeTemplates]);

  // --- Process nodes for LangGraph特殊属性 ---
  const processedNodes = useMemo(() => {
    return processNodes(nodes);
  }, [nodes]);

  // --- ReactFlow实例配置，包含动态边界限制 ---
  const reactFlowConfig: ReactFlowConfig = useMemo(() => {
    const viewport = calculateDynamicViewport(nodes);
    return {
      translateExtent: viewport.translateExtent,
      nodeExtent: viewport.nodeExtent,
      minZoom: viewport.minZoom,
      maxZoom: viewport.maxZoom,
    };
  }, [nodes]);

  // --- Constants needed by ReactFlow ---
  const defaultEdgeOptions: DefaultEdgeOptions = useMemo(() => ({
    animated: false,
    style: {
      stroke: '#888',
      strokeWidth: 2,
    },
    markerEnd: {
      type: MarkerType.ArrowClosed,
      color: '#888',
      width: 20,
      height: 20,
    },
    type: 'smoothstep',
  }), []);
  
  const connectionLineStyle = useMemo(() => ({
    stroke: '#1976d2',
    strokeWidth: 2,
    strokeDasharray: '5 5',
  }), []);

  // 临时调试函数
  const debugAgentState = useCallback(() => {
    console.log('🐛 [DEBUG] Manual debug trigger');
    console.log('🐛 [DEBUG] Agent state:', agentState);
    console.log('🐛 [DEBUG] Current nodes:', nodes.length);
    console.log('🐛 [DEBUG] LangGraph nodes:', nodes.filter(n => n.id.startsWith('langgraph_')));
    
    if (agentState?.sas_step1_generated_tasks?.length) {
      console.log('🐛 [DEBUG] Found tasks in agent state');
    } else {
      console.log('🐛 [DEBUG] No tasks found in agent state');
    }
  }, [agentState, nodes]);

  return {
    nodeTemplates,
    templatesLoading,
    templatesError,
    nodeTypes,
    processedNodes,
    reactFlowConfig,
    defaultEdgeOptions,
    connectionLineStyle,
    debugAgentState
  };
}; 