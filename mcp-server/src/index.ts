#!/usr/bin/env node
/**
 * SAP Workflow Mining MCP Server
 *
 * This server exposes 8 SAP-shaped tools for workflow mining analysis.
 * It uses the Model Context Protocol (MCP) to integrate with AI assistants.
 *
 * Architecture:
 * - Tools: 8 specialized tools for SAP document analysis
 * - Adapters: Pluggable data sources (synthetic, ECC RFC, S/4 OData)
 * - Policies: Row limits, field restrictions, timeout handling
 * - Audit: Comprehensive logging of all tool calls
 *
 * Usage:
 *   SAP_ADAPTER=synthetic node dist/index.js
 *   SYNTHETIC_DATA_PATH=/path/to/data node dist/index.js
 */

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';

import { IDataAdapter } from './adapters/adapter-interface.js';
import { SyntheticAdapter } from './adapters/synthetic/index.js';
import { allTools, executeTool } from './tools/index.js';
import { logServerEvent } from './logging/audit-logger.js';
import { PolicyViolationError, TimeoutError } from './policies/limits.js';

// Import adapters to ensure they register themselves
import './adapters/ecc_rfc/index.js';
import './adapters/s4_odata/index.js';

/**
 * Server configuration from environment
 */
interface ServerConfig {
  adapterType: 'synthetic' | 'ecc_rfc' | 's4_odata';
  syntheticDataPath?: string;
  logLevel?: string;
}

function getConfig(): ServerConfig {
  const syntheticDataPath = process.env['SYNTHETIC_DATA_PATH'];
  return {
    adapterType: (process.env['SAP_ADAPTER'] as ServerConfig['adapterType']) || 'synthetic',
    ...(syntheticDataPath ? { syntheticDataPath } : {}),
    logLevel: process.env['LOG_LEVEL'] || 'info',
  };
}

/**
 * Create the appropriate adapter based on configuration
 */
async function createAdapter(config: ServerConfig): Promise<IDataAdapter> {
  switch (config.adapterType) {
    case 'synthetic':
      const adapter = new SyntheticAdapter(config.syntheticDataPath);
      await adapter.initialize();
      return adapter;

    case 'ecc_rfc':
    case 's4_odata':
      throw new Error(
        `Adapter '${config.adapterType}' is not yet implemented. ` +
        `Use 'synthetic' adapter for testing or implement the adapter.`
      );

    default:
      throw new Error(`Unknown adapter type: ${config.adapterType}`);
  }
}

/**
 * Create and configure the MCP server
 */
function createMCPServer(): Server {
  const server = new Server(
    {
      name: 'sap-workflow-mining',
      version: '1.0.0',
    },
    {
      capabilities: {
        tools: {},
      },
    }
  );

  return server;
}

/**
 * Set up request handlers for the MCP server
 */
function setupHandlers(server: Server, adapter: IDataAdapter): void {
  // Register tool list handler
  server.setRequestHandler(ListToolsRequestSchema, async () => {
    return {
      tools: allTools,
    };
  });

  // Register tool call handler
  server.setRequestHandler(CallToolRequestSchema, async (request) => {
    const { name, arguments: args } = request.params;

    try {
      const result = await executeTool(name, adapter, args);

      return {
        content: [
          {
            type: 'text' as const,
            text: JSON.stringify(result, null, 2),
          },
        ],
      };
    } catch (error) {
      // Handle different error types with structured JSON responses

      // Policy violations (row limits, field access, etc.)
      if (error instanceof PolicyViolationError) {
        return {
          content: [
            {
              type: 'text' as const,
              text: JSON.stringify({
                error: 'Policy Violation',
                code: 'POLICY_VIOLATION',
                message: error.message,
                violation: error.violation,
                details: error.details,
              }, null, 2),
            },
          ],
          isError: true,
        };
      }

      // Timeout errors
      if (error instanceof TimeoutError) {
        return {
          content: [
            {
              type: 'text' as const,
              text: JSON.stringify({
                error: 'Timeout',
                code: 'TIMEOUT',
                message: error.message,
                timeout_ms: error.timeoutMs,
              }, null, 2),
            },
          ],
          isError: true,
        };
      }

      // Zod validation errors
      if (error && typeof error === 'object' && 'issues' in error) {
        return {
          content: [
            {
              type: 'text' as const,
              text: JSON.stringify({
                error: 'Validation Error',
                code: 'VALIDATION_ERROR',
                message: 'Invalid tool parameters',
                issues: (error as { issues: unknown[] }).issues,
              }, null, 2),
            },
          ],
          isError: true,
        };
      }

      // Generic errors
      const errorMessage = error instanceof Error ? error.message : String(error);
      const errorName = error instanceof Error ? error.name : 'UnknownError';

      return {
        content: [
          {
            type: 'text' as const,
            text: JSON.stringify({
              error: 'Tool Execution Error',
              code: 'EXECUTION_ERROR',
              error_type: errorName,
              message: errorMessage,
            }, null, 2),
          },
        ],
        isError: true,
      };
    }
  });
}

/**
 * Main entry point
 */
async function main(): Promise<void> {
  const config = getConfig();

  logServerEvent('start', {
    adapter: config.adapterType,
    data_path: config.syntheticDataPath || 'default',
    tools_count: allTools.length,
  });

  try {
    // Create adapter
    const adapter = await createAdapter(config);

    // Create MCP server
    const server = createMCPServer();

    // Set up handlers
    setupHandlers(server, adapter);

    // Set up graceful shutdown
    const shutdown = async (signal: string) => {
      logServerEvent('stop', { signal });
      await adapter.shutdown();
      process.exit(0);
    };

    process.on('SIGINT', () => shutdown('SIGINT'));
    process.on('SIGTERM', () => shutdown('SIGTERM'));

    // Connect to stdio transport
    const transport = new StdioServerTransport();
    await server.connect(transport);

    logServerEvent('ready', {
      adapter: adapter.name,
      tools: allTools.map(t => t.name),
    });

    // Server is now running and waiting for requests via stdio
  } catch (error) {
    logServerEvent('error', {
      message: error instanceof Error ? error.message : String(error),
      stack: error instanceof Error ? error.stack : undefined,
    });
    process.exit(1);
  }
}

// Run the server
main().catch((error) => {
  console.error('Fatal error:', error);
  process.exit(1);
});
