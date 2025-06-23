import React, { RefObject } from 'react';
import ReactFlow, {
  Controls,
  Background,
  Node,
  Edge,
  Connection,
  NodeMouseHandler,
  ReactFlowInstance,
  NodeTypes,
  BackgroundVariant,
  DefaultEdgeOptions,
  ConnectionLineType,
  Panel,
  ReactFlowProps, // Import base props
} from 'reactflow';
import { Box, Tooltip, IconButton } from '@mui/material';
import SortIcon from '@mui/icons-material/Sort';
import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh';
import { useTranslation } from 'react-i18next';
import { NodeData } from './FlowEditor'; // Adjust path if needed
import VersionInfo from './VersionInfo';

// Define Props for the FlowCanvas component
// Inherit basic ReactFlowProps and add/override specific ones
interface FlowCanvasProps extends Omit<ReactFlowProps, 'nodes' | 'edges'> {
  nodes: Node<NodeData>[];
  edges: Edge[];
  reactFlowWrapperRef: RefObject<HTMLDivElement>;
  nodeTypes: NodeTypes;
  defaultEdgeOptions: DefaultEdgeOptions;
  connectionLineStyle: React.CSSProperties;
  // Pass layout handlers
  onAutoLayout: () => void;
  onOptimizeEdges?: () => void; // Make optimize optional for now
  // Add drag handlers
  onNodeDragStart?: (event: React.MouseEvent, node: Node) => void;
  onNodeDragStop?: (event: React.MouseEvent, node: Node) => void;
  // 新增：动态边界配置
  reactFlowConfig?: {
    translateExtent: [[number, number], [number, number]];
    nodeExtent: [[number, number], [number, number]];
    minZoom: number;
    maxZoom: number;
  };
  // 添加删除事件处理器
  onNodesDelete?: (deletedNodes: Node[]) => void;
  onEdgesDelete?: (deletedEdges: Edge[]) => void;
}

const FlowCanvas: React.FC<FlowCanvasProps> = ({
  nodes,
  edges,
  reactFlowWrapperRef,
  nodeTypes,
  defaultEdgeOptions,
  connectionLineStyle,
  onNodesChange,
  onEdgesChange,
  onConnect,
  onInit,
  onNodeClick,
  onPaneClick,
  onDrop,
  onDragOver,
  onAutoLayout,
  onOptimizeEdges,
  // Destructure drag handlers
  onNodeDragStart,
  onNodeDragStop,
  // 新增：解构动态边界配置
  reactFlowConfig,
  // 新增：解构删除处理器
  onNodesDelete,
  onEdgesDelete,
  ...rest // Pass any remaining ReactFlowProps
}) => {
  const { t } = useTranslation();

  return (
    <Box
      ref={reactFlowWrapperRef}
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
          display: 'none'
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
        panOnDrag={true} // 修改为true，允许拖拽画布
        zoomOnScroll={true}
        zoomOnPinch={true}
        snapToGrid={false}
        snapGrid={[5, 5]}
        defaultEdgeOptions={defaultEdgeOptions}
        connectionLineStyle={connectionLineStyle}
        connectionLineType={ConnectionLineType.SmoothStep}
        elevateEdgesOnSelect={true}
        fitView
        style={{
          width: '100%',
          height: '100%',
          background: '#1e1e1e'
        }}
        className="fullscreen-flow"
        onPaneClick={onPaneClick}
        // Pass drag handlers to ReactFlow
        onNodeDragStart={onNodeDragStart}
        onNodeDragStop={onNodeDragStop}
        // 应用动态边界配置
        translateExtent={reactFlowConfig?.translateExtent}
        nodeExtent={reactFlowConfig?.nodeExtent}
        minZoom={reactFlowConfig?.minZoom}
        maxZoom={reactFlowConfig?.maxZoom}
        // 添加删除事件处理器
        onNodesDelete={onNodesDelete}
        onEdgesDelete={onEdgesDelete}
        {...rest} // Spread remaining props
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

        <Panel position="top-left" style={{ marginTop: '50px', backgroundColor: '#2d2d2d', color: '#fff', borderRadius: '4px', padding: '8px', border: '1px solid #444' }}>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
            <Tooltip title={t('flowEditor.autoLayout')}>
              <IconButton
                size="small"
                onClick={onAutoLayout}
                sx={{ color: '#fff', borderColor: '#666', '&:hover': { borderColor: '#888', backgroundColor: 'rgba(255, 255, 255, 0.08)' } }}
              >
                <SortIcon fontSize="small" />
              </IconButton>
            </Tooltip>
            {/* Optimize button might need adjustment or temporary removal */}
            {onOptimizeEdges && (
              <Tooltip title="Optimize Edges">
                <IconButton
                  size="small"
                  onClick={onOptimizeEdges}
                  sx={{ color: '#fff', borderColor: '#666', '&:hover': { borderColor: '#888', backgroundColor: 'rgba(255, 255, 255, 0.08)' } }}
                >
                  <AutoFixHighIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            )}
          </Box>
        </Panel>
      </ReactFlow>
    </Box>
  );
};

export default FlowCanvas; 