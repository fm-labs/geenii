import { WidgetRendererProps } from '@/components/xchat/chat.types.ts'

type ListItem = string | { text: string; description?: string | null }

/** geenii.list — data: { items: (string | { text, description? })[], ordered?: boolean } */
export const ListWidget = ({ data }: WidgetRendererProps<{ items: ListItem[]; ordered?: boolean } | null>) => {
  const items = Array.isArray(data?.items) ? data.items : []
  const List = data?.ordered ? 'ol' : 'ul'
  return (
    <List className={`${data?.ordered ? 'list-decimal' : 'list-disc'} pl-6 space-y-1`}>
      {items.map((item, i) => (typeof item === 'string'
        ? <li key={i}>{item}</li>
        : (
          <li key={i}>
            <span>{item.text}</span>
            {item.description && <div className={'text-sm text-muted-foreground'}>{item.description}</div>}
          </li>
        )))}
    </List>
  )
}
