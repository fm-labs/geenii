import React from 'react'
import { cn } from 'cn'
import { useOptionalDesktop } from './DesktopStartupGate.tsx'
import { describeServerStatus } from './desktop-runtime.ts'
import ServerLogView from './ServerLogView.tsx'

const Section = ({ title, children }: React.PropsWithChildren<{ title: string }>) => (
  <section className="min-w-0">
    <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{title}</h3>
    <dl className="grid grid-cols-[max-content_minmax(0,1fr)] gap-x-4 gap-y-1 text-sm">{children}</dl>
  </section>
)

const Row = ({ label, value, mono }: { label: string; value: React.ReactNode; mono?: boolean }) =>
  value === null || value === undefined || value === '' ? null : (
    <>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className={cn('break-words', mono && 'select-all font-mono text-xs leading-5')}>{value}</dd>
    </>
  )

/** Desktop shell, managed server and backend details; live, from the desktop context. */
const DesktopInfoView = () => {
  const desktop = useOptionalDesktop()
  if (!desktop) return null

  const info = desktop.tauri.info
  const status = desktop.server.status
  const backend = desktop.backend.info
  const { label, dot } = describeServerStatus(status)
  const providers = backend?.providers ?? []

  return (
    <div className="space-y-6">
      <div className="grid gap-6 md:grid-cols-3">
        <Section title="Desktop app">
          <Row label="App" value={info && `${info.appName} ${info.appVersion}`} />
          <Row label="Tauri" value={info?.tauriVersion} />
          <Row label="Platform" value={info && `${info.os} / ${info.arch}`} />
        </Section>

        <Section title="Server">
          <Row
            label="Status"
            value={
              <span className="inline-flex items-center gap-1.5">
                <span className={cn('size-2 shrink-0 rounded-full', dot)} />
                {label}
              </span>
            }
          />
          <Row label="Release" value={info?.serverVersion} />
          <Row label="URL" value={info?.serverUrl} mono />
          <Row label="Binary" value={info?.serverBinOverride} mono />
          <Row label="Log" value={info?.serverLog} mono />
        </Section>

        <Section title="Backend">
          {backend ? (
            <>
              <Row label="Version" value={backend.app?.version} />
              <Row label="Working dir" value={backend.app?.cwd} mono />
              <Row
                label="Providers"
                value={
                  providers.length > 0
                    ? providers.map((p) => (p.configured ? p.name : `${p.name} (not configured)`)).join(', ')
                    : 'none'
                }
              />
            </>
          ) : (
            <Row label="Status" value={desktop.backend.error ?? 'not connected'} />
          )}
        </Section>
      </div>
      <ServerLogView />
    </div>
  )
}

export default DesktopInfoView
