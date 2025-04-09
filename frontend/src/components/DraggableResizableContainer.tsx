import React, { useState, ReactNode, useEffect, useRef } from 'react';
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
  resizable?: boolean;
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
  maxWidth = 2000,
  maxHeight = 2000,
  zIndex = 5,
  resizable = true,
  children
}) => {
  const [size, setSize] = useState(defaultSize);
  const [position, setPosition] = useState(defaultPosition);
  const containerRef = useRef<HTMLDivElement>(null);
  const draggableNodeRef = useRef<HTMLDivElement>(null);

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

  const ensureVisibility = () => {
    if (!draggableNodeRef.current) return;
    
    const windowWidth = window.innerWidth;
    const windowHeight = window.innerHeight;
    
    // 增加底部安全边距，考虑顶部导航栏高度
    const topNavHeight = 0; // 顶部导航栏高度
    const bottomSafetyMargin = topNavHeight + 10; // 安全边距加上顶部导航栏的高度
    
    const rect = draggableNodeRef.current.getBoundingClientRect();
    let newX = position.x;
    let newY = position.y;
    
    // 顶部检查 - 确保标题栏完全在可视区域内，考虑顶部导航栏
    if (rect.top < topNavHeight) {
      newY = position.y - rect.top + topNavHeight + 5; // 加5px额外空间
    }
    
    // 左侧检查 - 确保至少有部分可见
    if (rect.left < 0) {
      newX = position.x - rect.left + 20;
    }
    
    // 右侧检查 - 确保至少有部分可见
    if (rect.right > windowWidth) {
      newX = position.x - (rect.right - windowWidth) - 20;
    }
    
    // 底部检查 - 确保整个窗口在可视区域内，并添加安全边距
    if (rect.bottom > windowHeight - bottomSafetyMargin) {
      newY = position.y - (rect.bottom - windowHeight) - bottomSafetyMargin;
    }
    
    if (newX !== position.x || newY !== position.y) {
      setPosition({ x: newX, y: newY });
    }
  };

  const handleDragStop = (e: any, data: any) => {
    const windowWidth = window.innerWidth;
    const windowHeight = window.innerHeight;
    
    // 增加底部安全边距，考虑顶部导航栏高度
    const topNavHeight = 0; // 顶部导航栏高度
    const bottomSafetyMargin = topNavHeight + 10; // 安全边距加上顶部导航栏的高度
    
    let newX = data.x;
    let newY = data.y;
    
    // 右边界检查 - 确保窗口不会超出右边界
    if (newX + 20 > windowWidth) {
      newX = windowWidth - 20;
    }
    
    // 底部边界检查 - 考虑整个窗口的高度和顶部导航栏
    if (newY + size.height > windowHeight - bottomSafetyMargin) {
      newY = windowHeight - size.height - bottomSafetyMargin;
    }
    
    // 左边界检查 - 确保至少有部分内容在可视区域内
    if (newX + size.width - 20 < 0) {
      newX = -size.width + 20;
    }
    
    // 顶部边界检查 - 确保标题栏不超过顶部导航栏
    if (newY < topNavHeight) {
      newY = topNavHeight + 5; // 加5px额外空间
    }
    
    setPosition({ x: newX, y: newY });
  };

  return (
    <Draggable
      nodeRef={draggableNodeRef}
      position={position}
      onStop={handleDragStop}
      bounds="parent"
      handle=".drag-handle"
      cancel=".cancel-drag"
    >
      <div
        ref={draggableNodeRef}
        style={{
          position: 'absolute',
          width: `${size.width}px`,
          height: `${size.height}px`,
          zIndex: zIndex
        }}
      >
        {resizable ? (
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
        ) : (
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
        )}
      </div>
    </Draggable>
  );
};

export default DraggableResizableContainer; 