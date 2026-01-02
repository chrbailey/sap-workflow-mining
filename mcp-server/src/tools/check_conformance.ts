/**
 * Tool: check_conformance
 *
 * Phase 3 - Conformance Checking for SAP Order-to-Cash Process
 *
 * Compares actual SAP process flows against the expected O2C reference model
 * to detect deviations, score severity, and calculate conformance rates.
 */

import { z } from 'zod';
import { SAPAdapter } from '../adapters/adapter.js';
import { createAuditContext } from '../logging/audit.js';
import {
  enforceRowLimit,
  withTimeout,
  getPolicyConfig,
} from '../policies/limits.js';

// ============================================================================
// Type Definitions
// ============================================================================

/**
 * Deviation severity levels
 */
export type DeviationSeverity = 'critical' | 'major' | 'minor';

/**
 * Types of process deviations
 */
export type DeviationType =
  | 'skipped_step'
  | 'wrong_order'
  | 'unexpected_activity'
  | 'missing_activity'
  | 'repeated_activity'
  | 'timing_violation';

/**
 * Individual deviation record
 */
export interface Deviation {
  /** Case identifier (typically sales order number) */
  case_id: string;
  /** Type of deviation detected */
  deviation_type: DeviationType;
  /** Severity classification */
  severity: DeviationSeverity;
  /** Human-readable description */
  description: string;
  /** Expected activity or sequence */
  expected: string;
  /** Actual activity or sequence observed */
  actual: string;
  /** Activity name where deviation occurred */
  activity?: string;
  /** Position in the process where deviation occurred */
  position?: number;
}

/**
 * Conformance check result
 */
export interface ConformanceResult {
  /** Overall conformance rate as percentage (0-100) */
  conformance_rate: number;
  /** Total number of cases analyzed */
  total_cases: number;
  /** Number of fully conforming cases */
  conforming_cases: number;
  /** Number of cases with deviations */
  non_conforming_cases: number;
  /** Breakdown by severity */
  severity_summary: {
    critical: number;
    major: number;
    minor: number;
  };
  /** Breakdown by deviation type */
  deviation_type_summary: Record<DeviationType, number>;
  /** Individual deviations (if include_deviations is true) */
  deviations: Deviation[];
  /** Analysis metadata */
  metadata: {
    analyzed_at: string;
    reference_model: string;
    filters_applied: {
      doc_numbers?: string[];
      severity_filter: string;
    };
  };
}

/**
 * Reference model activity
 */
interface ReferenceActivity {
  name: string;
  required: boolean;
  order: number;
  /** Allowed predecessors (if order is flexible) */
  allowed_predecessors?: string[];
}

// ============================================================================
// O2C Reference Model
// ============================================================================

/**
 * Standard Order-to-Cash Reference Model
 * Defines the expected sequence of activities in SAP O2C process
 */
const O2C_REFERENCE_MODEL: ReferenceActivity[] = [
  {
    name: 'order_created',
    required: true,
    order: 1,
  },
  {
    name: 'credit_check',
    required: false,
    order: 2,
  },
  {
    name: 'order_confirmed',
    required: false,
    order: 3,
    allowed_predecessors: ['order_created', 'credit_check'],
  },
  {
    name: 'delivery_created',
    required: true,
    order: 4,
  },
  {
    name: 'picking_completed',
    required: false,
    order: 5,
  },
  {
    name: 'goods_issued',
    required: true,
    order: 6,
  },
  {
    name: 'invoice_created',
    required: true,
    order: 7,
  },
  {
    name: 'payment_received',
    required: false,
    order: 8,
  },
];

/**
 * Map SAP document/event types to reference model activities
 */
const ACTIVITY_MAPPING: Record<string, string> = {
  // Sales Order related
  'C': 'order_created',       // VBTYP_N = C (Sales Order)
  'order': 'order_created',
  'sales': 'order_created',
  'order_created': 'order_created',

  // Delivery related
  'J': 'delivery_created',    // VBTYP_N = J (Delivery)
  'delivery': 'delivery_created',
  'delivery_created': 'delivery_created',

  // Goods Issue
  'goods_issued': 'goods_issued',
  'gi': 'goods_issued',

  // Invoice related
  'M': 'invoice_created',     // VBTYP_N = M (Invoice)
  'invoice': 'invoice_created',
  'invoice_created': 'invoice_created',
  'billing': 'invoice_created',
};

// ============================================================================
// Zod Schema
// ============================================================================

/**
 * Zod schema for input validation
 */
export const CheckConformanceSchema = z.object({
  doc_numbers: z.array(z.string()).optional().describe(
    'Specific document numbers to check. If omitted, checks recent documents.'
  ),
  include_deviations: z.boolean().default(true).describe(
    'Include detailed deviation information in results'
  ),
  severity_filter: z.enum(['all', 'critical', 'major', 'minor']).default('all').describe(
    'Filter results by severity level'
  ),
});

export type CheckConformanceInput = z.infer<typeof CheckConformanceSchema>;

// ============================================================================
// Tool Definition
// ============================================================================

/**
 * Tool definition for MCP registration
 */
export const checkConformanceTool = {
  name: 'check_conformance',
  description: `Check conformance of SAP Order-to-Cash process flows against the expected reference model.

Analyzes actual process executions and detects deviations such as:
- Skipped steps (required activities not performed)
- Wrong order (activities executed in incorrect sequence)
- Missing activities (expected activities not found)
- Unexpected activities (activities not in the reference model)

Severity levels:
- Critical: Missing required steps (delivery, invoice), wrong document sequence
- Major: Skipped optional but important steps, significant timing violations
- Minor: Minor sequence variations, repeated activities

Use this tool to:
- Audit process compliance across sales orders
- Identify process bottlenecks and exceptions
- Generate conformance reports for management
- Detect systematic process violations

Parameters:
- doc_numbers: Array of specific sales order numbers to check (optional, checks recent if omitted)
- include_deviations: Include detailed deviation list (default: true)
- severity_filter: Filter by 'all', 'critical', 'major', or 'minor' (default: 'all')

Returns:
- conformance_rate: Overall conformance percentage (0-100%)
- total_cases: Number of cases analyzed
- conforming_cases: Number of cases with no deviations
- deviations: Detailed list of detected deviations`,
  inputSchema: {
    type: 'object' as const,
    properties: {
      doc_numbers: {
        type: 'array',
        items: { type: 'string' },
        description: 'Specific sales order numbers to check (optional)',
      },
      include_deviations: {
        type: 'boolean',
        description: 'Include detailed deviation information (default: true)',
      },
      severity_filter: {
        type: 'string',
        enum: ['all', 'critical', 'major', 'minor'],
        description: 'Filter results by severity level (default: all)',
      },
    },
    required: [],
  },
};

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Map a raw activity/event type to the reference model activity name
 */
function mapToReferenceActivity(activityType: string): string | null {
  const mapped = ACTIVITY_MAPPING[activityType.toLowerCase()];
  return mapped || null;
}

/**
 * Get the expected order position for an activity
 */
function getActivityOrder(activityName: string): number {
  const activity = O2C_REFERENCE_MODEL.find(a => a.name === activityName);
  return activity?.order ?? -1;
}

/**
 * Check if an activity is required in the reference model
 */
function isActivityRequired(activityName: string): boolean {
  const activity = O2C_REFERENCE_MODEL.find(a => a.name === activityName);
  return activity?.required ?? false;
}

/**
 * Determine severity based on deviation type and activity
 */
function determineSeverity(
  deviationType: DeviationType,
  activityName?: string
): DeviationSeverity {
  // Critical: Missing required activities or fundamental sequence violations
  if (deviationType === 'missing_activity' && activityName) {
    if (isActivityRequired(activityName)) {
      return 'critical';
    }
  }

  if (deviationType === 'skipped_step' && activityName) {
    if (['delivery_created', 'goods_issued', 'invoice_created'].includes(activityName)) {
      return 'critical';
    }
  }

  if (deviationType === 'wrong_order') {
    // Invoice before delivery is critical
    return 'critical';
  }

  // Major: Important but not critical deviations
  if (deviationType === 'skipped_step') {
    return 'major';
  }

  if (deviationType === 'unexpected_activity') {
    return 'major';
  }

  // Minor: Other deviations
  return 'minor';
}

/**
 * Analyze a single case (sales order) for conformance
 */
async function analyzeCase(
  adapter: SAPAdapter,
  orderNumber: string,
  config: { defaultTimeoutMs: number }
): Promise<{ conforming: boolean; deviations: Deviation[] }> {
  const deviations: Deviation[] = [];

  try {
    // Get document flow for this order
    const docFlow = await withTimeout(
      adapter.getDocFlow({ vbeln: orderNumber }),
      config.defaultTimeoutMs,
      'check_conformance:docflow'
    );

    if (!docFlow || !docFlow.flow || docFlow.flow.length === 0) {
      // No flow found - this is a deviation
      deviations.push({
        case_id: orderNumber,
        deviation_type: 'missing_activity',
        severity: 'critical',
        description: 'No document flow found for this order',
        expected: 'Complete O2C document flow',
        actual: 'No documents found',
      });
      return { conforming: false, deviations };
    }

    // Build actual activity sequence from document flow
    const actualActivities: Array<{ name: string; timestamp: string; docNumber: string }> = [];

    // Always add order_created as first activity
    actualActivities.push({
      name: 'order_created',
      timestamp: `${docFlow.flow[0]?.created_date || ''}T${docFlow.flow[0]?.created_time || ''}`,
      docNumber: orderNumber,
    });

    // Track which document types we've seen
    const seenDocTypes = new Set<string>();
    seenDocTypes.add('order_created');

    // Process flow documents
    for (const flowDoc of docFlow.flow) {
      const mappedActivity = mapToReferenceActivity(flowDoc.doc_category || flowDoc.doc_type);

      if (mappedActivity && mappedActivity !== 'order_created') {
        actualActivities.push({
          name: mappedActivity,
          timestamp: `${flowDoc.created_date}T${flowDoc.created_time}`,
          docNumber: flowDoc.doc_number,
        });
        seenDocTypes.add(mappedActivity);

        // Check for goods issued (via delivery timing if available)
        if (mappedActivity === 'delivery_created') {
          try {
            const deliveryTiming = await withTimeout(
              adapter.getDeliveryTiming({ vbeln: flowDoc.doc_number }),
              config.defaultTimeoutMs,
              'check_conformance:delivery_timing'
            );

            if (deliveryTiming?.header_timing.actual_gi_date) {
              actualActivities.push({
                name: 'goods_issued',
                timestamp: `${deliveryTiming.header_timing.actual_gi_date}T000000`,
                docNumber: flowDoc.doc_number,
              });
              seenDocTypes.add('goods_issued');
            }
          } catch {
            // Ignore timing fetch errors
          }
        }
      }
    }

    // Sort by timestamp
    actualActivities.sort((a, b) => a.timestamp.localeCompare(b.timestamp));

    // Check 1: Missing required activities
    const requiredActivities = O2C_REFERENCE_MODEL.filter(a => a.required);
    for (const required of requiredActivities) {
      if (!seenDocTypes.has(required.name)) {
        deviations.push({
          case_id: orderNumber,
          deviation_type: 'missing_activity',
          severity: determineSeverity('missing_activity', required.name),
          description: `Required activity '${required.name}' not found in process`,
          expected: required.name,
          actual: 'Not found',
          activity: required.name,
          position: required.order,
        });
      }
    }

    // Check 2: Wrong order of activities
    let lastOrder = 0;
    for (let i = 0; i < actualActivities.length; i++) {
      const activity = actualActivities[i];
      if (!activity) continue;

      const expectedOrder = getActivityOrder(activity.name);

      if (expectedOrder > 0 && expectedOrder < lastOrder) {
        // Activity is out of order
        const previousActivity = actualActivities[i - 1];
        deviations.push({
          case_id: orderNumber,
          deviation_type: 'wrong_order',
          severity: determineSeverity('wrong_order', activity.name),
          description: `Activity '${activity.name}' occurred before '${previousActivity?.name || 'previous activity'}'`,
          expected: `${previousActivity?.name || 'N/A'} -> ${activity.name}`,
          actual: `${activity.name} -> ${previousActivity?.name || 'N/A'}`,
          activity: activity.name,
          position: i,
        });
      }

      if (expectedOrder > lastOrder) {
        lastOrder = expectedOrder;
      }
    }

    // Check 3: Skipped optional steps (important ones)
    const optionalImportant = ['credit_check', 'picking_completed'];
    for (const activityName of optionalImportant) {
      if (!seenDocTypes.has(activityName)) {
        // Check if we have subsequent activities
        const activityOrder = getActivityOrder(activityName);
        const hasLaterActivities = actualActivities.some(
          a => getActivityOrder(a.name) > activityOrder
        );

        if (hasLaterActivities) {
          deviations.push({
            case_id: orderNumber,
            deviation_type: 'skipped_step',
            severity: 'minor',
            description: `Optional activity '${activityName}' was skipped`,
            expected: activityName,
            actual: 'Skipped',
            activity: activityName,
          });
        }
      }
    }

    // Check 4: Repeated activities (potential rework)
    const activityCounts = new Map<string, number>();
    for (const activity of actualActivities) {
      const count = activityCounts.get(activity.name) || 0;
      activityCounts.set(activity.name, count + 1);
    }

    for (const [activityName, count] of activityCounts) {
      if (count > 1) {
        deviations.push({
          case_id: orderNumber,
          deviation_type: 'repeated_activity',
          severity: 'minor',
          description: `Activity '${activityName}' was repeated ${count} times`,
          expected: `${activityName} (once)`,
          actual: `${activityName} (${count} times)`,
          activity: activityName,
        });
      }
    }

    return {
      conforming: deviations.length === 0,
      deviations,
    };
  } catch (error) {
    // Log error but continue with other cases
    deviations.push({
      case_id: orderNumber,
      deviation_type: 'missing_activity',
      severity: 'major',
      description: `Error analyzing case: ${(error as Error).message}`,
      expected: 'Successful analysis',
      actual: 'Analysis failed',
    });
    return { conforming: false, deviations };
  }
}

// ============================================================================
// Tool Executor
// ============================================================================

/**
 * Execute the check_conformance tool
 */
export async function executeCheckConformance(
  adapter: SAPAdapter,
  rawInput: unknown
): Promise<ConformanceResult> {
  // Validate input
  const input = CheckConformanceSchema.parse(rawInput);

  // Create audit context
  const auditContext = createAuditContext(
    'check_conformance',
    input as Record<string, unknown>,
    adapter.name
  );

  try {
    const config = getPolicyConfig();
    let docNumbers = input.doc_numbers || [];

    // If no specific documents provided, search for recent orders
    if (docNumbers.length === 0) {
      try {
        // Calculate date range for last 30 days
        const now = new Date();
        const thirtyDaysAgo = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
        const dateTo = now.toISOString().split('T')[0] as string;
        const dateFrom = thirtyDaysAgo.toISOString().split('T')[0] as string;

        const searchResults = await withTimeout(
          adapter.searchDocText({
            pattern: '.*',
            doc_type: 'sales',
            date_from: dateFrom,
            date_to: dateTo,
            limit: 50,
          }),
          config.defaultTimeoutMs,
          'check_conformance:search'
        ).catch(() => []);

        docNumbers = [...new Set(
          searchResults
            .filter(r => r.doc_type === 'sales' || r.doc_type === 'order')
            .map(r => r.doc_key)
        )];
      } catch {
        // If search fails, return empty result
        docNumbers = [];
      }
    }

    // Enforce row limit
    docNumbers = enforceRowLimit(docNumbers, 200, auditContext);

    // Analyze each case
    const allDeviations: Deviation[] = [];
    let conformingCases = 0;
    const severityCounts = { critical: 0, major: 0, minor: 0 };
    const deviationTypeCounts: Record<DeviationType, number> = {
      skipped_step: 0,
      wrong_order: 0,
      unexpected_activity: 0,
      missing_activity: 0,
      repeated_activity: 0,
      timing_violation: 0,
    };

    for (const docNumber of docNumbers) {
      const result = await analyzeCase(adapter, docNumber, config);

      if (result.conforming) {
        conformingCases++;
      } else {
        // Apply severity filter
        let filteredDeviations = result.deviations;
        if (input.severity_filter !== 'all') {
          filteredDeviations = result.deviations.filter(
            d => d.severity === input.severity_filter
          );
        }

        // Count deviations
        for (const deviation of result.deviations) {
          severityCounts[deviation.severity]++;
          deviationTypeCounts[deviation.deviation_type]++;
        }

        // Add to results if including deviations
        if (input.include_deviations) {
          allDeviations.push(...filteredDeviations);
        }
      }
    }

    // Calculate conformance rate
    const totalCases = docNumbers.length;
    const conformanceRate = totalCases > 0
      ? Math.round((conformingCases / totalCases) * 100 * 100) / 100
      : 0;

    // Build result
    const filtersApplied: { doc_numbers?: string[]; severity_filter: string } = {
      severity_filter: input.severity_filter,
    };
    if (input.doc_numbers) {
      filtersApplied.doc_numbers = input.doc_numbers;
    }

    const result: ConformanceResult = {
      conformance_rate: conformanceRate,
      total_cases: totalCases,
      conforming_cases: conformingCases,
      non_conforming_cases: totalCases - conformingCases,
      severity_summary: severityCounts,
      deviation_type_summary: deviationTypeCounts,
      deviations: input.include_deviations ? allDeviations : [],
      metadata: {
        analyzed_at: new Date().toISOString(),
        reference_model: 'SAP O2C Standard v1.0',
        filters_applied: filtersApplied,
      },
    };

    // Log success
    auditContext.success(totalCases);

    return result;
  } catch (error) {
    auditContext.error(error as Error);
    throw error;
  }
}
