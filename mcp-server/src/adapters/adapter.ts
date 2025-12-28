/**
 * SAP Adapter Module
 *
 * Re-exports from adapter-interface for backward compatibility.
 * Import from this file or directly from adapter-interface.ts.
 */

export {
  IDataAdapter,
  BaseDataAdapter,
  AdapterFactory,
  adapterRegistry,
  registerAdapter,
  getAdapter,
  listAdapters,
} from './adapter-interface.js';

// Legacy alias for backward compatibility
export { IDataAdapter as SAPAdapter } from './adapter-interface.js';
export { BaseDataAdapter as BaseSAPAdapter } from './adapter-interface.js';
