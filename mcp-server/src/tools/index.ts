/**
 * Tool Registry
 *
 * Central export point for all MCP tools.
 * Each tool includes its definition (for MCP registration) and executor function.
 */

// Tool 1: Search Document Text
export {
  searchDocTextTool,
  executeSearchDocText,
  SearchDocTextSchema,
  type SearchDocTextInput,
} from './search_doc_text.js';

// Tool 2: Get Document Text
export {
  getDocTextTool,
  executeGetDocText,
  GetDocTextSchema,
  type GetDocTextInput,
} from './get_doc_text.js';

// Tool 3: Get Document Flow
export {
  getDocFlowTool,
  executeGetDocFlow,
  GetDocFlowSchema,
  type GetDocFlowInput,
} from './get_doc_flow.js';

// Tool 4: Get Sales Document Header
export {
  getSalesDocHeaderTool,
  executeGetSalesDocHeader,
  GetSalesDocHeaderSchema,
  type GetSalesDocHeaderInput,
} from './get_sales_doc_header.js';

// Tool 5: Get Sales Document Items
export {
  getSalesDocItemsTool,
  executeGetSalesDocItems,
  GetSalesDocItemsSchema,
  type GetSalesDocItemsInput,
} from './get_sales_doc_items.js';

// Tool 6: Get Delivery Timing
export {
  getDeliveryTimingTool,
  executeGetDeliveryTiming,
  GetDeliveryTimingSchema,
  type GetDeliveryTimingInput,
} from './get_delivery_timing.js';

// Tool 7: Get Invoice Timing
export {
  getInvoiceTimingTool,
  executeGetInvoiceTiming,
  GetInvoiceTimingSchema,
  type GetInvoiceTimingInput,
} from './get_invoice_timing.js';

// Tool 8: Get Master Stub
export {
  getMasterStubTool,
  executeGetMasterStub,
  GetMasterStubSchema,
  type GetMasterStubInput,
} from './get_master_stub.js';

// Tool 9: Ask Process (Natural Language Interface)
export {
  askProcessTool,
  executeAskProcess,
  AskProcessSchema,
  type AskProcessInput,
} from './ask_process.js';

// Tool 10: Export OCEL
export {
  exportOcelTool,
  executeExportOcel,
  ExportOcelSchema,
  type ExportOcelInput,
} from './export_ocel.js';

// Tool 11: Visualize Process
export {
  visualizeProcessTool,
  executeVisualizeProcess,
  VisualizeProcessSchema,
  type VisualizeProcessInput,
} from './visualize_process.js';

// Tool 12: Check Conformance (Phase 3)
export {
  checkConformanceTool,
  executeCheckConformance,
  CheckConformanceSchema,
  type CheckConformanceInput,
  type ConformanceResult,
  type Deviation,
  type DeviationSeverity,
  type DeviationType,
} from './check_conformance.js';

// Tool 13: Predict Outcome (Phase 5)
export {
  predictOutcomeTool,
  executePredictOutcome,
  PredictOutcomeSchema,
  type PredictOutcomeInput,
  type PredictionResult,
  type Prediction,
  type PredictionAlert,
  type PredictionFactor,
  type PredictionType,
  type RiskLevel,
  type ModelInfo,
} from './predict_outcome.js';

/**
 * All tool definitions for MCP registration
 */
import { searchDocTextTool } from './search_doc_text.js';
import { getDocTextTool } from './get_doc_text.js';
import { getDocFlowTool } from './get_doc_flow.js';
import { getSalesDocHeaderTool } from './get_sales_doc_header.js';
import { getSalesDocItemsTool } from './get_sales_doc_items.js';
import { getDeliveryTimingTool } from './get_delivery_timing.js';
import { getInvoiceTimingTool } from './get_invoice_timing.js';
import { getMasterStubTool } from './get_master_stub.js';
import { askProcessTool } from './ask_process.js';
import { exportOcelTool } from './export_ocel.js';
import { visualizeProcessTool } from './visualize_process.js';
import { checkConformanceTool } from './check_conformance.js';
import { predictOutcomeTool } from './predict_outcome.js';

export const allTools = [
  searchDocTextTool,
  getDocTextTool,
  getDocFlowTool,
  getSalesDocHeaderTool,
  getSalesDocItemsTool,
  getDeliveryTimingTool,
  getInvoiceTimingTool,
  getMasterStubTool,
  askProcessTool,
  exportOcelTool,
  visualizeProcessTool,
  checkConformanceTool,
  predictOutcomeTool,
];

/**
 * Tool executor map for routing
 */
import { executeSearchDocText } from './search_doc_text.js';
import { executeGetDocText } from './get_doc_text.js';
import { executeGetDocFlow } from './get_doc_flow.js';
import { executeGetSalesDocHeader } from './get_sales_doc_header.js';
import { executeGetSalesDocItems } from './get_sales_doc_items.js';
import { executeGetDeliveryTiming } from './get_delivery_timing.js';
import { executeGetInvoiceTiming } from './get_invoice_timing.js';
import { executeGetMasterStub } from './get_master_stub.js';
import { executeAskProcess } from './ask_process.js';
import { executeExportOcel } from './export_ocel.js';
import { executeVisualizeProcess } from './visualize_process.js';
import { executeCheckConformance } from './check_conformance.js';
import { executePredictOutcome } from './predict_outcome.js';
import { SAPAdapter } from '../adapters/adapter.js';

export type ToolExecutor = (adapter: SAPAdapter, input: unknown) => Promise<unknown>;

export const toolExecutors: Record<string, ToolExecutor> = {
  search_doc_text: executeSearchDocText,
  get_doc_text: executeGetDocText,
  get_doc_flow: executeGetDocFlow,
  get_sales_doc_header: executeGetSalesDocHeader,
  get_sales_doc_items: executeGetSalesDocItems,
  get_delivery_timing: executeGetDeliveryTiming,
  get_invoice_timing: executeGetInvoiceTiming,
  get_master_stub: executeGetMasterStub,
  ask_process: executeAskProcess,
  export_ocel: executeExportOcel,
  visualize_process: executeVisualizeProcess,
  check_conformance: executeCheckConformance,
  predict_outcome: executePredictOutcome,
};

/**
 * Execute a tool by name
 */
export async function executeTool(
  toolName: string,
  adapter: SAPAdapter,
  input: unknown
): Promise<unknown> {
  const executor = toolExecutors[toolName];
  if (!executor) {
    throw new Error(`Unknown tool: ${toolName}`);
  }
  return executor(adapter, input);
}
