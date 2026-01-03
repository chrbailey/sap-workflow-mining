/**
 * Predictive Monitoring Demo using BPI Challenge 2019 Data
 *
 * Demonstrates ML-based prediction of process outcomes:
 * - Late delivery prediction
 * - Credit hold prediction
 * - Completion time estimation
 * - Risk scoring and alerts
 */

import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';
import {
  ProcessCase,
  extractFeatures,
  extractBatchFeatures,
  predict,
  predictOutcomes,
  assessRisk,
  generateAlerts,
  formatRiskLevel,
  rankByRisk,
  PREDICTION_TYPES,
  MODEL_DESCRIPTIONS,
} from '../mcp-server/src/prediction/index.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Load BPI 2019 data
const dataPath = path.join(__dirname, '../data/bpi/bpi_2019.json');

interface BPIEvent {
  'concept:name': string;
  'time:timestamp': string;
  'org:resource'?: string;
  User?: string;
  [key: string]: unknown;
}

interface BPITrace {
  case_id: string;
  attributes: Record<string, unknown>;
  events: BPIEvent[];
}

interface BPIData {
  metadata: Record<string, unknown>;
  stats: Record<string, unknown>;
  traces: BPITrace[];
}

async function loadBPIData(): Promise<ProcessCase[]> {
  const rawData = fs.readFileSync(dataPath, 'utf-8');
  const data: BPIData = JSON.parse(rawData);

  // Convert traces to ProcessCase format
  return data.traces.map((trace) => ({
    caseId: trace.case_id,
    events: trace.events.map((event) => {
      const processEvent: ProcessCase['events'][0] = {
        caseId: trace.case_id,
        activity: event['concept:name'],
        timestamp: event['time:timestamp'],
        attributes: event,
      };
      const resource = event['org:resource'] || event.User;
      if (resource !== undefined) {
        processEvent.resource = resource;
      }
      return processEvent;
    }),
  }));
}

async function main() {
  console.log('='.repeat(70));
  console.log('PREDICTIVE MONITORING DEMO - BPI Challenge 2019 Data');
  console.log('='.repeat(70));
  console.log();

  // Load data
  console.log('Loading BPI 2019 data...');
  const cases = await loadBPIData();
  console.log(`Loaded ${cases.length} cases`);
  console.log();

  // Limit for demo
  const maxCases = parseInt(process.argv[2] || '50', 10);
  const demoCases = cases.slice(0, maxCases);
  console.log(`Analyzing ${demoCases.length} cases for demo`);
  console.log();

  // Show available prediction types
  console.log('Available Prediction Types:');
  console.log('-'.repeat(50));
  for (const type of PREDICTION_TYPES) {
    console.log(`  - ${type}: ${MODEL_DESCRIPTIONS[type]}`);
  }
  console.log();

  // Feature extraction example
  console.log('='.repeat(70));
  console.log('FEATURE EXTRACTION');
  console.log('='.repeat(70));
  console.log();

  const sampleCase = demoCases[0]!;
  const features = extractFeatures(sampleCase);

  console.log(`Case: ${sampleCase.caseId}`);
  console.log(`  Events: ${features.eventCount}`);
  console.log(`  Unique activities: ${features.uniqueActivities}`);
  console.log(`  Case age: ${Math.round(features.caseAge)} hours (${Math.round(features.caseAge / 24)} days)`);
  console.log(`  Progress score: ${Math.round(features.progressScore * 100)}%`);
  console.log(`  Complexity score: ${Math.round(features.complexityScore * 100)}%`);
  console.log(`  Has rework: ${features.hasRework}`);
  console.log(`  Loop count: ${features.loopCount}`);
  console.log(`  Risk indicators: ${features.riskIndicators.join(', ') || 'None'}`);
  console.log();

  // Individual predictions
  console.log('='.repeat(70));
  console.log('INDIVIDUAL PREDICTIONS');
  console.log('='.repeat(70));
  console.log();

  for (const predType of PREDICTION_TYPES) {
    const result = predict(features, predType);
    console.log(`${predType.toUpperCase()}:`);
    console.log(`  Risk Level: ${formatRiskLevel(result.riskLevel)}`);

    if (predType === 'completion_time') {
      const hours = result.prediction as number;
      console.log(`  Estimated completion: ${Math.round(hours)} hours (${Math.round(hours / 24)} days)`);
    } else {
      console.log(`  Probability: ${Math.round(result.probability * 100)}%`);
    }

    if (result.factors.length > 0) {
      console.log('  Top factors:');
      for (const factor of result.factors.slice(0, 3)) {
        const icon = factor.impact === 'positive' ? '✅' : factor.impact === 'negative' ? '❌' : '➖';
        console.log(`    ${icon} ${factor.description}`);
      }
    }

    if (result.recommendations.length > 0) {
      console.log('  Recommendations:');
      for (const rec of result.recommendations) {
        console.log(`    → ${rec}`);
      }
    }
    console.log();
  }

  // Batch prediction - Late Delivery
  console.log('='.repeat(70));
  console.log('BATCH PREDICTION: Late Delivery');
  console.log('='.repeat(70));
  console.log();

  const { result: lateDeliveryResult, alerts: lateDeliveryAlerts } = predictOutcomes(
    demoCases,
    'late_delivery',
    {
      enabled: true,
      riskThreshold: 'high',
      predictionTypes: ['late_delivery'],
    }
  );

  console.log('Summary:');
  console.log(`  Total cases: ${lateDeliveryResult.summary.totalCases}`);
  console.log(`  Average risk: ${Math.round(lateDeliveryResult.summary.avgProbability * 100)}%`);
  console.log();

  console.log('Risk Distribution:');
  console.log(`  🟢 Low: ${lateDeliveryResult.summary.riskDistribution.low} cases`);
  console.log(`  🟡 Medium: ${lateDeliveryResult.summary.riskDistribution.medium} cases`);
  console.log(`  🟠 High: ${lateDeliveryResult.summary.riskDistribution.high} cases`);
  console.log(`  🔴 Critical: ${lateDeliveryResult.summary.riskDistribution.critical} cases`);
  console.log();

  if (lateDeliveryResult.summary.topRiskFactors.length > 0) {
    console.log('Top Risk Factors:');
    for (const { factor, count } of lateDeliveryResult.summary.topRiskFactors.slice(0, 5)) {
      const name = factor.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
      console.log(`  - ${name}: ${count} cases`);
    }
    console.log();
  }

  // Alerts
  if (lateDeliveryAlerts.length > 0) {
    console.log('='.repeat(70));
    console.log('ALERTS');
    console.log('='.repeat(70));
    console.log();

    for (const alert of lateDeliveryAlerts.slice(0, 5)) {
      const icon = alert.alertType === 'immediate_action' ? '🚨' : '⚠️';
      console.log(`${icon} ${alert.caseId}`);
      console.log(`   ${alert.message}`);
      if (alert.recommendations.length > 0) {
        console.log('   Recommendations:');
        for (const rec of alert.recommendations) {
          console.log(`     → ${rec}`);
        }
      }
      console.log();
    }

    if (lateDeliveryAlerts.length > 5) {
      console.log(`... and ${lateDeliveryAlerts.length - 5} more alerts`);
      console.log();
    }
  }

  // Risk ranking
  console.log('='.repeat(70));
  console.log('RISK RANKING (Top 10)');
  console.log('='.repeat(70));
  console.log();

  const ranked = rankByRisk(lateDeliveryResult.predictions);
  for (const { caseId, riskScore, riskLevel } of ranked.slice(0, 10)) {
    console.log(`  ${formatRiskLevel(riskLevel)} ${caseId} - Score: ${riskScore}`);
  }
  console.log();

  // Composite risk assessment
  console.log('='.repeat(70));
  console.log('COMPOSITE RISK ASSESSMENT (Top 5 Cases)');
  console.log('='.repeat(70));
  console.log();

  for (const processCase of demoCases.slice(0, 5)) {
    const assessment = assessRisk(processCase);
    console.log(`Case: ${processCase.caseId}`);
    console.log(`  Overall Risk: ${assessment.overallRisk}`);
    console.log(`  Late Delivery: ${assessment.lateDeliveryRisk}%`);
    console.log(`  Credit Hold: ${assessment.creditHoldRisk}%`);
    console.log(`  Est. Completion: ${Math.round(assessment.estimatedCompletion / 24)} days`);
    if (assessment.recommendations.length > 0) {
      console.log('  Recommendations:');
      for (const rec of assessment.recommendations.slice(0, 2)) {
        console.log(`    → ${rec}`);
      }
    }
    console.log();
  }

  console.log('='.repeat(70));
  console.log('Demo complete!');
  console.log('='.repeat(70));
}

main().catch(console.error);
