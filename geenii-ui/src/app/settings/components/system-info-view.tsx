import React from 'react'
import Header from '@/components/header.tsx'
import JsonView from '@/components/json-view.tsx'
import { useApi } from '@/context/api-context.tsx'

const SystemInfoView = () => {
  const { api } = useApi()
  const [data, setData] = React.useState<any>(null)

  const fetchInfo = async () => {
    try {
      const data = await api.getInfo()
      console.log('System Info:', data)
      setData(data)
    } catch (error) {
      console.error('Error fetching system info:', error)
    }
  }

  React.useEffect(() => {
    fetchInfo()
  }, [api])

  return (
    <div>
      {data ? <JsonView src={data} /> : <p>Loading system information...</p>}
    </div>
  )
}

export default SystemInfoView