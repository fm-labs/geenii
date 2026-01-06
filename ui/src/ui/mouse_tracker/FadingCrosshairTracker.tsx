import { useState, useEffect } from 'react';

const FadingCrosshairTracker = ({ 
  fadeDelay = 2000, // Hide crosshair after 2 seconds of no movement
  fadeSpeed = 300   // Fade transition duration
}) => {
  const [mousePosition, setMousePosition] = useState({ x: 0, y: 0 });
  const [isVisible, setIsVisible] = useState(false);
  const [crosshairOpacity, setCrosshairOpacity] = useState(0.6);

  useEffect(() => {
    let fadeTimeout;

    const handleMouseMove = (event) => {
      setMousePosition({
        x: event.clientX,
        y: event.clientY
      });
      setIsVisible(true);
      setCrosshairOpacity(0.6);

      // Clear existing timeout
      clearTimeout(fadeTimeout);

      // Set new timeout to fade crosshair
      fadeTimeout = setTimeout(() => {
        setCrosshairOpacity(0.1);
      }, fadeDelay);
    };

    const handleMouseLeave = () => {
      setIsVisible(false);
      clearTimeout(fadeTimeout);
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseleave', handleMouseLeave);

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseleave', handleMouseLeave);
      clearTimeout(fadeTimeout);
    };
  }, [fadeDelay]);

  return (
    <>
      {/* Horizontal crosshair line */}
      {isVisible && (
        <div
          style={{
            position: 'fixed',
            left: 0,
            top: mousePosition.y - 1.5,
            width: '100vw',
            height: '3px',
            backgroundColor: `rgba(0, 150, 255, ${crosshairOpacity})`,
            pointerEvents: 'none',
            zIndex: 9998,
            transition: `opacity ${fadeSpeed}ms ease`
          }}
        />
      )}
      
      {/* Vertical crosshair line */}
      {isVisible && (
        <div
          style={{
            position: 'fixed',
            left: mousePosition.x - 1.5,
            top: 0,
            width: '3px',
            height: '100vh',
            backgroundColor: `rgba(0, 150, 255, ${crosshairOpacity})`,
            pointerEvents: 'none',
            zIndex: 9998,
            transition: `opacity ${fadeSpeed}ms ease`
          }}
        />
      )}

      {/* Mouse tracker */}
      {isVisible && (
        <div
          style={{
            position: 'fixed',
            left: mousePosition.x + 15,
            top: mousePosition.y - 25,
            backgroundColor: 'rgba(0, 0, 0, 0.8)',
            color: 'white',
            padding: '4px 8px',
            borderRadius: '4px',
            fontSize: '11px',
            pointerEvents: 'none',
            zIndex: 9999,
            opacity: crosshairOpacity + 0.3,
            transition: `opacity ${fadeSpeed}ms ease`
          }}
        >
          📍 {mousePosition.x}, {mousePosition.y}
        </div>
      )}
    </>
  );
};

export default FadingCrosshairTracker;
