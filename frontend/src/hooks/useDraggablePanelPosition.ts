import { useState, useEffect, useCallback, useRef } from 'react';
import { debounce } from 'lodash'; // Import debounce

interface Position {
  x: number;
  y: number;
}

interface UseDraggablePanelPositionProps {
  initialPosition: Position;
  panelWidth: number | string; // Needed for boundary checks
  panelHeight: number | string; // Needed for boundary checks
  topNavHeight?: number; // Height of any fixed top navigation
  buffer?: number; // Pixels from edge
  minVisibleWidth?: number; // Minimum pixels of the panel to keep visible on left/right edges
  minVisibleHeight?: number; // Minimum pixels of the panel to keep visible on top/bottom edges
  boundsSelector?: string | { left?: number, top?: number, right?: number, bottom?: number }; // Optional bounds
}

interface UseDraggablePanelPositionOutput {
  position: Position;
  setPosition: React.Dispatch<React.SetStateAction<Position>>;
  bounds: string | { left?: number, top?: number, right?: number, bottom?: number } | undefined;
  handleDragStart: () => void;
  handleDragStop: () => void;
}

export const useDraggablePanelPosition = ({
  initialPosition,
  panelWidth: initialPanelWidth, // Rename props to avoid conflict in handleResize
  panelHeight: initialPanelHeight,
  topNavHeight = 48, // Default top nav height
  buffer = 20, // Default buffer
  minVisibleWidth = 120, // Default minimum visible width
  minVisibleHeight = 50, // Default minimum visible height (e.g., for header)
  boundsSelector = 'body' // Default bounds to body, can be overridden
}: UseDraggablePanelPositionProps): UseDraggablePanelPositionOutput => {
  const [position, setPosition] = useState<Position>(initialPosition);
  const [bounds, setBounds] = useState<string | { left?: number, top?: number, right?: number, bottom?: number } | undefined>(boundsSelector);

  // --- Define helper function FIRST ---
  const parseDimension = (dim: number | string): number => {
    // Ensure NaN is handled, return 0 or a default?
    const parsed = typeof dim === 'string' ? parseInt(dim, 10) : dim;
    return isNaN(parsed) ? 0 : parsed; 
  };

  // --- Initialize refs AFTER defining helper ---
  const panelWidthRef = useRef(parseDimension(initialPanelWidth));
  const panelHeightRef = useRef(parseDimension(initialPanelHeight));

  // Update refs when props change
  useEffect(() => {
    panelWidthRef.current = parseDimension(initialPanelWidth);
  }, [initialPanelWidth]);
  useEffect(() => {
    panelHeightRef.current = parseDimension(initialPanelHeight);
  }, [initialPanelHeight]);

  useEffect(() => {
    // Update position if initial position changes (e.g., on panel open)
    setPosition(initialPosition);
  }, [initialPosition]);

  // --- Resize Effect with Debounce ---
  useEffect(() => {
    if (typeof window === 'undefined') return;

    const calculateAndSetPosition = () => {
      const newWindowWidth = window.innerWidth;
      const newWindowHeight = window.innerHeight;
      // Read dimensions from refs inside the handler
      const currentPanelWidth = panelWidthRef.current;
      const currentPanelHeight = panelHeightRef.current;

      setPosition(prevPos => {
        let newX = prevPos.x;
        let newY = prevPos.y;
        let changed = false;

        // Calculate boundaries using ref values
        const maxX = newWindowWidth - buffer - minVisibleWidth;
        const maxY = newWindowHeight - buffer - minVisibleHeight;
        const minX = buffer - currentPanelWidth + minVisibleWidth;
        const minY = topNavHeight + buffer;

        // Check and correct X position
        if (prevPos.x < minX) { newX = minX; changed = true; }
        if (prevPos.x > maxX) { newX = maxX; changed = true; }
        // Check and correct Y position
        if (prevPos.y < minY) { newY = minY; changed = true; }
        if (prevPos.y > maxY) { newY = maxY; changed = true; }

        if (changed) {
          console.log(`Debounced Resize: Correcting position from ${JSON.stringify(prevPos)} to ${JSON.stringify({x: newX, y: newY})}`);
        }
        return changed ? { x: newX, y: newY } : prevPos;
      });
    };

    // Create debounced version of the position calculation
    const debouncedHandleResize = debounce(calculateAndSetPosition, 200); // Debounce for 200ms

    // Initial calculation (no need to debounce)
    calculateAndSetPosition(); 

    // Add debounced listener
    window.addEventListener('resize', debouncedHandleResize);

    // Cleanup: remove listener and cancel any pending debounce calls
    return () => {
      window.removeEventListener('resize', debouncedHandleResize);
      debouncedHandleResize.cancel(); // Cancel lodash debounce
    };
  }, [topNavHeight, buffer, minVisibleWidth, minVisibleHeight]);

  useEffect(() => {
    // For now, just set the initial bounds provided
    setBounds(boundsSelector);
  }, [boundsSelector]);

  // Placeholder drag handlers (can add logic later)
  const handleDragStart = useCallback(() => {
    // console.log('Drag started');
    // Potentially set a flag or change cursor
  }, []);

  const handleDragStop = useCallback(() => {
    // console.log('Drag stopped at:', position);
    // Potentially snap to grid or save position
  }, []); // Add position dependency if logic uses it

  return {
    position,
    setPosition,
    bounds,
    handleDragStart,
    handleDragStop,
  };
}; 