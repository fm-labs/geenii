import React from 'react'
import { FileIcon, ExternalLinkIcon } from 'lucide-react'
import { OutputDataMarkdown } from '@/components/output-data-markdown.tsx'
import {
  AudioContent,
  ContentPartRendererProps,
  EmbedContent,
  FileContent,
  ImageContent,
  JsonContent,
  TextContent,
} from '@/components/xchat/chat.types.ts'

// tailwind preflight resets markdown element styles; restore the basics for rendered markdown
export const markdownClass = [
  'break-words',
  '[&_p]:my-2 [&_p:first-child]:mt-0 [&_p:last-child]:mb-0',
  '[&_ul]:list-disc [&_ol]:list-decimal [&_ul]:pl-6 [&_ol]:pl-6 [&_ul]:my-2 [&_ol]:my-2',
  '[&_h1]:text-xl [&_h2]:text-lg [&_h3]:text-base [&_h1,&_h2,&_h3]:font-semibold [&_h1,&_h2,&_h3]:mt-3 [&_h1,&_h2,&_h3]:mb-1',
  '[&_a]:underline [&_blockquote]:border-l-2 [&_blockquote]:pl-3 [&_blockquote]:text-muted-foreground',
  '[&_:not(pre)>code]:rounded [&_:not(pre)>code]:bg-muted [&_:not(pre)>code]:px-1 [&_:not(pre)>code]:text-[0.9em]',
  '[&_pre]:my-2 [&_pre]:overflow-x-auto [&_table]:my-2 [&_td,&_th]:border [&_td,&_th]:px-2 [&_th]:text-left',
  '[&_.contains-task-list]:list-none [&_.contains-task-list]:pl-1 [&_.task-list-item_input]:mr-1.5',
].join(' ')

export const TextPart = ({ part, message }: ContentPartRendererProps<TextContent>) => {
  const text = part.text?.trim() ?? ''
  // user input is shown as typed; model output is markdown
  if (message.message.role === 'user') {
    return <div className={'whitespace-pre-wrap break-words'}>{text}</div>
  }
  return <div className={markdownClass}><OutputDataMarkdown data={text} /></div>
}

const imageSrc = (part: ImageContent): string | null => {
  if (part.url) return part.url
  if (part.base64) return part.base64.startsWith('data:') ? part.base64 : `data:image/png;base64,${part.base64}`
  return null
}

export const ImagePart = ({ part }: ContentPartRendererProps<ImageContent>) => {
  const src = imageSrc(part)
  if (!src) return <UnknownPart part={part} />
  return <img src={src} alt={part.alt ?? 'Image'} className={'max-w-full h-auto rounded-md'} />
}

export const AudioPart = ({ part }: ContentPartRendererProps<AudioContent>) => (
  <audio controls src={part.url} className={'w-full max-w-md'} />
)

const formatSize = (size?: number | null) => {
  if (size == null) return null
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / (1024 * 1024)).toFixed(1)} MB`
}

export const FilePart = ({ part }: ContentPartRendererProps<FileContent>) => (
  <a href={part.url} target={'_blank'} rel={'noreferrer'}
     className={'inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm hover:bg-accent'}>
    <FileIcon className={'size-4 shrink-0'} />
    <span className={'truncate'}>{part.filename}</span>
    {part.size != null && <span className={'text-muted-foreground'}>{formatSize(part.size)}</span>}
  </a>
)

export const EmbedPart = ({ part }: ContentPartRendererProps<EmbedContent>) => (
  <div className={'flex gap-3 rounded-md border p-3 max-w-lg'}>
    {part.thumbnail_url && <img src={part.thumbnail_url} alt={''} className={'size-16 rounded object-cover'} />}
    <div className={'min-w-0'}>
      <div className={'font-medium truncate'}>{part.title || part.url || 'Embed'}</div>
      {part.description && <div className={'text-sm text-muted-foreground line-clamp-2'}>{part.description}</div>}
      {part.url && (
        <a href={part.url} target={'_blank'} rel={'noreferrer'}
           className={'inline-flex items-center gap-1 text-sm underline'}>
          Open <ExternalLinkIcon className={'size-3'} />
        </a>
      )}
      {part.video_url && <video controls src={part.video_url} className={'mt-2 max-w-full'} />}
    </div>
  </div>
)

export const JsonBlock = ({ data }: { data: unknown }) => (
  <pre className={'text-xs bg-muted rounded-md p-2 overflow-x-auto max-h-80'}>
    {typeof data === 'string' ? data : JSON.stringify(data, null, 2)}
  </pre>
)

export const JsonPart = ({ part }: ContentPartRendererProps<JsonContent>) => <JsonBlock data={part.data} />

export const UnknownPart = ({ part }: { part: { type: string } }) => (
  <div className={'text-sm text-muted-foreground'}>
    <div className={'italic'}>[{part.type} content]</div>
    <JsonBlock data={part} />
  </div>
)
