import React, { PropsWithChildren } from 'react'
import { useNavigate } from '@/app-router.tsx'

interface LinkProps {
  to?: string
}

const Link = ({ to, children }: PropsWithChildren<LinkProps>) => {
  const navigate = useNavigate()
  return (
    <a href={'#' + to } onClick={() => navigate(to)}>
      {children}
    </a>
  )
}

export default Link