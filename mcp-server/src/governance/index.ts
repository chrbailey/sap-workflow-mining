// ═══════════════════════════════════════════════════════════════════════════
// SAP WORKFLOW MINING - PROMPTSPEAK GOVERNANCE
// ═══════════════════════════════════════════════════════════════════════════
// PromptSpeak-based governance layer for SAP MCP Server
//
// This module provides:
// - Pre-execution blocking via circuit breaker
// - Frame-based access control
// - Human-in-the-loop holds for risky operations
// - Audit logging for compliance
//
// Usage:
//   import { gatekeeper, wrapWithGovernance } from './governance/index.js';
//
//   // Wrap a tool execution
//   const result = await wrapWithGovernance(
//     'search_doc_text',
//     { pattern: 'credit hold', date_from: '2024-01-01' },
//     '⊕◐▲α',  // strict, operational, analyze, primary
//     async (params) => adapter.searchDocText(params)
//   );
// ═══════════════════════════════════════════════════════════════════════════

export * from './types.js';
export * from './validator.js';
export { CircuitBreaker } from './circuit-breaker.js';
export { HoldManager } from './hold-manager.js';
export { Gatekeeper, gatekeeper } from './gatekeeper.js';

import { gatekeeper } from './gatekeeper.js';
import { defaultSAPFrame } from './validator.js';
import type { ExecuteResult } from './types.js';

/**
 * Wrap a tool execution with PromptSpeak governance.
 *
 * This is the main integration point for SAP tools. It:
 * 1. Checks the circuit breaker (blocks halted agents)
 * 2. Validates the frame (blocks invalid frames)
 * 3. Checks for hold triggers (pauses risky operations)
 * 4. Executes the tool if all checks pass
 *
 * @param tool - The SAP tool name (e.g., 'search_doc_text')
 * @param params - Tool parameters
 * @param frame - PromptSpeak frame (e.g., '⊕◐▲α')
 * @param executor - The actual tool execution function
 * @param agentId - Agent identifier (defaults to 'default')
 *
 * @returns Promise with either the tool result or governance error
 */
export async function wrapWithGovernance<T>(
  tool: string,
  params: Record<string, unknown>,
  frame: string | undefined,
  executor: (params: Record<string, unknown>) => Promise<T>,
  agentId: string = 'default'
): Promise<{
  success: boolean;
  result?: T;
  held?: boolean;
  holdId?: string;
  error?: string;
  governance: ExecuteResult;
}> {
  // Get or generate frame
  const effectiveFrame = frame || defaultSAPFrame(tool);

  // Run through governance pipeline
  const governance = gatekeeper.execute({
    agentId,
    frame: effectiveFrame,
    tool,
    params,
  });

  // If held, return hold info
  if (governance.held) {
    return {
      success: false,
      held: true,
      ...(governance.holdRequest?.holdId ? { holdId: governance.holdRequest.holdId } : {}),
      error: `Operation held for approval: ${governance.holdRequest?.reason}`,
      governance,
    };
  }

  // If blocked, return error
  if (!governance.allowed) {
    return {
      success: false,
      error: governance.error || 'Operation blocked by governance',
      governance,
    };
  }

  // Execute the actual tool
  try {
    const result = await executor(params);
    return {
      success: true,
      result,
      governance,
    };
  } catch (error) {
    // Record failure in circuit breaker
    const circuitBreaker = gatekeeper['circuitBreaker'];
    circuitBreaker.recordFailure(agentId);

    return {
      success: false,
      error: error instanceof Error ? error.message : String(error),
      governance,
    };
  }
}

/**
 * Generate documentation for SAP governance frames.
 */
export function getFrameDocumentation(): string {
  return `
# SAP Governance Frames (PromptSpeak)

## Frame Format
A frame consists of symbols: MODE + DOMAIN + ACTION + ENTITY

Example: ⊕◐◀α (strict operational retrieve primary)

## Modes
- ⊕ (strict)   - Exact compliance required
- ⊘ (neutral)  - Standard operation
- ⊖ (flexible) - Allow interpretation
- ⊗ (forbidden)- Block all actions

## Domains
- ◊ (financial)   - Monetary data (invoices, values)
- ◐ (operational) - Process data (orders, deliveries)

## Actions
- ◀ (retrieve) - Read data
- ▲ (analyze)  - Search/analyze patterns
- ● (validate) - Check/verify data

## Entities
- α (primary)   - Main agent
- β (secondary) - Delegated agent
- γ (tertiary)  - Sub-delegated agent

## SAP Tool Mappings
| Tool                  | Default Frame |
|-----------------------|---------------|
| search_doc_text       | ⊘◐▲α          |
| get_doc_text          | ⊘◐◀α          |
| get_doc_flow          | ⊘◐◀α          |
| get_sales_doc_header  | ⊘◊◀α          |
| get_sales_doc_items   | ⊘◐◀α          |
| get_delivery_timing   | ⊘◐◀α          |
| get_invoice_timing    | ⊘◊◀α          |
| get_master_stub       | ⊘◐●α          |

## Hold Triggers
Operations are held for human approval when:
- Date range exceeds 90 days
- Row limit exceeds 500
- Text search matches sensitive patterns
`.trim();
}
