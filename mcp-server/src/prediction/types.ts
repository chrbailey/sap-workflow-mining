/**
 * Predictive Monitoring Types
 *
 * Type definitions for ML-based process outcome prediction.
 */

/**
 * Types of predictions supported
 */
export type PredictionType = 'late_delivery' | 'credit_hold' | 'completion_time';

/**
 * Risk levels for alerts
 */
export type RiskLevel = 'low' | 'medium' | 'high' | 'critical';

/**
 * Process event for feature extraction
 */
export interface ProcessEvent {
  caseId: string;
  activity: string;
  timestamp: string;
  resource?: string;
  attributes?: Record<string, unknown>;
}

/**
 * Case with events for prediction
 */
export interface ProcessCase {
  caseId: string;
  events: ProcessEvent[];
  attributes?: Record<string, unknown>;
}

/**
 * Extracted features from a case
 */
export interface CaseFeatures {
  caseId: string;

  // Temporal features
  caseAge: number; // Hours since case started
  eventCount: number;
  avgTimeBetweenEvents: number; // Hours
  timeSinceLastEvent: number; // Hours

  // Activity features
  uniqueActivities: number;
  hasDeliveryCreated: boolean;
  hasGoodsIssued: boolean;
  hasInvoiceCreated: boolean;
  hasCreditCheck: boolean;
  hasCreditHold: boolean;

  // Sequence features
  currentActivity: string;
  previousActivity: string | null;
  activitySequenceLength: number;

  // Resource features
  uniqueResources: number;
  resourceChanges: number;

  // Pattern features
  hasRework: boolean; // Same activity repeated
  loopCount: number; // Number of loops detected
  backtrackCount: number; // Going back to earlier activities

  // Time-based patterns
  weekdayStart: number; // 0-6
  hourStart: number; // 0-23
  isWeekend: boolean;

  // P2P specific features
  hasPurchaseOrder: boolean;
  hasGoodsReceipt: boolean;
  hasServiceEntry: boolean;

  // Derived metrics
  progressScore: number; // 0-1 estimated progress
  complexityScore: number; // 0-1 case complexity
  riskIndicators: string[]; // List of detected risk factors
}

/**
 * Prediction result
 */
export interface PredictionResult {
  caseId: string;
  predictionType: PredictionType;
  prediction: boolean | number; // boolean for classification, number for regression
  probability: number; // Confidence 0-1
  riskLevel: RiskLevel;
  factors: PredictionFactor[];
  recommendations: string[];
  timestamp: string;
}

/**
 * Factor contributing to prediction
 */
export interface PredictionFactor {
  name: string;
  value: number | string | boolean;
  impact: 'positive' | 'negative' | 'neutral';
  weight: number; // Importance 0-1
  description: string;
}

/**
 * Model configuration
 */
export interface ModelConfig {
  type: 'random_forest' | 'gradient_boosting' | 'ensemble' | 'heuristic';
  threshold: number; // Classification threshold
  featureWeights?: Record<string, number>;
}

/**
 * Alert configuration
 */
export interface AlertConfig {
  enabled: boolean;
  riskThreshold: RiskLevel;
  predictionTypes: PredictionType[];
}

/**
 * Prediction options
 */
export interface PredictionOptions {
  predictionType: PredictionType;
  modelConfig?: Partial<ModelConfig>;
  includeFactors?: boolean;
  includeRecommendations?: boolean;
}

/**
 * Batch prediction result
 */
export interface BatchPredictionResult {
  predictions: PredictionResult[];
  summary: PredictionSummary;
  timestamp: string;
}

/**
 * Summary statistics for batch predictions
 */
export interface PredictionSummary {
  totalCases: number;
  predictionType: PredictionType;
  riskDistribution: Record<RiskLevel, number>;
  avgProbability: number;
  highRiskCases: string[];
  topRiskFactors: { factor: string; count: number }[];
}

/**
 * Historical outcome for model training/validation
 */
export interface HistoricalOutcome {
  caseId: string;
  outcome: boolean | number;
  completedAt: string;
}

/**
 * Model performance metrics
 */
export interface ModelMetrics {
  accuracy: number;
  precision: number;
  recall: number;
  f1Score: number;
  auc: number;
  confusionMatrix: {
    truePositive: number;
    trueNegative: number;
    falsePositive: number;
    falseNegative: number;
  };
}

/**
 * Risk thresholds for each level
 */
export const RISK_THRESHOLDS: Record<RiskLevel, { min: number; max: number }> = {
  low: { min: 0, max: 0.25 },
  medium: { min: 0.25, max: 0.5 },
  high: { min: 0.5, max: 0.75 },
  critical: { min: 0.75, max: 1.0 },
};

/**
 * Default model configuration
 */
export const DEFAULT_MODEL_CONFIG: ModelConfig = {
  type: 'heuristic',
  threshold: 0.5,
};

/**
 * O2C activity milestones for progress tracking
 */
export const O2C_MILESTONES = [
  'order_created',
  'credit_check',
  'delivery_created',
  'picking',
  'packing',
  'goods_issued',
  'invoice_created',
  'payment_received',
] as const;

/**
 * P2P activity milestones for progress tracking
 */
export const P2P_MILESTONES = [
  'purchase_requisition',
  'purchase_order',
  'goods_receipt',
  'service_entry',
  'invoice_receipt',
  'invoice_verification',
  'payment',
] as const;
