import React from 'react'
import {
    DockerMcpCatalogServerDef,
    useDockerMcpCatalog,
} from '@/app/catalog/components/docker-mcp-catalog-provider.tsx'
import { Button } from '@/components/ui/button.tsx'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog.tsx'
import { Badge } from '@/components/ui/badge.tsx'
import { Input } from '@/components/ui/input.tsx'
import JsonView from '@/components/json-view.tsx'
import DockerMcpCatalogConfigBuilder from '@/app/catalog/components/docker-mcp-catalog-config-builder.tsx'

/**
 * Render the docker MCP toolkit catalog
 *
 * Example data:
 * {
 *       "type": "image",
 *       "image": "mcp/airtable-mcp-server@sha256:3d15a7da38f6d077a481d3f8b7ca0a445ceb51fe66dac81650d06a60731591e3",
 *       "snapshot": {
 *         "server": {
 *           "name": "airtable-mcp-server",
 *           "type": "server",
 *           "image": "mcp/airtable-mcp-server@sha256:3d15a7da38f6d077a481d3f8b7ca0a445ceb51fe66dac81650d06a60731591e3",
 *           "description": "Provides AI assistants with direct access to Airtable bases, allowing them to read schemas, query records, and interact with your Airtable data. Supports listing bases, retrieving table structures, and searching through records to help automate workflows and answer questions about your organized data.",
 *           "title": "Airtable",
 *           "icon": "https://www.google.com/s2/favicons?domain=airtable.com\u0026sz=64",
 *           "readme": "https://desktop.docker.com/mcp/catalog/v3/readme/airtable-mcp-server.md",
 *           "remote": {},
 *           "secrets": [
 *             {
 *               "name": "airtable-mcp-server.api_key",
 *               "env": "AIRTABLE_API_KEY"
 *             }
 *           ],
 *           "env": [
 *             {
 *               "name": "NODE_ENV",
 *               "value": "{{airtable-mcp-server.nodeenv}}"
 *             }
 *           ],
 *           "tools": [
 *             {
 *               "name": "create_comment",
 *               "description": "Create a comment on a record",
 *               "arguments": [
 *                 {
 *                   "name": "baseId",
 *                   "type": "string",
 *                   "desc": "The ID of the base"
 *                 },
 *                 {
 *                   "name": "recordId",
 *                   "type": "string",
 *                   "desc": "The ID of the record"
 *                 },
 *                 {
 *                   "name": "tableId",
 *                   "type": "string",
 *                   "desc": "The ID or name of the table"
 *                 },
 *                 {
 *                   "name": "text",
 *                   "type": "string",
 *                   "desc": "The comment text"
 *                 },
 *                 {
 *                   "name": "parentCommentId",
 *                   "type": "string",
 *                   "desc": "Optional parent comment ID for threaded replies",
 *                   "optional": true
 *                 }
 *               ],
 *               "annotations": {
 *                 "readOnlyHint": false,
 *                 "destructiveHint": false
 *               },
 *               "container": {
 *                 "image": "",
 *                 "command": null,
 *                 "volumes": null
 *               },
 *               "parameters": {
 *                 "type": "",
 *                 "properties": null,
 *                 "required": null
 *               }
 *             },
 *             {
 *               "name": "create_field",
 *               "description": "Create a new field in a table",
 *               "arguments": [
 *                 {
 *                   "name": "baseId",
 *                   "type": "string",
 *                   "desc": "The ID of the base"
 *                 },
 *                 {
 *                   "name": "nested",
 *                   "type": "object",
 *                   "desc": ""
 *                 },
 *                 {
 *                   "name": "tableId",
 *                   "type": "string",
 *                   "desc": "The ID or name of the table"
 *                 }
 *               ],
 *               "annotations": {
 *                 "readOnlyHint": false,
 *                 "destructiveHint": false
 *               },
 *               "container": {
 *                 "image": "",
 *                 "command": null,
 *                 "volumes": null
 *               },
 *               "parameters": {
 *                 "type": "",
 *                 "properties": null,
 *                 "required": null
 *               }
 *             },
 *             {
 *               "name": "create_record",
 *               "description": "Create a new record in a table",
 *               "arguments": [
 *                 {
 *                   "name": "baseId",
 *                   "type": "string",
 *                   "desc": "The ID of the base"
 *                 },
 *                 {
 *                   "name": "fields",
 *                   "type": "object",
 *                   "desc": "The fields for the new record"
 *                 },
 *                 {
 *                   "name": "tableId",
 *                   "type": "string",
 *                   "desc": "The ID or name of the table"
 *                 }
 *               ],
 *               "annotations": {
 *                 "readOnlyHint": false,
 *                 "destructiveHint": false
 *               },
 *               "container": {
 *                 "image": "",
 *                 "command": null,
 *                 "volumes": null
 *               },
 *               "parameters": {
 *                 "type": "",
 *                 "properties": null,
 *                 "required": null
 *               }
 *             },
 *             {
 *               "name": "create_table",
 *               "description": "Create a new table in a base",
 *               "arguments": [
 *                 {
 *                   "name": "baseId",
 *                   "type": "string",
 *                   "desc": "The ID of the base"
 *                 },
 *                 {
 *                   "name": "fields",
 *                   "type": "array",
 *                   "items": {
 *                     "type": "object"
 *                   },
 *                   "desc": "Array of field definitions"
 *                 },
 *                 {
 *                   "name": "name",
 *                   "type": "string",
 *                   "desc": "The name of the table"
 *                 },
 *                 {
 *                   "name": "description",
 *                   "type": "string",
 *                   "desc": "Optional description for the table",
 *                   "optional": true
 *                 }
 *               ],
 *               "annotations": {
 *                 "readOnlyHint": false,
 *                 "destructiveHint": false
 *               },
 *               "container": {
 *                 "image": "",
 *                 "command": null,
 *                 "volumes": null
 *               },
 *               "parameters": {
 *                 "type": "",
 *                 "properties": null,
 *                 "required": null
 *               }
 *             },
 *             {
 *               "name": "delete_records",
 *               "description": "Delete records from a table",
 *               "arguments": [
 *                 {
 *                   "name": "baseId",
 *                   "type": "string",
 *                   "desc": "The ID of the base"
 *                 },
 *                 {
 *                   "name": "recordIds",
 *                   "type": "array",
 *                   "items": {
 *                     "type": "string"
 *                   },
 *                   "desc": "Array of record IDs to delete"
 *                 },
 *                 {
 *                   "name": "tableId",
 *                   "type": "string",
 *                   "desc": "The ID or name of the table"
 *                 }
 *               ],
 *               "annotations": {
 *                 "readOnlyHint": false,
 *                 "destructiveHint": true
 *               },
 *               "container": {
 *                 "image": "",
 *                 "command": null,
 *                 "volumes": null
 *               },
 *               "parameters": {
 *                 "type": "",
 *                 "properties": null,
 *                 "required": null
 *               }
 *             },
 *             {
 *               "name": "describe_table",
 *               "description": "Get detailed information about a specific table",
 *               "arguments": [
 *                 {
 *                   "name": "baseId",
 *                   "type": "string",
 *                   "desc": "The ID of the base"
 *                 },
 *                 {
 *                   "name": "tableId",
 *                   "type": "string",
 *                   "desc": "The ID or name of the table"
 *                 },
 *                 {
 *                   "name": "detailLevel",
 *                   "type": "string",
 *                   "desc": "Detail level for table information:\n- tableIdentifiersOnly: table IDs and names\n- identifiersOnly: table, field, and view IDs and names\n- full: complete details including field types, descriptions, and configurations\n\nNote for LLMs: To optimize context window usage, request the minimum detail level needed:\n- Use 'tableIdentifiersOnly' when you only need to list or reference tables\n- Use 'identifiersOnly' when you need to work with field or view references\n- Only use 'full' when you need field types, descriptions, or other detailed configuration\n\nIf you only need detailed information on a few tables in a base with many complex tables, it might be more efficient for you to use list_tables with tableIdentifiersOnly, then describe_table with full on the specific tables you want.",
 *                   "optional": true
 *                 }
 *               ],
 *               "annotations": {
 *                 "readOnlyHint": true
 *               },
 *               "container": {
 *                 "image": "",
 *                 "command": null,
 *                 "volumes": null
 *               },
 *               "parameters": {
 *                 "type": "",
 *                 "properties": null,
 *                 "required": null
 *               }
 *             },
 *             {
 *               "name": "get_record",
 *               "description": "Get a specific record by ID",
 *               "arguments": [
 *                 {
 *                   "name": "baseId",
 *                   "type": "string",
 *                   "desc": "The ID of the base"
 *                 },
 *                 {
 *                   "name": "recordId",
 *                   "type": "string",
 *                   "desc": "The ID of the record"
 *                 },
 *                 {
 *                   "name": "tableId",
 *                   "type": "string",
 *                   "desc": "The ID or name of the table"
 *                 }
 *               ],
 *               "annotations": {
 *                 "readOnlyHint": true
 *               },
 *               "container": {
 *                 "image": "",
 *                 "command": null,
 *                 "volumes": null
 *               },
 *               "parameters": {
 *                 "type": "",
 *                 "properties": null,
 *                 "required": null
 *               }
 *             },
 *             {
 *               "name": "list_bases",
 *               "description": "List all accessible Airtable bases",
 *               "arguments": [],
 *               "annotations": {
 *                 "readOnlyHint": true
 *               },
 *               "container": {
 *                 "image": "",
 *                 "command": null,
 *                 "volumes": null
 *               },
 *               "parameters": {
 *                 "type": "",
 *                 "properties": null,
 *                 "required": null
 *               }
 *             },
 *             {
 *               "name": "list_comments",
 *               "description": "List comments on a record",
 *               "arguments": [
 *                 {
 *                   "name": "baseId",
 *                   "type": "string",
 *                   "desc": "The ID of the base"
 *                 },
 *                 {
 *                   "name": "recordId",
 *                   "type": "string",
 *                   "desc": "The ID of the record"
 *                 },
 *                 {
 *                   "name": "tableId",
 *                   "type": "string",
 *                   "desc": "The ID or name of the table"
 *                 },
 *                 {
 *                   "name": "offset",
 *                   "type": "string",
 *                   "desc": "Offset for pagination",
 *                   "optional": true
 *                 },
 *                 {
 *                   "name": "pageSize",
 *                   "type": "number",
 *                   "desc": "Number of comments to return (max 100, default 100)",
 *                   "optional": true
 *                 }
 *               ],
 *               "annotations": {
 *                 "readOnlyHint": true
 *               },
 *               "container": {
 *                 "image": "",
 *                 "command": null,
 *                 "volumes": null
 *               },
 *               "parameters": {
 *                 "type": "",
 *                 "properties": null,
 *                 "required": null
 *               }
 *             },
 *             {
 *               "name": "list_records",
 *               "description": "List records from a table",
 *               "arguments": [
 *                 {
 *                   "name": "baseId",
 *                   "type": "string",
 *                   "desc": "The ID of the base"
 *                 },
 *                 {
 *                   "name": "tableId",
 *                   "type": "string",
 *                   "desc": "The ID or name of the table"
 *                 },
 *                 {
 *                   "name": "filterByFormula",
 *                   "type": "string",
 *                   "desc": "A formula used to filter records",
 *                   "optional": true
 *                 },
 *                 {
 *                   "name": "maxRecords",
 *                   "type": "number",
 *                   "desc": "The maximum total number of records that will be returned",
 *                   "optional": true
 *                 },
 *                 {
 *                   "name": "sort",
 *                   "type": "array",
 *                   "items": {
 *                     "type": "object"
 *                   },
 *                   "desc": "A list of sort objects that specifies how the records will be ordered",
 *                   "optional": true
 *                 },
 *                 {
 *                   "name": "view",
 *                   "type": "string",
 *                   "desc": "The name or ID of a view in the table",
 *                   "optional": true
 *                 }
 *               ],
 *               "annotations": {
 *                 "readOnlyHint": true
 *               },
 *               "container": {
 *                 "image": "",
 *                 "command": null,
 *                 "volumes": null
 *               },
 *               "parameters": {
 *                 "type": "",
 *                 "properties": null,
 *                 "required": null
 *               }
 *             },
 *             {
 *               "name": "list_tables",
 *               "description": "List all tables in a specific base",
 *               "arguments": [
 *                 {
 *                   "name": "baseId",
 *                   "type": "string",
 *                   "desc": "The ID of the base"
 *                 },
 *                 {
 *                   "name": "detailLevel",
 *                   "type": "string",
 *                   "desc": "Detail level for table information:\n- tableIdentifiersOnly: table IDs and names\n- identifiersOnly: table, field, and view IDs and names\n- full: complete details including field types, descriptions, and configurations\n\nNote for LLMs: To optimize context window usage, request the minimum detail level needed:\n- Use 'tableIdentifiersOnly' when you only need to list or reference tables\n- Use 'identifiersOnly' when you need to work with field or view references\n- Only use 'full' when you need field types, descriptions, or other detailed configuration\n\nIf you only need detailed information on a few tables in a base with many complex tables, it might be more efficient for you to use list_tables with tableIdentifiersOnly, then describe_table with full on the specific tables you want.",
 *                   "optional": true
 *                 }
 *               ],
 *               "annotations": {
 *                 "readOnlyHint": true
 *               },
 *               "container": {
 *                 "image": "",
 *                 "command": null,
 *                 "volumes": null
 *               },
 *               "parameters": {
 *                 "type": "",
 *                 "properties": null,
 *                 "required": null
 *               }
 *             },
 *             {
 *               "name": "search_records",
 *               "description": "Search for records containing specific text",
 *               "arguments": [
 *                 {
 *                   "name": "baseId",
 *                   "type": "string",
 *                   "desc": "The ID of the base"
 *                 },
 *                 {
 *                   "name": "searchTerm",
 *                   "type": "string",
 *                   "desc": "The text to search for"
 *                 },
 *                 {
 *                   "name": "tableId",
 *                   "type": "string",
 *                   "desc": "The ID or name of the table"
 *                 },
 *                 {
 *                   "name": "fieldIds",
 *                   "type": "array",
 *                   "items": {
 *                     "type": "string"
 *                   },
 *                   "desc": "Optional array of field IDs to search in",
 *                   "optional": true
 *                 },
 *                 {
 *                   "name": "maxRecords",
 *                   "type": "number",
 *                   "desc": "The maximum total number of records that will be returned",
 *                   "optional": true
 *                 },
 *                 {
 *                   "name": "view",
 *                   "type": "string",
 *                   "desc": "The name or ID of a view in the table",
 *                   "optional": true
 *                 }
 *               ],
 *               "annotations": {
 *                 "readOnlyHint": true
 *               },
 *               "container": {
 *                 "image": "",
 *                 "command": null,
 *                 "volumes": null
 *               },
 *               "parameters": {
 *                 "type": "",
 *                 "properties": null,
 *                 "required": null
 *               }
 *             },
 *             {
 *               "name": "update_field",
 *               "description": "Update a field's name or description",
 *               "arguments": [
 *                 {
 *                   "name": "baseId",
 *                   "type": "string",
 *                   "desc": "The ID of the base"
 *                 },
 *                 {
 *                   "name": "fieldId",
 *                   "type": "string",
 *                   "desc": "The ID of the field"
 *                 },
 *                 {
 *                   "name": "tableId",
 *                   "type": "string",
 *                   "desc": "The ID or name of the table"
 *                 },
 *                 {
 *                   "name": "description",
 *                   "type": "string",
 *                   "desc": "New description for the field",
 *                   "optional": true
 *                 },
 *                 {
 *                   "name": "name",
 *                   "type": "string",
 *                   "desc": "New name for the field",
 *                   "optional": true
 *                 }
 *               ],
 *               "annotations": {
 *                 "readOnlyHint": false,
 *                 "destructiveHint": true
 *               },
 *               "container": {
 *                 "image": "",
 *                 "command": null,
 *                 "volumes": null
 *               },
 *               "parameters": {
 *                 "type": "",
 *                 "properties": null,
 *                 "required": null
 *               }
 *             },
 *             {
 *               "name": "update_records",
 *               "description": "Update up to 10 records in a table",
 *               "arguments": [
 *                 {
 *                   "name": "baseId",
 *                   "type": "string",
 *                   "desc": "The ID of the base"
 *                 },
 *                 {
 *                   "name": "records",
 *                   "type": "array",
 *                   "items": {
 *                     "type": "object"
 *                   },
 *                   "desc": "Array of records to update (max 10)"
 *                 },
 *                 {
 *                   "name": "tableId",
 *                   "type": "string",
 *                   "desc": "The ID or name of the table"
 *                 }
 *               ],
 *               "annotations": {
 *                 "readOnlyHint": false,
 *                 "destructiveHint": true
 *               },
 *               "container": {
 *                 "image": "",
 *                 "command": null,
 *                 "volumes": null
 *               },
 *               "parameters": {
 *                 "type": "",
 *                 "properties": null,
 *                 "required": null
 *               }
 *             },
 *             {
 *               "name": "update_table",
 *               "description": "Update a table's name or description",
 *               "arguments": [
 *                 {
 *                   "name": "baseId",
 *                   "type": "string",
 *                   "desc": "The ID of the base"
 *                 },
 *                 {
 *                   "name": "tableId",
 *                   "type": "string",
 *                   "desc": "The ID or name of the table"
 *                 },
 *                 {
 *                   "name": "description",
 *                   "type": "string",
 *                   "desc": "New description for the table",
 *                   "optional": true
 *                 },
 *                 {
 *                   "name": "name",
 *                   "type": "string",
 *                   "desc": "New name for the table",
 *                   "optional": true
 *                 }
 *               ],
 *               "annotations": {
 *                 "readOnlyHint": false,
 *                 "destructiveHint": true
 *               },
 *               "container": {
 *                 "image": "",
 *                 "command": null,
 *                 "volumes": null
 *               },
 *               "parameters": {
 *                 "type": "",
 *                 "properties": null,
 *                 "required": null
 *               }
 *             },
 *             {
 *               "name": "upload_attachment",
 *               "description": "Upload a file directly to an attachment field on an existing record using Airtable's upload API. Supports files up to 5 MB. For larger files, use create_record or update_records with a public URL. The record must already exist.",
 *               "arguments": [
 *                 {
 *                   "name": "attachmentFieldIdOrName",
 *                   "type": "string",
 *                   "desc": "The ID or name of the attachment field (e.g. fldXXXXXXXXXXXXXX or \"Images\")"
 *                 },
 *                 {
 *                   "name": "baseId",
 *                   "type": "string",
 *                   "desc": "The ID of the base"
 *                 },
 *                 {
 *                   "name": "contentType",
 *                   "type": "string",
 *                   "desc": "MIME type of the file (e.g. \"image/jpeg\", \"image/png\", \"application/pdf\")"
 *                 },
 *                 {
 *                   "name": "file",
 *                   "type": "string",
 *                   "desc": "Raw base64-encoded file content (no data URL prefix)"
 *                 },
 *                 {
 *                   "name": "filename",
 *                   "type": "string",
 *                   "desc": "Filename for the attachment (e.g. \"image.jpg\")"
 *                 },
 *                 {
 *                   "name": "recordId",
 *                   "type": "string",
 *                   "desc": "The ID of the existing record (e.g. recXXXXXXXXXXXXXX)"
 *                 }
 *               ],
 *               "annotations": {
 *                 "readOnlyHint": false,
 *                 "destructiveHint": false
 *               },
 *               "container": {
 *                 "image": "",
 *                 "command": null,
 *                 "volumes": null
 *               },
 *               "parameters": {
 *                 "type": "",
 *                 "properties": null,
 *                 "required": null
 *               }
 *             }
 *           ],
 *           "config": [
 *             {
 *               "description": "Configure the connection to Airtable mcp server",
 *               "name": "airtable-mcp-server",
 *               "properties": {
 *                 "nodeenv": {
 *                   "type": "string"
 *                 }
 *               },
 *               "type": "object"
 *             }
 *           ],
 *           "metadata": {
 *             "pulls": 19894,
 *             "stars": 1,
 *             "githubStars": 455,
 *             "category": "productivity",
 *             "tags": [
 *               "productivity"
 *             ],
 *             "license": "MIT License",
 *             "owner": "domdomegg"
 *           }
 *         }
 *       }
 *     },
 *     {
 *       "type": "remote",
 *       "endpoint": "https://mcp.aisfleet.com/sse",
 *       "snapshot": {
 *         "server": {
 *           "name": "ais-fleet",
 *           "type": "remote",
 *           "image": "",
 *           "description": "The AIS Fleet MCP Server provides a unified interface for discovering, querying, and analyzing vessel activity from AIS data. It enables MCP-based agents and tools to answer complex maritime questions such as vessel movements between regions, port activity trends, or traffic patterns over time, empowering developers, researchers, and fleet operators to build intelligent, location-aware marine applications powered by AIS insights.",
 *           "title": "AIS Fleet",
 *           "icon": "https://aisfleet.com/static/logo_icon.png",
 *           "readme": "https://desktop.docker.com/mcp/catalog/v3/readme/ais-fleet.md",
 *           "remote": {
 *             "url": "https://mcp.aisfleet.com/sse",
 *             "transport_type": "sse"
 *           },
 *           "metadata": {
 *             "category": "boating",
 *             "tags": [
 *               "boating",
 *               "remote"
 *             ],
 *             "license": "Apache License 2.0",
 *             "owner": "docker"
 *           }
 *         }
 *       }
 *     },
 *
 *
 * @constructor
 */
const DockerMcpCatalogOci = () => {
  const { catalog } = useDockerMcpCatalog()
  const [selectedServerKey, setSelectedServerKey] = React.useState<string | null>(null)
  const [selectedServer, setSelectedServer] = React.useState<DockerMcpCatalogServerDef | null>(null)

  const [searchTerm, setSearchTerm] = React.useState<string>('')
  const [category, setCategory] = React.useState<string>('')
  const [rawJsonKeys, setRawJsonKeys] = React.useState<Set<string>>(new Set())

  const toggleRawJson = (key: string) => {
    setRawJsonKeys((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  const registry = catalog && catalog?.servers ? catalog.servers:null

  const itemHasSecrets = (item: DockerMcpCatalogServerDef) => {
      return item?.secrets && item?.secrets.length > 0
  }

  const itemHasEnv = (item: DockerMcpCatalogServerDef) => {
      return item?.env && item?.env.length > 0
  }

  const itemHasConfig = (item: DockerMcpCatalogServerDef) => {
      return item?.config && item?.config.length > 0
  }

  const itemHasOauth = (item: DockerMcpCatalogServerDef) => {
      return item?.oauth && item?.oauth.providers && item?.oauth.providers.length > 0
  }

  const toolCount = React.useMemo(() => {
      if (!registry) return 0;
      return registry.reduce((count, record) => {
          const tools = record.snapshot?.server?.tools
          return count + (Array.isArray(tools) ? tools.length : 0)
      }, 0)
  }, [registry])

  const getCategory = (server: DockerMcpCatalogServerDef): string => {
      const value = server?.metadata?.category
      return typeof value === 'string' ? value.trim().toLowerCase() : ''
  }

  // categories with server counts, most used first
  const categories = React.useMemo(() => {
      if (!registry) return []
      const counts = new Map<string, number>()
      registry.forEach((record) => {
          const cat = getCategory(record.snapshot.server)
          if (cat) counts.set(cat, (counts.get(cat) || 0) + 1)
      })
      return [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
  }, [registry])

  const filteredServers = React.useMemo(() => {
      if (!registry) return []
      const term = searchTerm.trim().toLowerCase()
      if (!term && !category) return registry

      return registry.filter((record) => {
          const server = record.snapshot.server
          if (category && getCategory(server) !== category) return false
          if (!term) return true
          const haystack = [
              server.name,
              server.title,
              server.description,
              server.metadata?.category,
              ...(server.metadata?.tags || []),
              ...(server.tools || []).map((tool: any) => tool?.name),
          ]
          return haystack.some((value) => typeof value === 'string' && value.toLowerCase().includes(term))
      })
  }, [registry, searchTerm, category])


  const typeEmojis: { [key: string]: string } = {
    'server': '🖥️',
    'remote': '☁️',
    'poci': '🧪',
  }

  const getTypeEmoji = (type: string) => {
    return typeEmojis[type] || '❓'
  }

  const numberFormat = new Intl.NumberFormat(undefined, { notation: 'compact', maximumFractionDigits: 1 })
  const formatCount = (value: unknown) => typeof value === 'number' ? numberFormat.format(value) : null

  return (
    <div>
      <div className={'flex flex-row gap-2 mb-4'}>
        <Input value={searchTerm}
               placeholder={'Search servers, tools, tags...'}
               className={'flex-1'}
               onChange={(e) => setSearchTerm(e.target.value)} />
        <select value={category}
                aria-label={'Filter by category'}
                className={'h-9 rounded-md border border-input bg-transparent px-3 text-sm shadow-xs dark:bg-input/30'}
                onChange={(e) => setCategory(e.target.value)}>
          <option value={''}>All categories</option>
          {categories.map(([cat, count]) => (
            <option key={cat} value={cat}>{cat} ({count})</option>
          ))}
        </select>
      </div>
      <div className={'flex flex-row mb-2 text-sm text-muted-foreground'}>
        {registry?.length || 0} servers in registry.{' '}
        {toolCount} tools available.{' '}
        {(searchTerm.trim() || category) && `${filteredServers.length} servers match.`}
      </div>
      {filteredServers.map((record) => {
        const server = record.snapshot.server
        const key = server.name
        const metadata = server?.metadata || {}
        const pulls = formatCount(metadata.pulls)
        const githubStars = formatCount(metadata.githubStars)
        const serverCategory = getCategory(server)
        return (
          <div key={server.name} className={'border px-4 py-2 mb-2 rounded-xl hover:bg-accent'}>
            <div className={'flex justify-between items-center'}>
              <div className={'mb-1'}>
                <h3 className={'font-bold'} title={server?.description} onClick={() => {
                  if (selectedServerKey===key) {
                    setSelectedServerKey(null)
                    setSelectedServer(null)
                  } else {
                    setSelectedServerKey(key)
                    setSelectedServer(server)
                  }
                }}>
                  {getTypeEmoji(server.type)} {server.title}</h3>
                <p
                  className={'text-xs text-muted-foreground mb-1 max-h-8 overflow-hidden hover:max-h-16 hover:overflow-y-scroll'}>{server?.description}</p>

                <div className={'flex flex-row flex-wrap gap-x-2 mb-1 text-xs text-muted-foreground'}>
                  {metadata.owner && <div title={'Owner'}>👤 {metadata.owner}</div>}
                  {serverCategory && (
                    <button type={'button'} title={'Filter by this category'}
                            className={'cursor-pointer hover:underline'}
                            onClick={() => setCategory(serverCategory)}>
                      🏷️ {serverCategory}
                    </button>
                  )}
                  {pulls && <div title={`${metadata.pulls} Docker pulls`}>⬇️ {pulls} pulls</div>}
                  {githubStars && <div title={`${metadata.githubStars} GitHub stars`}>⭐ {githubStars} GitHub stars</div>}
                </div>

                <div className={'flex flex-row'}>
                  <div className={"text-xs text-muted-foreground mr-1"}>🛠️ {server?.tools?.length || 0} tools</div>
                  <div className={"text-xs text-muted-foreground mr-1"}>{(itemHasConfig(server) || itemHasEnv(server)) && ("⚙️ Requires configuration")}</div>
                  <div className={"text-xs text-muted-foreground mr-1"}>{itemHasSecrets(server) && ("🔑 Requires secrets")}</div>
                  <div className={"text-xs text-muted-foreground mr-1"}>{itemHasOauth(server) && (`🆔 ${server?.oauth?.providers.length} Oauth provider`)}</div>

                  <div className={'text-xs text-muted-foreground mr-1'}>
                    📄 <a rel={'noreferrer noopener'} href={server?.readme} target={'_blank'}>Readme</a>
                  </div>
                  <div className={'text-xs text-muted-foreground mr-1'}>
                    📚 <a rel={'noreferrer noopener'} href={server?.source} target={'_blank'}>Source</a>
                  </div>
                  <div className={'text-xs text-muted-foreground mr-1'}>
                    <button type={'button'} className={'cursor-pointer hover:underline'}
                            onClick={() => toggleRawJson(key)}>
                      {'{ }'} {rawJsonKeys.has(key) ? 'Hide JSON' : 'JSON'}
                    </button>
                  </div>
                </div>
                <div className={'flex flex-wrap space-x-1'}>
                  {server?.tools?.map((tool: any) => (
                    <div key={tool.name}><Badge>{tool.name}</Badge></div>
                  ))}
                </div>
              </div>
              <Button variant={'outline'}
                      size={'sm'}
                      onClick={() => {
                        setSelectedServerKey(key)
                        setSelectedServer(server)
                      }}>Add Server</Button>
            </div>
            {rawJsonKeys.has(key) && (
              <div className={'mt-2'}>
                <JsonView src={record} className={'max-w-full text-xs'} />
              </div>
            )}
            {selectedServer?.title===server.title && <div>
              <Dialog onOpenChange={() => setSelectedServerKey(null)}
                      open={selectedServerKey!==null}>
                <DialogContent className={'max-h-200 w-1/2 overflow-y-scroll'}>
                  <DialogHeader>
                    <DialogTitle>Connect {selectedServer?.title}</DialogTitle>
                  </DialogHeader>
                  <DockerMcpCatalogConfigBuilder serverName={selectedServerKey}
                                                 serverDef={selectedServer} />
                </DialogContent>
              </Dialog>
            </div>}
          </div>
        )
      })}
    </div>
  )
}

export default DockerMcpCatalogOci
