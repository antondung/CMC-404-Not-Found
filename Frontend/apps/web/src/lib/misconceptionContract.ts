export type TemporalMisconceptionVerdict =
  | 'SUPPORTED'
  | 'CONTRADICTED'
  | 'PARTIALLY_INCORRECT'
  | 'OUTDATED_BUT_PREVIOUSLY_TRUE'
  | 'UNVERIFIABLE'
  | 'NEEDS_REVIEW';

export interface RiskFactor {
  code: string;
  score: number;
  weight: number;
  contribution: number;
  explanation: string;
}

export interface MisconceptionSummary {
  misconception_id: string;
  canonical_claim: string;
  topic: string;
  legal_anchor_id: string;
  status: 'open' | 'reviewing' | 'corrected' | 'resolved';
  occurrence_count: number;
  source_count: number;
  provider_count: number;
  temporal_verdict: TemporalMisconceptionVerdict | null;
  temporal_as_of: string | null;
  risk_score: number | null;
  risk_severity: 'low' | 'medium' | 'high' | 'critical' | null;
  created_at: string;
  last_seen_at: string;
}

export interface MisconceptionOccurrence {
  ykien_id: string;
  claim_text: string;
  evidence_span: string;
  content_id: string;
  source_type: string;
  provider: string;
  canonical_url: string;
  content_hash: string;
  published_at: string;
  nli_score: number;
  cluster_similarity: number;
}

export interface MisconceptionDetail extends MisconceptionSummary {
  normalized_claim: string;
  occurrences: MisconceptionOccurrence[];
  legal_anchor_ids: string[];
  risk_factors: RiskFactor[];
  temporal_evaluations: TemporalOccurrenceEvaluation[];
  evaluated_at: string | null;
  evaluated_by: string | null;
}

export interface TemporalLegalCheck {
  as_of: string;
  provision_id: string;
  lineage_id: string;
  legal_text: string;
  text_checksum: string;
  effective_from: string;
  effective_to: string | null;
  label: 'khop' | 'mau_thuan' | 'khong_ro';
  score: number;
  model: string;
  needs_review: boolean;
}

export interface TemporalOccurrenceEvaluation {
  evaluation_id: string;
  ykien_id: string;
  claim_text: string;
  published_at: string;
  current_as_of: string;
  verdict: TemporalMisconceptionVerdict;
  historical: TemporalLegalCheck | null;
  current: TemporalLegalCheck | null;
  reason_codes: string[];
}

export interface MisconceptionEvaluationReport {
  misconception_id: string;
  current_as_of: string;
  cluster_verdict: TemporalMisconceptionVerdict;
  evaluations: TemporalOccurrenceEvaluation[];
  risk: {
    risk_score: number;
    severity: 'low' | 'medium' | 'high' | 'critical';
    factors: RiskFactor[];
    assessed_at: string;
    assessment_version: string;
  };
  persisted: boolean;
}

export function verdictLabel(verdict: TemporalMisconceptionVerdict | null): string {
  if (!verdict) return 'Chưa đánh giá theo thời gian';
  return {
    SUPPORTED: 'Hiện vẫn có căn cứ',
    CONTRADICTED: 'Mâu thuẫn với pháp luật',
    PARTIALLY_INCORRECT: 'Đúng/sai một phần',
    OUTDATED_BUT_PREVIOUSLY_TRUE: 'Từng đúng nhưng đã lỗi thời',
    UNVERIFIABLE: 'Chưa đủ căn cứ',
    NEEDS_REVIEW: 'Cần pháp chế thẩm định',
  }[verdict];
}

export function riskPercent(value: number | null): number {
  if (value === null || !Number.isFinite(value)) return 0;
  return Math.round(Math.max(0, Math.min(1, value)) * 100);
}

export function sourceDiversityLabel(
  occurrenceCount: number,
  sourceCount: number,
  providerCount: number,
): string {
  return `${occurrenceCount} claim · ${sourceCount} nội dung độc lập · ${providerCount} nhà cung cấp`;
}
