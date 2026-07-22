import test from 'node:test';
import assert from 'node:assert/strict';

import { riskPercent, sourceDiversityLabel, verdictLabel } from '../apps/web/src/lib/misconceptionContract.ts';

test('renders the outdated verdict in citizen-safe Vietnamese', () => {
  assert.equal(
    verdictLabel('OUTDATED_BUT_PREVIOUSLY_TRUE'),
    'Từng đúng nhưng đã lỗi thời',
  );
});

test('clamps risk scores for UI rendering', () => {
  assert.equal(riskPercent(0.824), 82);
  assert.equal(riskPercent(4), 100);
  assert.equal(riskPercent(-1), 0);
  assert.equal(riskPercent(null), 0);
});

test('separates independent content from provider count', () => {
  assert.equal(
    sourceDiversityLabel(8, 3, 5),
    '8 claim · 3 nội dung độc lập · 5 nhà cung cấp',
  );
});
