import React from 'react'
import Form from '@rjsf/shadcn'
import validator from '@rjsf/validator-ajv8'
import JsonView from '@/components/json-view.tsx'
import { RJSFSchema } from '@rjsf/utils'

const DockerMcpServerConfigBuilder = ({ serverName, serverDef }: { serverName: string, serverDef: any }) => {

  const [formData, setFormData] = React.useState<any | null>(null)
  //const [result, setResult] = React.useState<any | null>(null);

  const result = React.useMemo(() => {
    if (!serverDef) {
      console.error('No server selected')
      return
    }

    // create new mcp_server inventory item
    let mcpType
    let properties: any = {}
    if (serverDef.type === 'server') {
      mcpType = 'stdio'
      properties['command'] = 'docker'
      properties['args'] = ['run', '--rm', '-i', serverDef.image]
    } else if (serverDef.type === 'remote') {
      mcpType = 'http'
      properties['url'] = serverDef.remote.url
    }

    const config = serverDef?.config && Array.isArray(serverDef?.config)
      ? serverDef?.config[0] || {} : {}

    const envVars = {}
    if (serverDef?.env && Array.isArray(serverDef.env)) {
      serverDef.env.forEach((envVar: any) => {
        let value = envVar.value || ''
        if (value.startsWith("{{") && value.endsWith("}}")) {
          const varName = value.substring(2, value.length - 2).trim()
          if (formData && config) {
            const formLookupKey = varName.substring(config.name.length + 1) // remove config prefix
            const formValue = formData ? formData[formLookupKey] : undefined
            value = formValue !== undefined ? formValue : value
            console.log(`Resolving env var ${envVar.name}: found form value for ${formLookupKey}:`, formValue)
          }
        }
        envVars[envVar.name] = value || ""
      })
    }

    serverDef?.secrets?.forEach((secretVar: any) => {
      const formLookupKey = 'secret__' + secretVar.name
      const formValue = formData ? formData[formLookupKey] : undefined
      console.log(`Resolving secret var ${secretVar.name}: looking for form value with key ${formLookupKey}:`, formValue)
      const value = formValue !== undefined ? formValue : `{{secret__${secretVar.name}}}`
      console.log(`Resolving secret var ${secretVar.name}: found form value for ${formLookupKey}:`, formValue)
      envVars[secretVar.env] = value
    })
    properties['environment'] = envVars

    const result = {
      mcpServers: {}
    }
    result['mcpServers'][serverName] = {
      name: serverName,
      type: mcpType,
      ...properties,
    }

    console.log('Creating MCP server inventory item:', result)
    return result
  }, [serverDef, formData])

  const buildConnectJsonSchemaForServer = (serverDef: any): RJSFSchema => {
    const properties: any = {}

    // env vars
    // const envs = serverDef?.env || []
    // envs.forEach((envVar: any) => {
    //     properties[envVar.name] = {
    //         type: "string",
    //         title: envVar.name,
    //         default: envVar.value || ""
    //     }
    // })
    console.log('serverDef:', serverDef)
    console.log('serverDef config:', serverDef?.config)
    const config = serverDef?.config && Array.isArray(serverDef?.config)
      ? serverDef?.config[0] || {} : {}

    // add secrets
    const secrets = serverDef?.secrets || []
    secrets.forEach((secretVar: any) => {
      properties['secret__' + secretVar.name] = {
        type: 'string',
        title: '🔐 Secret: ' + secretVar.name,
        default: '',
        description: `Secret (in env var ${secretVar.env})`,
      }
    })

    if (config) {
      config?.properties?.forEach((configVar: any) => {
        const schema = configVar?.Schema || {}
        properties[configVar.Name] = schema
      })
    }

    return {
      type: 'object',
      properties: properties,
      required: [],
    }
  }

  const handleFormChange = async ({ formData }: any) => {
    console.log('Form data:', formData)
    setFormData(formData)
  }

  return (
    <div className={""}>
      <Form schema={buildConnectJsonSchemaForServer(serverDef)}
            validator={validator}
            onChange={handleFormChange}
      >{' '}</Form>
      <hr className={"my-3"} />
      {result && <div className={''}>
        <p className={'pb-4 text-sm'}>
          In your .geenii/mcp.json configuration file, update the "mcpServers"
          section to include the following entry:
        </p>
        <JsonView src={result} className={"max-w-[300px]"} />
        {/*<JsonView src={formData} />*/}
      </div>}
    </div>
  )
}

export default DockerMcpServerConfigBuilder