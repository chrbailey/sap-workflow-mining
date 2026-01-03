#!/usr/bin/env npx tsx
/**
 * Demo: export_ocel Tool with BPI Challenge 2019 Data
 *
 * Demonstrates exporting SAP P2P process data to OCEL 2.0 format
 * for use with PM4Py, Celonis, and other process mining tools.
 *
 * Usage:
 *   npx tsx demos/export_ocel_demo.ts
 *   npx tsx demos/export_ocel_demo.ts --max-traces=1000
 */

import { BPIAdapter } from '../mcp-server/src/adapters/bpi/index.js';
import { executeExportOcel } from '../mcp-server/src/tools/export_ocel.js';
import { writeFile } from 'fs/promises';
import { join } from 'path';

// ANSI colors
const colors = {
  reset: '\x1b[0m',
  bright: '\x1b[1m',
  dim: '\x1b[2m',
  cyan: '\x1b[36m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
};

function printHeader(text: string): void {
  console.log(`\n${colors.bright}${colors.cyan}${'═'.repeat(70)}${colors.reset}`);
  console.log(`${colors.bright}${colors.cyan}  ${text}${colors.reset}`);
  console.log(`${colors.cyan}${'═'.repeat(70)}${colors.reset}\n`);
}

async function main() {
  printHeader('OCEL 2.0 Export Demo - BPI Challenge 2019');

  // Parse args
  const args = process.argv.slice(2);
  let maxTraces = 0;
  let outputFile = '';

  for (const arg of args) {
    if (arg.startsWith('--max-traces=')) {
      maxTraces = parseInt(arg.split('=')[1] || '0', 10);
    } else if (arg.startsWith('--output=')) {
      outputFile = arg.split('=')[1] || '';
    }
  }

  // Initialize adapter
  console.log(`${colors.dim}Loading BPI Challenge 2019 data...${colors.reset}`);
  const adapter = new BPIAdapter();
  await adapter.initialize();

  const stats = adapter.getStats();
  if (stats) {
    console.log(`${colors.green}✓ Loaded ${stats.processed_cases.toLocaleString()} cases with ${stats.total_events.toLocaleString()} events${colors.reset}`);
    console.log(`${colors.dim}  Activities: ${stats.unique_activities} | Vendors: ${stats.unique_vendors.toLocaleString()}${colors.reset}\n`);
  }

  // Export to OCEL 2.0
  printHeader('Exporting to OCEL 2.0 Format');

  console.log(`${colors.dim}Export options:${colors.reset}`);
  console.log(`  Max traces: ${maxTraces || 'all'}`);
  console.log(`  Include relationships: true`);
  console.log(`  Include items: true\n`);

  const startTime = Date.now();

  const result = await executeExportOcel(adapter, {
    max_traces: maxTraces,
    include_relationships: true,
    include_items: true,
    output_format: 'json',
  });

  const duration = ((Date.now() - startTime) / 1000).toFixed(2);

  // Print results
  printHeader('Export Results');

  console.log(`${colors.bright}Format:${colors.reset} ${result.format}`);
  console.log(`${colors.bright}Process Type:${colors.reset} ${result.processType}\n`);

  console.log(`${colors.bright}Statistics:${colors.reset}`);
  console.log(`  Total Events: ${result.stats.totalEvents.toLocaleString()}`);
  console.log(`  Total Objects: ${result.stats.totalObjects.toLocaleString()}`);
  console.log(`  Event Types: ${result.stats.eventTypes}`);
  console.log(`  Object Types: ${result.stats.objectTypes}\n`);

  console.log(`${colors.dim}Export Time: ${duration}s${colors.reset}\n`);

  // Show sample of OCEL structure
  if (result.ocel) {
    printHeader('OCEL 2.0 Structure Sample');

    console.log(`${colors.bright}Object Types:${colors.reset}`);
    for (const objType of result.ocel.objectTypes) {
      console.log(`  - ${objType.name}`);
      for (const attr of objType.attributes.slice(0, 3)) {
        console.log(`      ${colors.dim}${attr.name}: ${attr.type}${colors.reset}`);
      }
    }

    console.log(`\n${colors.bright}Event Types (first 5):${colors.reset}`);
    for (const eventType of result.ocel.eventTypes.slice(0, 5)) {
      console.log(`  - ${eventType.name}`);
    }
    if (result.ocel.eventTypes.length > 5) {
      console.log(`  ${colors.dim}... and ${result.ocel.eventTypes.length - 5} more${colors.reset}`);
    }

    console.log(`\n${colors.bright}Sample Events (first 3):${colors.reset}`);
    for (const event of result.ocel.events.slice(0, 3)) {
      console.log(`  [${event.id}] ${event.type}`);
      console.log(`      ${colors.dim}Time: ${event.time}${colors.reset}`);
      console.log(`      ${colors.dim}Related objects: ${event.relationships.map(r => r.objectId).join(', ')}${colors.reset}`);
    }

    console.log(`\n${colors.bright}Sample Objects (first 3):${colors.reset}`);
    for (const obj of result.ocel.objects.slice(0, 3)) {
      console.log(`  [${obj.id}] ${obj.type}`);
      const attrSummary = obj.attributes.slice(0, 2).map(a => `${a.name}=${a.value}`).join(', ');
      console.log(`      ${colors.dim}${attrSummary}${colors.reset}`);
    }
  }

  // Save to file if requested
  const filename = outputFile || join(process.cwd(), 'output', 'bpi_2019_ocel.json');
  printHeader('Saving OCEL File');

  try {
    const jsonContent = JSON.stringify(result.ocel, null, 2);
    await writeFile(filename, jsonContent, 'utf-8');
    console.log(`${colors.green}✓ Saved to: ${filename}${colors.reset}`);
    console.log(`${colors.dim}  File size: ${(jsonContent.length / 1024 / 1024).toFixed(2)} MB${colors.reset}`);
  } catch (error) {
    console.log(`${colors.yellow}Could not save file: ${(error as Error).message}${colors.reset}`);
  }

  // Shutdown
  await adapter.shutdown();

  printHeader('Demo Complete');
  console.log('The OCEL 2.0 file can be imported into:');
  console.log(`  ${colors.dim}• PM4Py: pm4py.read_ocel('bpi_2019_ocel.json')${colors.reset}`);
  console.log(`  ${colors.dim}• Celonis: OCEL 2.0 connector${colors.reset}`);
  console.log(`  ${colors.dim}• Apromore: Object-centric log import${colors.reset}\n`);
}

main().catch(console.error);
