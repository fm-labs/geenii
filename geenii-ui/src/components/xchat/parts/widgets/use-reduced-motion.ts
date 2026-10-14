import React from 'react'

const query = () => window.matchMedia?.('(prefers-reduced-motion: reduce)')

/** True if the user asked the OS for reduced motion; animated widgets then show their end state */
export const useReducedMotion = () => {
  const [reduced, setReduced] = React.useState(() => query()?.matches ?? false)
  React.useEffect(() => {
    const mq = query()
    if (!mq) return
    const onChange = () => setReduced(mq.matches)
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])
  return reduced
}
