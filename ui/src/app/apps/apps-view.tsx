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

const AppViewCard = ({ app }: { app: AppSpecModel }) => {
  const navigate = useNavigate()

  return (
    <div className="app-card rounded-lg border p-4 flex flex-row justify-between items-center">
      <div>
        <h3 className={"font-bold"}>{app.name}</h3>
        <p>{app?.description}</p>
      </div>
      <div className={"space-x-2"}>
        <Button variant={"default"} onClick={() => navigate(`/apps/${app.name}`)}>Open</Button>
      </div>
    </div>
  )
}


const AppsView = () => {

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
    return [...apps].sort((a, b) => a.name.localeCompare(b.name))
  }, [apps])

  React.useEffect(() => {
    fetchApps().then(setApps)
  }, [])

  return (
    <div>
      <div className={"grid sm:grid-cols-1 lg:grid-cols-3 gap-4"}>
        {sortedApps.map((app) => (
          <AppViewCard key={app.name} app={app} />
        ))}
      </div>
    </div>
  )
}

export default AppsView