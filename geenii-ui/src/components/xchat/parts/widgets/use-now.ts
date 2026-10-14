import React from 'react'

/** The current time, updated every second while `enabled` */
export const useNow = (enabled = true) => {
  const [now, setNow] = React.useState(() => new Date())
  React.useEffect(() => {
    if (!enabled) return
    const timer = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(timer)
  }, [enabled])
  return now
}
