/**
 * Demo: Conformance Checking with BPI Challenge 2019 Data
 *
 * This demo shows how to check conformance of P2P processes
 * against reference models using real event log data.
 *
 * Usage:
 *   npx tsx demos/check_conformance_bpi_demo.ts [max_traces]
 *
 * Arguments:
 *   max_traces - Maximum number of traces to analyze (default: 100)
 */

import { BPIAdapter } from '../mcp-server/src/adapters/bpi/index.js';
import {
  createChecker,
  Trace,
  listModels,
  P2P_SIMPLE_MODEL,
  P2P_DETAILED_MODEL,
} from '../mcp-server/src/conformance/index.js';

async function main() {
  const maxTraces = parseInt(process.argv[2] || '100', 10);

  console.log('═══════════════════════════════════════════════════════════════════════');
  console.log('  CONFORMANCE CHECKING DEMO - BPI Challenge 2019 P2P Data');
  console.log('═══════════════════════════════════════════════════════════════════════');
  console.log();

  // List available models
  console.log('Available Reference Models:');
  for (const model of listModels()) {
    console.log(`  - ${model.id}: ${model.name} (${model.processType})`);
    console.log(`    ${model.description}`);
  }
  console.log();

  // Load BPI data via adapter
  console.log('Loading BPI Challenge 2019 data...');
  const adapter = new BPIAdapter({ dataDir: 'data/bpi' });
  await adapter.initialize();

  const stats = adapter.getStats();
  if (stats) {
    console.log(`Loaded ${stats.processed_cases} traces with ${stats.total_events} events`);
  }
  console.log();

  // Get traces from adapter
  const bpiTraces = adapter.getTraces();
  console.log(`Adapter loaded ${bpiTraces.length} traces`);

  // Convert to conformance checker format
  const traces: Trace[] = bpiTraces.slice(0, maxTraces).map(bpiTrace => ({
    caseId: bpiTrace.case_id,
    events: bpiTrace.events.map(event => ({
      activity: event.activity,
      timestamp: event.timestamp,
      attributes: {
        user: event.user,
        org: event.org,
      },
    })),
  }));

  console.log(`Analyzing ${traces.length} traces...`);
  console.log();

  // Run conformance check with simple model
  console.log('─────────────────────────────────────────────────────────────────────────');
  console.log('  Analysis with P2P Simple Model');
  console.log('  (PO → Goods Receipt → Invoice → Payment)');
  console.log('─────────────────────────────────────────────────────────────────────────');

  const simpleChecker = createChecker(P2P_SIMPLE_MODEL);
  const simpleResult = simpleChecker.analyzeTraces(traces);

  console.log();
  console.log(`Conformance Rate: ${simpleResult.conformance_rate}%`);
  console.log(`Fitness Score: ${simpleResult.fitness_score}`);
  console.log(`Total Cases: ${simpleResult.total_cases}`);
  console.log(`Conforming Cases: ${simpleResult.conforming_cases}`);
  console.log(`Non-Conforming Cases: ${simpleResult.non_conforming_cases}`);
  console.log();

  console.log('Severity Summary:');
  console.log(`  Critical: ${simpleResult.severity_summary.critical}`);
  console.log(`  Major: ${simpleResult.severity_summary.major}`);
  console.log(`  Minor: ${simpleResult.severity_summary.minor}`);
  console.log();

  console.log('Deviation Type Summary:');
  for (const [type, count] of Object.entries(simpleResult.deviation_type_summary)) {
    if (count > 0) {
      console.log(`  ${type}: ${count}`);
    }
  }
  console.log();

  console.log('Top Deviation Patterns:');
  for (const pattern of simpleResult.top_deviations.slice(0, 5)) {
    console.log(`  [${pattern.severity.toUpperCase()}] ${pattern.pattern}: ${pattern.count} occurrences`);
  }
  console.log();

  // Run conformance check with detailed model
  console.log('─────────────────────────────────────────────────────────────────────────');
  console.log('  Analysis with P2P Detailed Model');
  console.log('  (PR → Approval → PO → GR → Invoice → 3-Way Match → Payment)');
  console.log('─────────────────────────────────────────────────────────────────────────');

  const detailedChecker = createChecker(P2P_DETAILED_MODEL);
  const detailedResult = detailedChecker.analyzeTraces(traces);

  console.log();
  console.log(`Conformance Rate: ${detailedResult.conformance_rate}%`);
  console.log(`Fitness Score: ${detailedResult.fitness_score}`);
  console.log(`Total Cases: ${detailedResult.total_cases}`);
  console.log(`Conforming Cases: ${detailedResult.conforming_cases}`);
  console.log(`Non-Conforming Cases: ${detailedResult.non_conforming_cases}`);
  console.log();

  console.log('Severity Summary:');
  console.log(`  Critical: ${detailedResult.severity_summary.critical}`);
  console.log(`  Major: ${detailedResult.severity_summary.major}`);
  console.log(`  Minor: ${detailedResult.severity_summary.minor}`);
  console.log();

  console.log('Top Deviation Patterns:');
  for (const pattern of detailedResult.top_deviations.slice(0, 5)) {
    console.log(`  [${pattern.severity.toUpperCase()}] ${pattern.pattern}: ${pattern.count} occurrences`);
  }
  console.log();

  // Show sample deviations
  console.log('─────────────────────────────────────────────────────────────────────────');
  console.log('  Sample Deviations (first 10)');
  console.log('─────────────────────────────────────────────────────────────────────────');
  console.log();

  for (const deviation of detailedResult.deviations.slice(0, 10)) {
    console.log(`Case ${deviation.case_id}:`);
    console.log(`  Type: ${deviation.deviation_type} [${deviation.severity.toUpperCase()}]`);
    console.log(`  ${deviation.description}`);
    console.log(`  Expected: ${deviation.expected}`);
    console.log(`  Actual: ${deviation.actual}`);
    console.log();
  }

  console.log('═══════════════════════════════════════════════════════════════════════');
  console.log('  Demo Complete');
  console.log('═══════════════════════════════════════════════════════════════════════');
}

main().catch(console.error);
