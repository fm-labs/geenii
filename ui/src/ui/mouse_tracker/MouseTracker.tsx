import { useState, useEffect } from 'react';

const MouseTracker = () => {
  const [mousePosition, setMousePosition] = useState({ x: 0, y: 0 });
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    const handleMouseMove = (event) => {
      setMousePosition({
        x: event.clientX,
        y: event.clientY
      });
      setIsVisible(true);
    };

    const handleMouseLeave = () => {
      setIsVisible(false);
    };

    // Add event listeners
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseleave', handleMouseLeave);

    // Cleanup event listeners on component unmount
    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseleave', handleMouseLeave);
    };
  }, []);

  return (
    <div style={{ height: '100vh', width: '100%', position: 'relative' }}>
      <h1>Mouse Position Tracker</h1>
      <p>Move your mouse around to see the tracker in action!</p>
      
      {/* Mouse follower div */}
      {isVisible && (
        <div
          style={{
            position: 'fixed',
            left: mousePosition.x + 10, // Offset to avoid cursor overlap
            top: mousePosition.y + 10,
            backgroundColor: 'rgba(0, 0, 0, 0.8)',
            color: 'white',
            padding: '8px 12px',
            borderRadius: '6px',
            fontSize: '14px',
            pointerEvents: 'none', // Prevent interference with mouse events
            zIndex: 9999,
            transform: 'translate(0, 0)', // Smooth positioning
            transition: 'opacity 0.2s ease',
            boxShadow: '0 2px 8px rgba(0, 0, 0, 0.3)',
            whiteSpace: 'nowrap'
          }}
        >
          X: {mousePosition.x}, Y: {mousePosition.y}
        </div>
      )}
    </div>
  );
};

export default MouseTracker;
