import React from 'react'
import { XAI_API_URL } from '@/constants.ts'
import Header from '@/components/header.tsx'
import { Badge } from '@/components/ui/badge.tsx'
import { Button } from '@/components/ui/button.tsx'
import { useNavigate } from '@/app-router.tsx'

type AppSpecModel = {
  name: string;
  path: string;
  manifest?: AppManifest;
  trusted?: boolean;
}

type AppManifest = {
  name: string;
  title?: string;
  description?: string;
  author?: string;
  version?: string;
  main?: string;
  files?: string[];
  permissions?: string[];
}

const AppsSettingCard = ({ app }: { app: AppSpecModel }) => {
  const navigate = useNavigate()

  return (
    <div className="app-card rounded-lg border p-4 flex flex-row justify-between items-center">
      <div>
        <h3 className={"font-bold"}>{app?.manifest?.title || app.name}</h3>
        <p className={"text-muted-foreground"}>{app?.manifest?.description || "No description available"}</p>
      </div>
      <div className={"space-x-2"}>
        <Button size={"sm"} variant={"secondary"}>Configure</Button>
        <Button size={"sm"} variant={"default"} onClick={() => navigate(`/apps/${app.name}`)}>Open</Button>
      </div>
    </div>
  )
}


const AppsSettings = () => {

  const [apps, setApps] = React.useState<AppSpecModel[]>([])

  const fetchApps = async () => {
    const response = await fetch(XAI_API_URL + 'api/v1/apps/', {
      headers: {
        "Content-Type": "application/json",
      }
    })
    const data = await response.json()
    console.log("Fetched apps", data)
    return data?.apps || []
  }

  const sortedApps = React.useMemo(() => {
    if (!apps) return []
    return [...apps].sort((a, b) => a.name.localeCompare(b.name))
  }, [apps])

  React.useEffect(() => {
    fetchApps().then(setApps)
  }, [])

  return (
    <div>
      <div className={"flex flex-col gap-y-4"}>
        {sortedApps.map((app) => (
          <AppsSettingCard key={app.name} app={app} />
        ))}
      </div>
    </div>
  )
}

export default AppsSettings