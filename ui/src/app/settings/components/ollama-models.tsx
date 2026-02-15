import React from 'react'

//import modelData from '../data/ollama_models.json'
import { Input } from '@/components/ui/input.tsx'
import { DownloadIcon } from 'lucide-react'
import { Button } from '@/components/ui/button.tsx'
import { Badge } from '@/components/ui/badge.tsx'

/**
 * OllamaModels Component
 * Renders a list of Ollama models.
 *
 * Example Model data:
 *   {
 *     "name": "nemotron-3-nano",
 *     "description": "Nemotron 3 Nano - A new Standard for Efficient, Open, and Intelligent Agentic Models",
 *     "pulls": "81.3K",
 *     "tag_count": "6",
 *     "sizes": [
 *       "30b"
 *     ],
 *     "capabilities": [
 *       "tools",
 *       "thinking"
 *     ],
 *     "updated": "2025-12-16 06:27:00",
 *     "tags": [
 *       {
 *         "name": "nemotron-3-nano:latest",
 *         "size": "24GB",
 *         "context_window": "1M",
 *         "input_type": "Text"
 *       }
 *     ]
 *  }
 *
 * @returns {JSX.Element} The OllamaModels component.
 * @constructor
 */
const OllamaModels = () => {
  const [searchTerm, setSearchTerm] = React.useState('')
  const [activeModel, setActiveModel] = React.useState<any>(null)

  const [modelData, setModelData] = React.useState<any[]>([])

  const modelHasCloudTag = (model: any) => {
    return model.tags.some((tag: any) => tag.name.toLowerCase().includes('cloud'))
  }

  const filteredModels = React.useMemo(() => {
    if (!modelData) return []
    if (searchTerm.trim() === '') return modelData

    return modelData.filter((model) =>
      model.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      model.description.toLowerCase().includes(searchTerm.toLowerCase()) ||
      model.tags.some((tag) => tag.name.toLowerCase().includes(searchTerm.toLowerCase()))
    )
  }, [searchTerm])

  return (
    <div>
      <div className={"mb-4"}>
        <Input placeholder={"Filter models ..."} onChange={(e) => setSearchTerm(e.target.value)} value={searchTerm} />
      </div>
      <div>
        {filteredModels && filteredModels.map((model) => (
          <div key={model.name} className={"border p-3 mb-3 hover:bg-accent hover:shadow"} onClick={() => setActiveModel(model)}>
            <div className={"flex justify-between mb-2"}>
              <h3 className={"font-bold"}>
                {model.name}
                {model.name.endsWith("-cloud") || modelHasCloudTag(model) && (
                  <Badge className={"ml-2"} variant={"secondary"}>cloud</Badge>
                )}
              </h3>
              <div>
                {/*<Button title={"Download Model"} variant={"outline"} size={"sm"}>
                  <DownloadIcon />
                </Button>*/}
              </div>
            </div>
            <p className={"text-muted-foreground mb-2"}>{model.description}</p>
            <div className={"flex flex-row space-x-2 text-sm"}>
              <div><strong>Pulls:</strong> {model.pulls}</div>
              <div><strong>Tags:</strong> {model.tag_count}</div>
              <div><strong>Sizes:</strong> {model.sizes.join(', ')}</div>
              <div><strong>Capabilities:</strong> {model.capabilities.join(', ')}</div>
              <div><strong>Last Updated:</strong> {model.updated}</div>
            </div>
            <div className={activeModel && activeModel.name === model.name ? "mt-4" : "hidden"}>
              <h4>Tags:</h4>
              <table className={"w-full mb-4"}>
                <tr>
                  <th>Name</th>
                  <th className={"ps-4 text-right"}>Size</th>
                  <th className={"ps-4 text-right"}>Context Window</th>
                  <th className={"ps-4 text-right"}>Input Type</th>
                  <th className={"ps-4 text-right"}>Install</th>
                </tr>
                {model.tags.map((tag) => (
                  <tr key={tag.name}>
                    <td>{tag.name}</td>
                    <td className={"ps-4 text-right"}>{tag.size}</td>
                    <td className={"ps-4 text-right"}>{tag.context_window}</td>
                    <td className={"ps-4 text-right"}>{tag.input_type}</td>
                    <td className={"ps-4 text-right"}>
                      {!tag.name.endsWith("-cloud") ? <Button title={"Download Model"} variant={"ghost"} size={"sm"}>
                        <DownloadIcon />
                      </Button> : ''}
                    </td>
                  </tr>
                ))}
              </table>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default OllamaModels