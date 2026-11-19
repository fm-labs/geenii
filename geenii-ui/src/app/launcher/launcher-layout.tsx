import React, { PropsWithChildren } from 'react'

const LauncherLayout = (props: PropsWithChildren<{}>) => {

  return (
    <>
        {props.children}
    </>
  )
}

export default LauncherLayout
