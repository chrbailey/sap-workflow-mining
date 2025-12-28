/**
 * Audit Logging Module
 *
 * Re-exports from audit-logger for backward compatibility.
 */

export {
  AuditContext,
  createAuditContext,
  generateRequestId,
  logToolStart,
  logToolSuccess,
  logToolError,
  logPolicyViolation,
  logServerEvent,
  auditLogger,
} from './audit-logger.js';

export type { AuditLogEntry } from './audit-logger.js';
