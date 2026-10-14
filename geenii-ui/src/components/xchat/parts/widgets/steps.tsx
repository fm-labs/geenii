import { CheckIcon, CircleIcon, LoaderIcon, MinusIcon, XIcon } from 'lucide-react'
import { WidgetRendererProps } from '@/components/xchat/chat.types.ts'

type StepStatus = 'pending' | 'running' | 'done' | 'failed' | 'skipped'

type StepsData = { title?: string; steps: { text: string; status?: StepStatus; detail?: string | null }[] }

const STATUS_ICONS: Record<StepStatus, { icon: typeof CheckIcon; className: string }> = {
  pending: { icon: CircleIcon, className: 'text-muted-foreground' },
  running: { icon: LoaderIcon, className: 'animate-spin text-primary' },
  done: { icon: CheckIcon, className: 'text-green-600' },
  failed: { icon: XIcon, className: 'text-destructive' },
  skipped: { icon: MinusIcon, className: 'text-muted-foreground' },
}

/** geenii.steps — data: { title?, steps: { text, status? = pending, detail? }[] }; status: pending, running, done, failed, skipped */
export const StepsWidget = ({ data }: WidgetRendererProps<StepsData | null>) => {
  const steps = Array.isArray(data?.steps) ? data.steps : []
  return (
    <div className={'rounded-md border p-3 max-w-lg'}>
      {data?.title && <div className={'font-medium mb-2'}>{data.title}</div>}
      <ol className={'space-y-1.5 text-sm'}>
        {steps.map((step, i) => {
          const status = STATUS_ICONS[step.status ?? 'pending'] ?? STATUS_ICONS.pending
          const Icon = status.icon
          return (
            <li key={i} className={'flex items-start gap-2'} data-status={step.status ?? 'pending'}>
              <Icon className={`size-4 shrink-0 mt-0.5 ${status.className}`} />
              <div className={'min-w-0'}>
                <div className={step.status === 'skipped' ? 'line-through text-muted-foreground' : ''}>{step.text}</div>
                {step.detail && <div className={'text-xs text-muted-foreground'}>{step.detail}</div>}
              </div>
            </li>
          )
        })}
      </ol>
    </div>
  )
}
