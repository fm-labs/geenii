import React from 'react'
import { XAI_API_URL } from '@/constants.ts'
import Header from '@/components/header.tsx'
import { Badge } from '@/components/ui/badge.tsx'
import { Button } from '@/components/ui/button.tsx'
import { useNavigate } from '@/app-router.tsx'

type AppSpecModel = {
  name: string;
  description?: string;
}

const AppCard = ({ app }: { app: AppSpecModel }) => {
  const navigate = useNavigate()

  return (
    <div className="app-card rounded-lg border p-4 flex flex-row justify-between items-center">
      <div>
        <h3 className={"font-bold"}>{app.name}</h3>
        <p>{app?.description}</p>
      </div>
      <div className={"space-x-2"}>
        <Button variant={"secondary"}>Configure</Button>
        <Button variant={"default"} onClick={() => navigate(`/apps/${app.name}`)}>Open</Button>
      </div>
    </div>
  )
}


const AppsSettings = () => {

  const [apps, setApps] = React.useState<AppSpecModel[]>([])

  const fetchApps = async () => {
    const response = await fetch(XAI_API_URL + 'apps/', {
      headers: {
        "Content-Type": "application/json",
      }
    })
    const data = await response.json()
    console.log("Fetched apps", data)
    return data?.apps || []
  }

  React.useEffect(() => {
    fetchApps().then(setApps)
  }, [])

  return (
    <div>
      <div className={"flex flex-col gap-y-4"}>
        {apps.map((app) => (
          <AppCard key={app.name} app={app} />
        ))}
      </div>
    </div>
  )
}

export default AppsSettings