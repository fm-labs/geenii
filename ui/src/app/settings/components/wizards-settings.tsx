import React from 'react'
import { XAI_API_URL } from '@/constants.ts'
import Header from '@/components/header.tsx'
import { Badge } from '@/components/ui/badge.tsx'

type WizardModel = {
  id: string;
  name: string;
  description: string;
  model: string;
  tools: string[];
  imageUrl?: string;
}

const WizardCard = ({ wizard }: { wizard: WizardModel }) => {
  return (
    <div className="wizard-card py-4">
      <h3 className={"font-bold"}>{wizard.name}</h3>
      <p>{wizard.description}</p>
      <p><strong>Model:</strong> {wizard.model}</p>
      <p><strong>Tools:</strong> {wizard.tools.map((tool) => <Badge>{tool}</Badge>)}</p>
      <hr />
    </div>
  )
}


const WizardsSettings = () => {

  const [wizards, setWizards] = React.useState<WizardModel[]>([])

  const fetchWizards = async () => {
    const response = await fetch(XAI_API_URL + 'wizards/', {
      headers: {
        "Content-Type": "application/json",
      }
    })
    const data = await response.json()
    console.log("Fetched wizards", data)
    return data?.wizards || []
  }

  React.useEffect(() => {
    fetchWizards().then(setWizards)
  }, [])

  return (
    <div>
      <Header title={'Wizard Settings'}></Header>
      <div>
        {wizards.map((wizard) => (
          <WizardCard key={wizard.id} wizard={wizard} />
        ))}
      </div>
    </div>
  )
}

export default WizardsSettings