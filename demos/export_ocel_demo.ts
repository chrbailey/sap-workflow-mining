#!/usr/bin/env npx tsx
/**
 * Demo: export_ocel Tool
 *
 * This demo shows how to export SAP Order-to-Cash data in OCEL 2.0 format
 * for use with process mining tools like PM4Py, Celonis, etc.
 *
 * Prerequisites:
 *   - No external dependencies - uses synthetic adapter
 *
 * Usage:
 *   cd mcp-server
 *   npx tsx ../demos/export_ocel_demo.ts
 */

import { executeExportOcel } from '../mcp-server/src/tools/export_ocel.js';
import { SyntheticAdapter } from '../mcp-server/src/adapters/synthetic/index.js';

// ANSI colors for terminal output
const colors = {
  reset: '\x1b[0m',
  bright: '\x1b[1m',
  dim: '\x1b[2m',
  cyan: '\x1b[36m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  magenta: '\x1b[35m',
};

function printHeader(text: string): void {
  console.log(`\n${colors.bright}${colors.cyan}${'═'.repeat(70)}${colors.reset}`);
  console.log(`${colors.bright}${colors.cyan}  ${text}${colors.reset}`);
  console.log(`${colors.cyan}${'═'.repeat(70)}${colors.reset}\n`);
}

function printSection(title: string): void {
  console.log(`${colors.bright}${colors.yellow}${title}${colors.reset}`);
}

async function runDemo(): Promise<void> {
  printHeader('SAP Workflow Mining - export_ocel Demo');

  // Create synthetic adapter
  console.log(`${colors.dim}Creating synthetic SAP adapter...${colors.reset}`);
  const adapter = new SyntheticAdapter();
  await adapter.initialize();
  console.log(`${colors.green}✓ Adapter ready${colors.reset}\n`);

  printHeader('OCEL 2.0 Export');

  console.log(`${colors.dim}Exporting Order-to-Cash data in OCEL 2.0 format...${colors.reset}\n`);

  try {
    const startTime = Date.now();

    const result = await executeExportOcel(adapter, {
      date_from: '2024-01-01',
      date_to: '2024-12-31',
      output_format: 'json',
      include_items: true,
    });

    const duration = ((Date.now() - startTime) / 1000).toFixed(2);

    // Display OCEL structure summary
    printSection('OCEL 2.0 Structure:');
    console.log(`${colors.dim}─────────────────────────────────────${colors.reset}`);

    const objectTypeNames = Object.keys(result.objectTypes);
    const eventTypeNames = Object.keys(result.eventTypes);
    const objectEntries = Object.entries(result.objects);
    const eventEntries = Object.entries(result.events);

    console.log(`\n${colors.bright}Object Types:${colors.reset}`);
    for (const typeName of objectTypeNames) {
      const objType = result.objectTypes[typeName];
      const count = objectEntries.filter(([_, o]) => o.type === typeName).length;
      console.log(`  ${colors.cyan}•${colors.reset} ${typeName}: ${count} objects`);
      if (objType.attributes && objType.attributes.length > 0) {
        console.log(`    ${colors.dim}Attributes: ${objType.attributes.map(a => a.name).join(', ')}${colors.reset}`);
      }
    }

    console.log(`\n${colors.bright}Event Types:${colors.reset}`);
    for (const typeName of eventTypeNames) {
      const count = eventEntries.filter(([_, e]) => e.type === typeName).length;
      console.log(`  ${colors.magenta}•${colors.reset} ${typeName}: ${count} events`);
    }

    console.log(`\n${colors.bright}Summary:${colors.reset}`);
    console.log(`  Total Objects: ${colors.green}${objectEntries.length}${colors.reset}`);
    console.log(`  Total Events: ${colors.green}${eventEntries.length}${colors.reset}`);

    // Show sample event
    if (eventEntries.length > 0) {
      console.log(`\n${colors.bright}Sample Event:${colors.reset}`);
      const [id, sample] = eventEntries[0];
      console.log(`${colors.dim}${id}: ${JSON.stringify(sample, null, 2)}${colors.reset}`);
    }

    // Show sample object
    if (objectEntries.length > 0) {
      console.log(`\n${colors.bright}Sample Object:${colors.reset}`);
      const [id, sample] = objectEntries[0];
      console.log(`${colors.dim}${id}: ${JSON.stringify(sample, null, 2)}${colors.reset}`);
    }

    console.log(`\n${colors.dim}─────────────────────────────────────${colors.reset}`);
    console.log(`${colors.dim}Export Time: ${duration}s${colors.reset}`);

  } catch (error) {
    console.error(`\n${colors.bright}\x1b[31mError:${colors.reset}`, error);
    process.exit(1);
  }

  printHeader('Demo Complete');
  console.log('The OCEL 2.0 export can be used with:');
  console.log(`  ${colors.dim}• PM4Py - Python process mining library${colors.reset}`);
  console.log(`  ${colors.dim}• Celonis - Enterprise process mining platform${colors.reset}`);
  console.log(`  ${colors.dim}• ProM - Academic process mining framework${colors.reset}`);
  console.log(`  ${colors.dim}• Any OCEL 2.0 compliant tool${colors.reset}\n`);
}

runDemo();
