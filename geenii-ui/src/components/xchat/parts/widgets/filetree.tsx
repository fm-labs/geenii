import { FileIcon, FolderIcon } from 'lucide-react'
import { WidgetRendererProps } from '@/components/xchat/chat.types.ts'

type FileEntry = { path: string; size?: number | null; type?: 'file' | 'dir' }

type TreeNode = { name: string; size?: number | null; dir: boolean; children: Map<string, TreeNode> }

/** Build a tree from flat paths; parent folders are created as needed, entries with type "dir" or a trailing "/" are folders */
export const buildFileTree = (entries: FileEntry[]): TreeNode => {
  const root: TreeNode = { name: '', dir: true, children: new Map() }
  for (const entry of entries) {
    const parts = entry.path.split('/').filter(Boolean)
    let node = root
    parts.forEach((name, i) => {
      const isLast = i === parts.length - 1
      let child = node.children.get(name)
      if (!child) {
        child = { name, dir: !isLast, children: new Map() }
        node.children.set(name, child)
      }
      if (isLast) {
        child.dir = child.dir || entry.type === 'dir' || entry.path.endsWith('/')
        child.size = entry.size
      }
      node = child
    })
  }
  return root
}

const formatSize = (size?: number | null) => {
  if (size == null) return null
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / (1024 * 1024)).toFixed(1)} MB`
}

// folders first, then by name
const sorted = (node: TreeNode) => [...node.children.values()]
  .sort((a, b) => Number(b.dir) - Number(a.dir) || a.name.localeCompare(b.name))

const TreeItem = ({ node, depth, expand }: { node: TreeNode; depth: number; expand: number }) => {
  if (!node.dir) {
    return (
      <div className={'flex items-center gap-1.5 pl-5'}>
        <FileIcon className={'size-3.5 shrink-0 text-muted-foreground'} />
        <span className={'truncate'}>{node.name}</span>
        {node.size != null && <span className={'ml-auto pl-2 text-muted-foreground tabular-nums'}>{formatSize(node.size)}</span>}
      </div>
    )
  }
  return (
    <details open={depth < expand} className={'pl-5 [&>summary]:-ml-5'}>
      <summary className={'flex cursor-pointer select-none items-center gap-1.5'}>
        <FolderIcon className={'size-3.5 shrink-0 text-muted-foreground'} />
        <span className={'truncate'}>{node.name}/</span>
        <span className={'text-muted-foreground'}>{node.children.size}</span>
      </summary>
      {sorted(node).map((child) => <TreeItem key={child.name} node={child} depth={depth + 1} expand={expand} />)}
    </details>
  )
}

/** geenii.filetree — data: { root?, entries: { path, size?, type? }[], expand? = 2 }; paths are "/"-separated */
export const FileTreeWidget = ({ data }: WidgetRendererProps<{ root?: string; entries: FileEntry[]; expand?: number } | null>) => {
  const tree = buildFileTree(Array.isArray(data?.entries) ? data.entries : [])
  return (
    <div className={'rounded-md border overflow-hidden max-w-lg'}>
      {data?.root && <div className={'bg-muted px-3 py-1 text-xs text-muted-foreground truncate'}>{data.root}</div>}
      <div className={'font-mono text-xs p-2 overflow-auto max-h-96 [&_summary]:list-none [&_summary::-webkit-details-marker]:hidden'}>
        {sorted(tree).map((child) => <TreeItem key={child.name} node={child} depth={0} expand={data?.expand ?? 2} />)}
      </div>
    </div>
  )
}
