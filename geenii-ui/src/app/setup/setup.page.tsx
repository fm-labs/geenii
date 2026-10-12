import React from 'react'
import Header from '@/components/header.tsx'

const SetupPage = () => {
  return (
    <div>
      <Header title="Setup" />
      <div className="p-4">
        <h2 className="text-xl font-bold mb-4">Welcome to the Setup Page</h2>
        <p className="text-gray-600">This is where you can configure your application settings and preferences.</p>
        {/* Add your setup form or configuration options here */}
      </div>
    </div>
  )
}

export default SetupPage