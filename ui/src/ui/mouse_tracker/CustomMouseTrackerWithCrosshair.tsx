import { useState, useEffect } from 'react';

const CustomMouseTrackerWithCrosshair = ({ 
  text = "Following your cursor!", 
  offset = { x: 10, y: 10 },
  crosshairStyle = {},
  trackerStyle = {},
  showCrosshair = true,
  crosshairColor = 'rgba(255, 0, 0, 0.6)',
  crosshairWidth = 3
}) => {
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

  const defaultCrosshairStyle: any = {
    backgroundColor: crosshairColor,
    pointerEvents: 'none',
    zIndex: 9998,
    transition: 'opacity 0.1s ease',
    ...crosshairStyle
  };

  const defaultTrackerStyle: any = {
    position: 'fixed',
    left: mousePosition.x + offset.x,
    top: mousePosition.y + offset.y,
    backgroundColor: 'rgba(50, 50, 50, 0.9)',
    color: 'white',
    padding: '6px 10px',
    borderRadius: '4px',
    fontSize: '12px',
    fontFamily: 'Arial, sans-serif',
    pointerEvents: 'none',
    zIndex: 10000,
    userSelect: 'none',
    boxShadow: '0 2px 6px rgba(0, 0, 0, 0.2)',
    border: '1px solid rgba(255, 255, 255, 0.2)',
    ...trackerStyle
  };

  const crosshairHStyle: any = {
    position: 'fixed',
    left: 0,
    top: mousePosition.y - (crosshairWidth / 2),
    width: '100vw',
    height: `${crosshairWidth}px`,
    ...defaultCrosshairStyle
  }

  const crosshairVStyle: any = {
    position: 'fixed',
    left: mousePosition.x - (crosshairWidth / 2),
    top: 0,
    width: `${crosshairWidth}px`,
    height: '100vh',
    ...defaultCrosshairStyle
  }

  return (
    <>
      {/* Horizontal crosshair line */}
      {isVisible && showCrosshair && (
        <div
          style={crosshairHStyle}
        />
      )}
      
      {/* Vertical crosshair line */}
      {isVisible && showCrosshair && (
        <div
          style={crosshairVStyle}
        />
      )}

      {/* Mouse follower div */}
      {isVisible && (
        <div style={defaultTrackerStyle}>
          {text}
        </div>
      )}
    </>
  );
};

export default CustomMouseTrackerWithCrosshair;
