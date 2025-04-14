import { useState, useCallback, useEffect } from 'react';

// Define explicit types for callbacks
type VoidCallback = () => void;
type MouseEventCallback<T extends HTMLElement = HTMLElement> = (event: React.MouseEvent<T>) => void;

export const usePanelManager = () => {
  const [sidebarOpen, setSidebarOpen] = useState<boolean>(false);
  const [nodeInfoOpen, setNodeInfoOpen] = useState<boolean>(false);
  const [globalVarsOpen, setGlobalVarsOpen] = useState<boolean>(false);
  const [chatOpen, setChatOpen] = useState<boolean>(false);
  const [toggleMenuAnchorEl, setToggleMenuAnchorEl] = useState<null | HTMLElement>(null);
  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null); // For user menu
  const [flowSelectOpen, setFlowSelectOpen] = useState<boolean>(false);

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

  // Toggle functions
  const toggleSidebar: VoidCallback = useCallback(() => setSidebarOpen(prev => !prev), []);

  // Modified toggle for Node Info to handle position reset if needed
  const toggleNodeInfo: VoidCallback = useCallback(() => {
      setNodeInfoOpen(prev => {
          // Optional: Reset position when opening?
          // if (!prev) {
          //     setNodeInfoPosition({ x: defaultPanelX, y: typeof window !== 'undefined' ? (window.innerHeight - 400) / 2 : 100 });
          // }
          return !prev;
      });
  }, []);

  const toggleGlobalVarsPanel: VoidCallback = useCallback(() => {
      setGlobalVarsOpen(prev => {
          // Optional: Reset position?
          // if (!prev && typeof window !== 'undefined') {
          //     setGlobalVarsPosition({ x: Math.max(0, window.innerWidth - 600), y: 48 + 5 });
          // }
          return !prev;
      });
  }, []);

  const toggleChatPanel: VoidCallback = useCallback(() => {
      setChatOpen(prev => {
          // Optional: Reset position?
          // if (!prev && typeof window !== 'undefined') {
          //     const topNavHeight = 48;
          //     setChatPosition({ x: Math.max(0, window.innerWidth - 720), y: Math.max(topNavHeight + 5, window.innerHeight - 600 - (topNavHeight + 10)) });
          // }
          return !prev;
      });
  }, []);

  // ... other callbacks (handleToggleMenuOpen, etc.) ...
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
      setFlowSelectOpen(true);
    }, [handleMenuClose]);
  
    const handleCloseFlowSelect: VoidCallback = useCallback(() => {
      setFlowSelectOpen(false);
    }, []);

  // Function to close the NodeInfo panel specifically
  const closeNodeInfoPanel: VoidCallback = useCallback(() => {
    setNodeInfoOpen(false);
  }, []);

  // Explicit function to open node info (e.g., on node click)
  const openNodeInfoPanel: VoidCallback = useCallback(() => {
      // Optional: Reset position when opening
      // setNodeInfoPosition({ x: defaultPanelX, y: typeof window !== 'undefined' ? (window.innerHeight - 400) / 2 : 100 });
      setNodeInfoOpen(true);
  }, []);

  return {
    sidebarOpen,
    nodeInfoOpen,
    globalVarsOpen,
    chatOpen,
    toggleMenuAnchorEl,
    anchorEl,
    flowSelectOpen,
    // Positions
    nodeInfoPosition,
    chatPosition,
    globalVarsPosition,
    // Toggles & Handlers
    toggleSidebar,
    toggleNodeInfo, // Keep original toggle if used
    openNodeInfoPanel, // Add explicit open function
    closeNodeInfoPanel, // Keep explicit close function
    toggleGlobalVarsPanel,
    toggleChatPanel,
    handleToggleMenuOpen,
    handleToggleMenuClose,
    handleMenuOpen,
    handleMenuClose,
    handleOpenFlowSelect,
    handleCloseFlowSelect,
    // Remove explicit setter export unless absolutely necessary elsewhere
    // _setNodeInfoOpen: setNodeInfoOpen
  };
}; 