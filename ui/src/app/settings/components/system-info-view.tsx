import React from 'react'
import Header from '@/components/header.tsx'
import JsonView from '@/components/json-view.tsx'
import { XAI_API_URL } from '@/constants.ts'

const SystemInfoView = () => {

  const [data, setData] = React.useState<any>(null)

  const fetchInfo = async () => {
    try {
      const response = await fetch(XAI_API_URL + 'api/v1/info')
      const data = await response.json()
      console.log('System Info:', data)
      setData(data)
    } catch (error) {
      console.error('Error fetching system info:', error)
    }
  }

  React.useEffect(() => {
    fetchInfo()
  }, [])

  return (
    <div>
      {data ? <JsonView src={data} /> : <p>Loading system information...</p>}
    </div>
  )
}

export default SystemInfoView