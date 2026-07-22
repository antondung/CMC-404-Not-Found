import assert from 'node:assert/strict';
import test from 'node:test';

import {
  amendmentStatusLabel,
  canCommitAmendmentBatch,
  stableCommitKey,
  type AmendmentReviewBatch,
} from '../apps/web/src/lib/amendmentReviewContract.ts';

function batch(changeType = 'TIGHTENED', status = 'approved'): AmendmentReviewBatch {
  return {
    batch_id: '11111111-1111-4111-8111-111111111111',
    target_logical_vb_id: '01/2026/ND-CP',
    amendment_text: 'Sửa đổi điểm a khoản 2 Điều 5.',
    status: status as AmendmentReviewBatch['status'],
    revision: 3,
    created_by: 'reviewer-1',
    review_note: null,
    commit_idempotency_key: null,
    committed_by: null,
    committed_at: null,
    commit_result: null,
    commit_allowed: false,
    auto_approve_eligible: false,
    created_at: '2026-07-21T00:00:00Z',
    updated_at: '2026-07-21T00:00:00Z',
    candidates: [{
      candidate_id: '22222222-2222-4222-8222-222222222222',
      batch_id: '11111111-1111-4111-8111-111111111111',
      old_provision_id: 'old',
      new_provision_id: 'new',
      lineage_id: '01/2026/ND-CP::D5.K2.Pa',
      reference_ids: [],
      confidence: 0.95,
      change_type: changeType as AmendmentReviewBatch['candidates'][number]['change_type'],
      review_route: 'human_review',
      proposed_effective_from: '2026-07-01',
      decision: 'accepted',
      reason_codes: [],
      diff_hunks: [],
      reviewer_note: null,
      revision: 2,
      commit_allowed: false,
      auto_approve_eligible: false,
    }],
  };
}

test('allows graph commit only for approved deterministic candidates', () => {
  assert.equal(canCommitAmendmentBatch(batch()), true);
  assert.equal(canCommitAmendmentBatch(batch('TIGHTENED', 'in_review')), false);
});

test('blocks ambiguous and unchanged candidates from the commit action', () => {
  assert.equal(canCommitAmendmentBatch(batch('SPLIT')), false);
  assert.equal(canCommitAmendmentBatch(batch('MERGED')), false);
  assert.equal(canCommitAmendmentBatch(batch('UNCERTAIN')), false);
  assert.equal(canCommitAmendmentBatch(batch('UNCHANGED')), false);
});

test('builds a stable retry key and renders committed status', () => {
  const id = '11111111-1111-4111-8111-111111111111';
  assert.equal(stableCommitKey(id), `amendment-commit:${id}`);
  assert.equal(amendmentStatusLabel('committed'), 'Đã ghi đồ thị');
});
