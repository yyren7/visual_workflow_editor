import { useState, useCallback, useEffect } from 'react';

// Define explicit types for callbacks
type VoidCallback = () => void;
type MouseEventCallback<T extends HTMLElement = HTMLElement> = (event: React.MouseEvent<T>) => void;

// 新增：定义面板状态的类型
export interface PanelStates {
  sidebarOpen: boolean;
  nodeInfoOpen: boolean;
  globalVarsOpen: boolean;
  chatOpen: boolean;
  flowSelectOpen: boolean;
}

export const usePanelManager = () => {
  // 将所有状态合并到一个对象中
  const [panelStates, setPanelStates] = useState<PanelStates>({
    sidebarOpen: false,
    nodeInfoOpen: false,
    globalVarsOpen: false,
    chatOpen: false,
    flowSelectOpen: false,
  });

  const [toggleMenuAnchorEl, setToggleMenuAnchorEl] = useState<null | HTMLElement>(null);
  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null); // For user menu

  // --- Panel Positions ---
  // Default X position for side panels
  const defaultPanelX = 10;
  const [nodeInfoPosition, setNodeInfoPosition] = useState<{ x: number; y: number }>({
      x: defaultPanelX,
      y: typeof window !== 'undefined' ? (window.innerHeight - 400) / 2 : 100 // Center vertically initially
  });
  const [chatPosition, setChatPosition] = useState<{ x: number; y: number }>({
    x: typeof window !== 'undefined' ? Math.max(0, window.innerWidth - 720) : 100,
    y: typeof window !== 'undefined' ? Math.max(48 + 5, Math.min(window.innerHeight - 600 - (48 + 10), window.innerHeight / 2)) : 100
  });
  const [globalVarsPosition, setGlobalVarsPosition] = useState<{ x: number; y: number }>({
    x: typeof window !== 'undefined' ? Math.max(0, window.innerWidth - 600) : 50,
    y: typeof window !== 'undefined' ? 48 + 5 : 50
  });

  // Recalculate positions on resize
  useEffect(() => {
    if (typeof window === 'undefined') return;

    const handleResize = () => {
      const newWidth = window.innerWidth;
      const newHeight = window.innerHeight;
      const topNavHeight = 48;

      // Node Info Panel (assuming it stays near the left)
      setNodeInfoPosition(prev => {
        const panelHeight = 400; // Estimate or get dynamically?
        const minY = topNavHeight + 5;
        const maxY = newHeight - panelHeight - 5;
        return { x: defaultPanelX, y: Math.min(Math.max(prev.y, minY), maxY) };
      });

      // Chat Panel
      setChatPosition(prev => {
          const panelWidth = 700;
          const panelHeight = 600;
          const minX = - (panelWidth - 120); // Allow partial hide
          const maxX = newWidth - 120; // Keep some part visible
          const minY = topNavHeight + 5;
          const maxY = newHeight - panelHeight - (topNavHeight + 10);
          return { x: Math.min(Math.max(prev.x, minX), maxX), y: Math.min(Math.max(prev.y, minY), maxY) };
      });

      // Global Vars Panel
      setGlobalVarsPosition(prev => {
          const panelWidth = 600;
          const panelHeight = 320;
          const minX = - (panelWidth - 120);
          const maxX = newWidth - 120;
          const minY = topNavHeight + 5;
          const maxY = newHeight - panelHeight - (topNavHeight + 10);
          return { x: Math.min(Math.max(prev.x, minX), maxX), y: Math.min(Math.max(prev.y, minY), maxY) };
      });
    };

    window.addEventListener('resize', handleResize);
    handleResize(); // Call once initially to set positions based on current size
    return () => window.removeEventListener('resize', handleResize);
  }, []); // Empty dependency array means this runs once on mount

  // --- Generic Toggle Function ---
  const togglePanel = useCallback((panel: keyof PanelStates) => {
    setPanelStates(prev => ({ ...prev, [panel]: !prev[panel] }));
  }, []);

  // --- Specific Open/Close Functions ---
  const openPanel = useCallback((panel: keyof PanelStates) => {
    setPanelStates(prev => ({ ...prev, [panel]: true }));
  }, []);

  const closePanel = useCallback((panel: keyof PanelStates) => {
    setPanelStates(prev => ({ ...prev, [panel]: false }));
  }, []);


  // --- Menu Handlers ---
  const handleToggleMenuOpen: MouseEventCallback<HTMLButtonElement> = useCallback((event) => {
      setToggleMenuAnchorEl(event.currentTarget);
    }, []);
  
    const handleToggleMenuClose: VoidCallback = useCallback(() => {
      setToggleMenuAnchorEl(null);
    }, []);
  
    const handleMenuOpen: MouseEventCallback = useCallback((event) => {
      setAnchorEl(event.currentTarget);
    }, []);
  
    const handleMenuClose: VoidCallback = useCallback(() => {
      setAnchorEl(null);
    }, []);
  
    const handleOpenFlowSelect: VoidCallback = useCallback(() => {
      handleMenuClose(); // Close user menu when opening flow select
      openPanel('flowSelectOpen');
    }, [handleMenuClose, openPanel]);
  
    const handleCloseFlowSelect: VoidCallback = useCallback(() => {
      closePanel('flowSelectOpen');
    }, [closePanel]);

  // Function to close the NodeInfo panel specifically
  const closeNodeInfoPanel: VoidCallback = useCallback(() => {
    closePanel('nodeInfoOpen');
  }, [closePanel]);

  // Explicit function to open node info (e.g., on node click)
  const openNodeInfoPanel: VoidCallback = useCallback(() => {
      // Optional: Reset position when opening
      // setNodeInfoPosition({ x: defaultPanelX, y: typeof window !== 'undefined' ? (window.innerHeight - 400) / 2 : 100 });
      openPanel('nodeInfoOpen');
  }, [openPanel]);

  return {
    panelStates,
    setPanelStates,
    togglePanel,
    openPanel,
    closePanel,
    
    // Positions
    nodeInfoPosition,
    chatPosition,
    globalVarsPosition,

    // Menu-related state and handlers (can be refactored out if they grow)
    toggleMenuAnchorEl,
    anchorEl,
    handleToggleMenuOpen,
    handleToggleMenuClose,
    handleMenuOpen,
    handleMenuClose,

    // Keep direct handlers that have extra logic
    handleOpenFlowSelect,
    handleCloseFlowSelect,
    openNodeInfoPanel,
    closeNodeInfoPanel,
  };
}; 