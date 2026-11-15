import React from 'react'
import { cn } from 'cn'

/** 24px square icon button used by the Tauri panel items, so their icons line up. */
const PanelIconButton = (
  props: React.PropsWithChildren<{ title: string; disabled?: boolean; className?: string; onClick: () => void }>,
) => (
  <button
    type="button"
    title={props.title}
    aria-label={props.title}
    disabled={props.disabled}
    onClick={props.onClick}
    className={cn(
      'inline-flex size-6 shrink-0 cursor-pointer items-center justify-center rounded hover:bg-accent disabled:pointer-events-none disabled:opacity-40',
      props.className,
    )}
  >
    {props.children}
  </button>
)

export default PanelIconButton
