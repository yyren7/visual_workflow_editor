import React, { useState, useEffect, useRef, useCallback, CSSProperties, ReactNode, SyntheticEvent } from 'react';
import { Box, Paper, IconButton, Typography } from '@mui/material';
import Draggable, { DraggableData, DraggableEvent } from 'react-draggable';
import CloseIcon from '@mui/icons-material/Close';
import { ResizableBox, ResizeCallbackData, ResizableBoxProps, ResizeHandle } from 'react-resizable';
import 'react-resizable/css/styles.css';
import { useDraggablePanelPosition } from '../hooks/useDraggablePanelPosition';

interface DraggableResizableContainerProps {
  title: string;
  icon?: ReactNode;
  isOpen: boolean;
  onClose: () => void;
  children: ReactNode;
  defaultPosition?: { x: number; y: number };
  defaultSize?: { width: number | string; height: number | string };
  minConstraints?: [number, number];
  maxConstraints?: [number, number];
  zIndex?: number;
  resizable?: boolean;
}

/**
 * 可拖动和可调整大小的容器组件
 */
const DraggableResizableContainer: React.FC<DraggableResizableContainerProps> = ({
  title,
  icon,
  isOpen,
  onClose,
  children,
  defaultPosition = { x: 100, y: 100 },
  defaultSize = { width: 400, height: 300 },
  minConstraints = [200, 150],
  maxConstraints = [Infinity, Infinity],
  zIndex = 10,
  resizable = true,
}) => {
  const nodeRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState(() => ({
    width: typeof defaultSize.width === 'string' ? parseInt(defaultSize.width) : defaultSize.width,
    height: typeof defaultSize.height === 'string' ? parseInt(defaultSize.height) : defaultSize.height
  }));

  const {
    position,
    setPosition,
    handleDragStart,
    handleDragStop,
    bounds
  } = useDraggablePanelPosition({
    initialPosition: defaultPosition,
    panelWidth: size.width,
    panelHeight: size.height,
  });

  const handleDrag = (e: DraggableEvent, data: DraggableData) => {
    setPosition({ x: data.x, y: data.y });
  };

  const handleResize = (event: SyntheticEvent, data: ResizeCallbackData) => {
    setSize({ width: data.size.width, height: data.size.height });
  };

  if (!isOpen) {
    return null;
  }

  const ContainerContent = (
    <Paper
      elevation={5}
      sx={{
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        border: '1px solid #555',
        borderRadius: '4px',
        bgcolor: '#2d2d2d',
        color: 'white',
        width: '100%',
        height: '100%',
      }}
    >
      <Box
        className="drag-handle"
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          p: 1,
          bgcolor: '#333',
          cursor: 'move',
          borderBottom: '1px solid #444'
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          {icon}
          <Typography variant="subtitle2">{title}</Typography>
        </Box>
        <IconButton size="small" color="inherit" onClick={onClose} className="no-drag">
          <CloseIcon fontSize="small" />
        </IconButton>
      </Box>
      <Box
        className="no-drag"
        sx={{
          flexGrow: 1,
          p: 1,
          overflow: 'auto',
          height: 'calc(100% - 49px)',
        }}
      >
        {children}
      </Box>
    </Paper>
  );

  const divStyle: CSSProperties = {
    position: 'absolute',
    zIndex: zIndex,
    width: size.width,
    height: size.height,
    overflow: 'hidden'
  };

  return (
    <Draggable
      nodeRef={nodeRef}
      handle=".drag-handle"
      cancel=".no-drag"
      position={position}
      onDrag={handleDrag}
      onStart={handleDragStart}
      onStop={handleDragStop}
      bounds={bounds}
    >
      {resizable ? (
        <div ref={nodeRef} style={{ position: 'absolute', zIndex: zIndex }}>
          <ResizableBox
            width={size.width}
            height={size.height}
            minConstraints={minConstraints}
            maxConstraints={maxConstraints}
            onResize={handleResize}
            resizeHandles={['se'] as any}
          >
            {ContainerContent}
          </ResizableBox>
        </div>
      ) : (
        <div 
          ref={nodeRef} 
          style={divStyle}
        >
          {ContainerContent}
        </div>
      )}
    </Draggable>
  );
};

export default DraggableResizableContainer; 