import React from 'react'

const FlowgraphBackground = () => {

  const dotSize = 1
  const spacing = 40
  const dotColor = '#94ec5d'
  const backgroundStyle: React.CSSProperties = {
    position: 'absolute',
    top: 0,
    left: 0,
    width: '100%',
    height: '100%',
    backgroundImage: `radial-gradient(circle at center, ${dotColor} ${dotSize}px, transparent 1px),
                      radial-gradient(circle at center, ${dotColor} ${dotSize}px, transparent 1px)`,
    backgroundSize: `${spacing}px ${spacing}px`,
    backgroundPosition: `0 0, ${spacing/2}px ${spacing/2}px`,
    zIndex: 0,
  }

  return (
    <div className={"flowgraph-background"} style={backgroundStyle}></div>
  )
}

export default FlowgraphBackground