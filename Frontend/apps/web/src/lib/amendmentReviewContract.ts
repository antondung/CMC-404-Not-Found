export type AmendmentBatchStatus = 'draft' | 'in_review' | 'approved' | 'rejected' | 'committed';
export type AmendmentCandidateDecision = 'pending' | 'accepted' | 'rejected';
export type AmendmentChangeType =
  | 'UNCHANGED'
  | 'REWORDED'
  | 'TIGHTENED'
  | 'LOOSENED'
  | 'ADDED'
  | 'REMOVED'
  | 'SPLIT'
  | 'MERGED'
  | 'UNCERTAIN';

export interface AmendmentCandidate {
  candidate_id: string;
  batch_id: string;
  old_provision_id: string | null;
  new_provision_id: string | null;
  lineage_id: string | null;
  reference_ids: string[];
  confidence: number;
  change_type: AmendmentChangeType;
  review_route: 'human_review' | 'mandatory_review';
  proposed_effective_from: string | null;
  decision: AmendmentCandidateDecision;
  reason_codes: string[];
  diff_hunks: Array<{ type: 'replace' | 'delete' | 'insert'; old: string; new: string }>;
  reviewer_note: string | null;
  revision: number;
  commit_allowed: false;
  auto_approve_eligible: false;
}

export interface AmendmentReviewBatch {
  batch_id: string;
  target_logical_vb_id: string;
  amendment_text: string;
  status: AmendmentBatchStatus;
  candidates: AmendmentCandidate[];
  revision: number;
  created_by: string;
  review_note: string | null;
  commit_idempotency_key: string | null;
  committed_by: string | null;
  committed_at: string | null;
  commit_result: Record<string, unknown> | null;
  commit_allowed: false;
  auto_approve_eligible: false;
  created_at: string;
  updated_at: string;
}

export interface AmendmentReviewSummary {
  batch_id: string;
  target_logical_vb_id: string;
  status: AmendmentBatchStatus;
  candidate_count: number;
  pending_count: number;
  revision: number;
  created_by: string;
  created_at: string;
  updated_at: string;
  commit_allowed: false;
}

export const CHANGE_TYPES: AmendmentChangeType[] = [
  'REWORDED',
  'TIGHTENED',
  'LOOSENED',
  'ADDED',
  'REMOVED',
  'UNCHANGED',
  'SPLIT',
  'MERGED',
  'UNCERTAIN',
];

const GRAPH_BLOCKED_TYPES = new Set<AmendmentChangeType>([
  'UNCHANGED',
  'SPLIT',
  'MERGED',
  'UNCERTAIN',
]);

export function canCommitAmendmentBatch(batch: AmendmentReviewBatch): boolean {
  if (batch.status !== 'approved') return false;
  const accepted = batch.candidates.filter((item) => item.decision === 'accepted');
  return (
    accepted.length > 0 &&
    accepted.every(
      (item) =>
        Boolean(item.proposed_effective_from) && !GRAPH_BLOCKED_TYPES.has(item.change_type),
    )
  );
}

export function amendmentStatusLabel(status: AmendmentBatchStatus): string {
  return {
    draft: 'Bản nháp',
    in_review: 'Đang thẩm định',
    approved: 'Đã phê duyệt',
    rejected: 'Đã từ chối',
    committed: 'Đã ghi đồ thị',
  }[status];
}

export function stableCommitKey(batchId: string): string {
  return `amendment-commit:${batchId}`;
}
