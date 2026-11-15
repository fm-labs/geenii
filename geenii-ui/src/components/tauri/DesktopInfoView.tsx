import React from 'react'
import { cn } from 'cn'
import { useOptionalDesktop } from './DesktopStartupGate.tsx'
import { describeServiceStatus, ServiceStatus } from './desktop-runtime.ts'
import ServiceLogView from './ServiceLogView.tsx'
import ServiceControls from './ServiceControls.tsx'

const Section = ({ title, actions, children }: React.PropsWithChildren<{ title: string; actions?: React.ReactNode }>) => (
  <section className="min-w-0 space-y-3">
    <div>
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{title}</h3>
      <dl className="grid grid-cols-[max-content_minmax(0,1fr)] gap-x-4 gap-y-1 text-sm">{children}</dl>
    </div>
    {actions}
  </section>
)

const Row = ({ label, value, mono }: { label: string; value: React.ReactNode; mono?: boolean }) =>
  value === null || value === undefined || value === '' ? null : (
    <>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className={cn('break-words', mono && 'select-all font-mono text-xs leading-5')}>{value}</dd>
    </>
  )

const StatusValue = ({ status, service }: { status: ServiceStatus | null; service: 'server' | 'daemon' }) => {
  const { label, dot } = describeServiceStatus(status, service)
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={cn('size-2 shrink-0 rounded-full', dot)} />
      {label}
    </span>
  )
}

/** Desktop shell, managed services and backend details; live, from the desktop context. */
const DesktopInfoView = () => {
  const desktop = useOptionalDesktop()
  if (!desktop) return null

  const info = desktop.tauri.info
  const backend = desktop.backend.info
  const providers = backend?.providers ?? []

  return (
    <div className="space-y-6">
      <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-4">
        <Section title="Desktop app">
          <Row label="App" value={info && `${info.appName} ${info.appVersion}`} />
          <Row label="Tauri" value={info?.tauriVersion} />
          <Row label="Platform" value={info && `${info.os} / ${info.arch}`} />
        </Section>

        <Section title="Server" actions={<ServiceControls service="server" status={desktop.server.status} />}>
          <Row label="Status" value={<StatusValue status={desktop.server.status} service="server" />} />
          <Row label="Release" value={info?.serverVersion} />
          <Row label="URL" value={info?.serverUrl} mono />
          <Row label="Binary" value={info?.serverBinOverride} mono />
          <Row label="Log" value={info?.serverLog} mono />
        </Section>

        <Section title="Daemon" actions={<ServiceControls service="daemon" status={desktop.daemon.status} />}>
          <Row label="Status" value={<StatusValue status={desktop.daemon.status} service="daemon" />} />
          <Row label="Socket" value={info?.daemonSocket} mono />
          <Row label="Log" value={info?.daemonLog} mono />
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
      <ServiceLogView />
    </div>
  )
}

export default DesktopInfoView
