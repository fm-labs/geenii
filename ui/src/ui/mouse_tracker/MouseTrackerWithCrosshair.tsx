import { useState, useEffect } from 'react';

const MouseTrackerWithCrosshair = () => {
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

    const handleMouseEnter = () => {
      setIsVisible(true);
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseleave', handleMouseLeave);
    document.addEventListener('mouseenter', handleMouseEnter);

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseleave', handleMouseLeave);
      document.removeEventListener('mouseenter', handleMouseEnter);
    };
  }, []);

  return (
    <div style={{ height: '100vh', width: '100%', position: 'relative', overflow: 'hidden' }}>
      <h1>Mouse Tracker with Crosshair</h1>
      <p>Move your mouse around to see the crosshair and tracker in action!</p>
      
      {/* Horizontal crosshair line */}
      {isVisible && (
        <div
          style={{
            position: 'fixed',
            left: 0,
            top: mousePosition.y - 1.5, // Center the 3px line on cursor
            width: '100vw',
            height: '3px',
            backgroundColor: 'rgba(255, 0, 0, 0.6)',
            pointerEvents: 'none',
            zIndex: 9998,
            transition: 'opacity 0.1s ease'
          }}
        />
      )}
      
      {/* Vertical crosshair line */}
      {isVisible && (
        <div
          style={{
            position: 'fixed',
            left: mousePosition.x - 1.5, // Center the 3px line on cursor
            top: 0,
            width: '3px',
            height: '100vh',
            backgroundColor: 'rgba(255, 0, 0, 0.6)',
            pointerEvents: 'none',
            zIndex: 9998,
            transition: 'opacity 0.1s ease'
          }}
        />
      )}

      {/* Mouse follower div */}
      {isVisible && (
        <div
          style={{
            position: 'fixed',
            left: mousePosition.x + 10,
            top: mousePosition.y + 10,
            backgroundColor: 'rgba(0, 0, 0, 0.8)',
            color: 'white',
            padding: '8px 12px',
            borderRadius: '6px',
            fontSize: '14px',
            pointerEvents: 'none',
            zIndex: 9999,
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

export default MouseTrackerWithCrosshair;
