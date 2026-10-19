import React from 'react'
import {
    DockerMcpCatalogServerDef,
    useDockerMcpCatalog,
} from '@/app/catalog/components/docker-mcp-catalog-provider.tsx'
import { Button } from '@/components/ui/button.tsx'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog.tsx'
import { Badge } from '@/components/ui/badge.tsx'
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

  // const [searchTerm, setSearchTerm] = React.useState<string>("");
  // const [searchFilter, setSearchFilter] = React.useState<any>({"hasTools": false, "hasConfig": false, "hasSecrets": false, "hasOauth": false, "hasNoConfig": false, "hasNoSecrets": false});

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
      let count = 0;
      Object.values(registry).forEach((item: any) => {
          if (item.tools && Array.isArray(item.tools)) {
              count += item.tools.length;
          }
      });
      return count;
  }, [registry])

  // const filteredRegistry = React.useMemo(() => {
  //     if (!registry) return {};
  //
  //     const filtered: { [key: string]: any } = {};
  //
  //     if (searchTerm.trim() !== "") {
  //         const lowerSearchTerm = searchTerm.toLowerCase();
  //         Object.entries(registry).forEach(([key, item]: [string, any]) => {
  //             if (
  //                 key.toLowerCase().includes(lowerSearchTerm) ||
  //                 (item.title && item.title.toLowerCase().includes(lowerSearchTerm)) ||
  //                 (item.description && item.description.toLowerCase().includes(lowerSearchTerm)) ||
  //                 (item.tags && item.tags.some((tag: string) => tag.toLowerCase().includes(lowerSearchTerm)))
  //             ) {
  //                 filtered[key] = item;
  //             }
  //         });
  //     }
  //
  //     // apply additional filters
  //     Object.entries(registry).forEach(([key, item]: [string, any]) => {
  //         let matches = true;
  //         if (searchFilter.hasTools && (!item.tools || item.tools.length === 0)) {
  //             matches = false;
  //         }
  //         if (searchFilter.hasConfig && (!itemHasConfig(item) || !itemHasEnv(item))) {
  //             matches = false;
  //         }
  //         if (searchFilter.hasSecrets && !itemHasSecrets(item)) {
  //             matches = false;
  //         }
  //         if (searchFilter.hasOauth && itemHasOauth(item)) {
  //             matches = false;
  //         }
  //         if (searchFilter.hasNoConfig && (itemHasConfig(item) || itemHasEnv(item))) {
  //             matches = false;
  //         }
  //         if (searchFilter.hasNoSecrets && itemHasSecrets(item)) {
  //             matches = false;
  //         }
  //         if (matches) {
  //             filtered[key] = item;
  //         }
  //     });
  //
  //     return filtered;
  // }, [registry, searchTerm, searchFilter]);


  const typeEmojis: { [key: string]: string } = {
    'server': '🖥️',
    'remote': '☁️',
    'poci': '🧪',
  }

  const getTypeEmoji = (type: string) => {
    return typeEmojis[type] || '❓'
  }

  return (
    <div>
      {/*<div>*/}
      {/*    <Input value={searchTerm} placeholder={"Search..."} className={"mb-4"}*/}
      {/*           onChange={(e) => setSearchTerm(e.target.value)} />*/}

      {/*    <div className={"flex flex-row mb-4"}>*/}
      {/*        <div className={"mr-4"}>*/}
      {/*            <input type="checkbox" id="hasTools" checked={searchFilter.hasTools}*/}
      {/*                   onChange={(e) => setSearchFilter({...searchFilter, hasTools: e.target.checked})} />*/}
      {/*            <label htmlFor="hasTools" className={"ml-1"}>Has Tools</label>*/}
      {/*        </div>*/}
      {/*        <div className={"mr-4"}>*/}
      {/*            <input type="checkbox" id="hasConfig" checked={searchFilter.hasConfig}*/}
      {/*                   onChange={(e) => setSearchFilter({...searchFilter, hasConfig: e.target.checked, hasNoConfig: false})} />*/}
      {/*            <label htmlFor="hasConfig" className={"ml-1"}>Requires Config</label>*/}
      {/*        </div>*/}
      {/*        <div className={"mr-4"}>*/}
      {/*            <input type="checkbox" id="hasSecrets" checked={searchFilter.hasSecrets}*/}
      {/*                   onChange={(e) => setSearchFilter({...searchFilter, hasSecrets: e.target.checked, hasNoSecrets: false})} />*/}
      {/*            <label htmlFor="hasSecrets" className={"ml-1"}>Requires Secrets</label>*/}
      {/*        </div>*/}
      {/*        <div className={"mr-4"}>*/}
      {/*            <input type="checkbox" id="hasOauth" checked={searchFilter.hasOauth}*/}
      {/*                   onChange={(e) => setSearchFilter({...searchFilter, hasOauth: e.target.checked})} />*/}
      {/*            <label htmlFor="hasOauth" className={"ml-1"}>Has Oauth</label>*/}
      {/*        </div>*/}
      {/*        <div className={"mr-4"}>*/}
      {/*            <input type="checkbox" id="hasNoConfig" checked={searchFilter.hasNoConfig}*/}
      {/*                   onChange={(e) => setSearchFilter({...searchFilter, hasNoConfig: e.target.checked, hasConfig: false})} />*/}
      {/*            <label htmlFor="hasNoConfig" className={"ml-1"}>No Config Required</label>*/}
      {/*        </div>*/}
      {/*        <div className={"mr-4"}>*/}
      {/*            <input type="checkbox" id="hasNoSecrets" checked={searchFilter.hasNoSecrets}*/}
      {/*                   onChange={(e) => setSearchFilter({...searchFilter, hasNoSecrets: e.target.checked, hasSecrets: false})} />*/}
      {/*            <label htmlFor="hasNoSecrets" className={"ml-1"}>No Secrets Required</label>*/}
      {/*        </div>*/}
      {/*    </div>*/}
      {/*</div>*/}
      {/*<div className={'flex flex-row mb-2 text-muted-foreground'}>*/}
      {/*  {registry && Object.keys(registry).length} servers in registry.{' '}*/}
      {/*  {toolCount} tools available.{' '}*/}
      {/*  {Object.keys(filteredRegistry).length} servers match filters.*/}
      {/*</div>*/}
      {catalog?.servers && catalog?.servers?.map((record) => {
        const server = record.snapshot.server
        const key = server.name
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
                </div>
                {/*<div>
                                    <JsonView src={item} collapsed={true} />
                                </div>*/}
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
