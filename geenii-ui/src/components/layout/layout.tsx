import React, { PropsWithChildren } from 'react'
import Headerbar from '@/components/layout/headerbar.tsx'

const Layout = (props: PropsWithChildren) => {

  return (
    <div>
      <Headerbar />
      <div>
        {props.children}
      </div>
    </div>
  )
}

export default Layout
