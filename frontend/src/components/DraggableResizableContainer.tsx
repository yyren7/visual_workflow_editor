import React, { useState, ReactNode, useEffect } from 'react';
import Draggable from 'react-draggable';
import { Resizable, ResizeCallbackData } from 'react-resizable';
import { Box, IconButton, Typography } from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import 'react-resizable/css/styles.css';

interface DraggableResizableContainerProps {
  title: string;
  icon: ReactNode;
  isOpen: boolean;
  onClose: () => void;
  defaultPosition?: { x: number; y: number };
  defaultSize?: { width: number; height: number };
  minWidth?: number;
  minHeight?: number;
  maxWidth?: number;
  maxHeight?: number;
  zIndex?: number;
  children: ReactNode;
}

/**
 * 可拖动和可调整大小的容器组件
 */
const DraggableResizableContainer: React.FC<DraggableResizableContainerProps> = ({
  title,
  icon,
  isOpen,
  onClose,
  defaultPosition = { x: 0, y: 0 },
  defaultSize = { width: 350, height: 300 },
  minWidth = 250,
  minHeight = 200,
  maxWidth = 800,
  maxHeight = 800,
  zIndex = 5,
  children
}) => {
  const [size, setSize] = useState(defaultSize);
  const [position, setPosition] = useState(defaultPosition);

  // 当组件打开时重置为默认位置
  useEffect(() => {
    if (isOpen) {
      setPosition(defaultPosition);
    }
  }, [isOpen, defaultPosition]);

  if (!isOpen) return null;

  const handleResize = (e: React.SyntheticEvent, data: ResizeCallbackData) => {
    setSize({
      width: data.size.width,
      height: data.size.height
    });
  };

  const handleDragStop = (e: any, data: any) => {
    setPosition({ x: data.x, y: data.y });
  };

  return (
    <Draggable
      position={position}
      onStop={handleDragStop}
      bounds="parent"
      handle=".drag-handle"
      cancel=".cancel-drag"
    >
      <div
        style={{
          position: 'absolute',
          width: `${size.width}px`,
          height: `${size.height}px`,
          zIndex: zIndex
        }}
      >
        <Resizable
          width={size.width}
          height={size.height}
          minConstraints={[minWidth, minHeight]}
          maxConstraints={[maxWidth, maxHeight]}
          onResize={handleResize}
          resizeHandles={['se']}
        >
          <Box
            sx={{
              width: `${size.width}px`,
              height: `${size.height}px`,
              bgcolor: '#2d2d2d',
              borderRadius: '4px',
              boxShadow: '0 4px 20px rgba(0,0,0,0.5)',
              display: 'flex',
              flexDirection: 'column',
              border: '1px solid #444',
              overflow: 'hidden'
            }}
          >
            <Box
              className="drag-handle"
              sx={{
                p: 1,
                bgcolor: '#333',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                borderBottom: '1px solid #444',
                cursor: 'move'
              }}
            >
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                {icon}
                <Typography variant="subtitle2">{title}</Typography>
              </Box>
              <IconButton
                className="cancel-drag"
                size="small"
                color="inherit"
                onClick={onClose}
              >
                <CloseIcon fontSize="small" />
              </IconButton>
            </Box>
            <Box 
              sx={{ 
                p: 0, 
                overflowY: 'auto', 
                flexGrow: 1, 
                height: `calc(${size.height}px - 40px)`,
                '&::-webkit-scrollbar': {
                  width: '8px',
                },
                '&::-webkit-scrollbar-track': {
                  background: '#333',
                },
                '&::-webkit-scrollbar-thumb': {
                  background: '#666',
                  borderRadius: '4px',
                },
                '&::-webkit-scrollbar-thumb:hover': {
                  background: '#888',
                }
              }}
            >
              {children}
            </Box>
          </Box>
        </Resizable>
      </div>
    </Draggable>
  );
};

export default DraggableResizableContainer; 