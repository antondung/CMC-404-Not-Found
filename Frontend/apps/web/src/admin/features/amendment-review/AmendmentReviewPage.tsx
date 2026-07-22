import { useCallback, useEffect, useState } from 'react';
import {
  CheckCircle,
  Clock,
  FloppyDisk,
  GitDiff,
  ListChecks,
  ShieldCheck,
  Spinner,
  WarningCircle,
  XCircle,
} from '@phosphor-icons/react';

import { apiGet, apiPatch, apiPost } from '../../../lib/api';
import {
  CHANGE_TYPES,
  amendmentStatusLabel,
  canCommitAmendmentBatch,
  stableCommitKey,
  type AmendmentCandidate,
  type AmendmentCandidateDecision,
  type AmendmentChangeType,
  type AmendmentReviewBatch,
  type AmendmentReviewSummary,
} from '../../../lib/amendmentReviewContract';

interface ReviewListResponse {
  items: AmendmentReviewSummary[];
  total: number;
  limit: number;
  offset: number;
}

function statusClass(status: AmendmentReviewBatch['status']): string {
  if (status === 'committed') return 'border-emerald-200 bg-emerald-50 text-emerald-700';
  if (status === 'approved') return 'border-blue-200 bg-blue-50 text-blue-700';
  if (status === 'rejected') return 'border-rose-200 bg-rose-50 text-rose-700';
  if (status === 'in_review') return 'border-amber-200 bg-amber-50 text-amber-700';
  return 'border-slate-200 bg-slate-50 text-slate-600';
}

function CandidateEditor({
  candidate,
  batchStatus,
  busy,
  onSaved,
}: {
  candidate: AmendmentCandidate;
  batchStatus: AmendmentReviewBatch['status'];
  busy: boolean;
  onSaved: (candidate: AmendmentCandidate) => void;
}) {
  const [oldId, setOldId] = useState(candidate.old_provision_id ?? '');
  const [newId, setNewId] = useState(candidate.new_provision_id ?? '');
  const [effectiveFrom, setEffectiveFrom] = useState(candidate.proposed_effective_from ?? '');
  const [changeType, setChangeType] = useState<AmendmentChangeType>(candidate.change_type);
  const [decision, setDecision] = useState<AmendmentCandidateDecision>(candidate.decision);
  const [note, setNote] = useState(candidate.reviewer_note ?? '');
  const editable = batchStatus === 'draft' || batchStatus === 'in_review';

  useEffect(() => {
    setOldId(candidate.old_provision_id ?? '');
    setNewId(candidate.new_provision_id ?? '');
    setEffectiveFrom(candidate.proposed_effective_from ?? '');
    setChangeType(candidate.change_type);
    setDecision(candidate.decision);
    setNote(candidate.reviewer_note ?? '');
  }, [candidate]);

  const save = async () => {
    const updated = await apiPatch<AmendmentCandidate>(
      `/admin/legal/amendment-reviews/${candidate.batch_id}/candidates/${candidate.candidate_id}`,
      {
        expected_revision: candidate.revision,
        old_provision_id: oldId.trim() || null,
        new_provision_id: newId.trim() || null,
        proposed_effective_from: effectiveFrom || null,
        change_type: changeType,
        decision: batchStatus === 'draft' ? 'pending' : decision,
        reviewer_note: note.trim() || null,
      },
    );
    onSaved(updated);
  };

  return (
    <article className="rounded-2xl border border-border bg-white p-5 shadow-sm">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-md bg-primary-soft px-2 py-1 text-xs font-bold text-primary">
              {candidate.change_type}
            </span>
            <span className={`rounded-md border px-2 py-1 text-xs font-bold ${candidate.review_route === 'mandatory_review' ? 'border-amber-200 bg-amber-50 text-amber-700' : 'border-slate-200 bg-slate-50 text-slate-600'}`}>
              {candidate.review_route === 'mandatory_review' ? 'Bắt buộc thẩm định' : 'Thẩm định thường'}
            </span>
            <span className="text-xs font-mono text-muted">rev {candidate.revision}</span>
          </div>
          <p className="mt-2 text-xs font-mono text-muted">{candidate.candidate_id}</p>
        </div>
        <span className="text-sm font-bold text-ink">
          Độ tin cậy {(candidate.confidence * 100).toFixed(1)}%
        </span>
      </div>

      <div className="grid gap-3 lg:grid-cols-2">
        <label className="text-xs font-bold text-muted">
          Phiên bản cũ
          <input value={oldId} onChange={(event) => setOldId(event.target.value)} disabled={!editable} className="mt-1 w-full rounded-control border border-border bg-slate-50 px-3 py-2 text-xs font-mono text-ink disabled:opacity-60" />
        </label>
        <label className="text-xs font-bold text-muted">
          Phiên bản mới
          <input value={newId} onChange={(event) => setNewId(event.target.value)} disabled={!editable} className="mt-1 w-full rounded-control border border-border bg-slate-50 px-3 py-2 text-xs font-mono text-ink disabled:opacity-60" />
        </label>
        <label className="text-xs font-bold text-muted">
          Loại thay đổi
          <select value={changeType} onChange={(event) => setChangeType(event.target.value as AmendmentChangeType)} disabled={!editable} className="mt-1 w-full rounded-control border border-border bg-white px-3 py-2 text-sm text-ink disabled:opacity-60">
            {CHANGE_TYPES.map((value) => <option key={value} value={value}>{value}</option>)}
          </select>
        </label>
        <label className="text-xs font-bold text-muted">
          Ngày bắt đầu hiệu lực
          <input type="date" value={effectiveFrom} onChange={(event) => setEffectiveFrom(event.target.value)} disabled={!editable} className="mt-1 w-full rounded-control border border-border bg-white px-3 py-2 text-sm text-ink disabled:opacity-60" />
        </label>
        <label className="text-xs font-bold text-muted">
          Quyết định candidate
          <select value={decision} onChange={(event) => setDecision(event.target.value as AmendmentCandidateDecision)} disabled={batchStatus !== 'in_review'} className="mt-1 w-full rounded-control border border-border bg-white px-3 py-2 text-sm text-ink disabled:opacity-60">
            <option value="pending">Chờ quyết định</option>
            <option value="accepted">Chấp nhận</option>
            <option value="rejected">Loại bỏ</option>
          </select>
        </label>
        <label className="text-xs font-bold text-muted">
          Ghi chú thẩm định
          <input value={note} onChange={(event) => setNote(event.target.value)} disabled={!editable} className="mt-1 w-full rounded-control border border-border bg-white px-3 py-2 text-sm text-ink disabled:opacity-60" />
        </label>
      </div>

      {candidate.reason_codes.length > 0 && (
        <div className="mt-4 rounded-xl border border-amber-100 bg-amber-50/60 p-3">
          <p className="text-xs font-bold text-amber-800">Lý do cần chú ý</p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {candidate.reason_codes.map((reason) => <code key={reason} className="rounded bg-white px-2 py-1 text-[11px] text-amber-700">{reason}</code>)}
          </div>
        </div>
      )}

      {candidate.diff_hunks.length > 0 && (
        <div className="mt-4 space-y-2">
          <p className="text-xs font-bold text-muted">Khác biệt nguyên văn</p>
          {candidate.diff_hunks.map((hunk, index) => (
            <div key={`${hunk.type}-${index}`} className="grid gap-2 rounded-xl border border-border bg-slate-50 p-3 text-xs lg:grid-cols-2">
              <p className="text-rose-700"><span className="font-bold">Cũ:</span> {hunk.old || '—'}</p>
              <p className="text-emerald-700"><span className="font-bold">Mới:</span> {hunk.new || '—'}</p>
            </div>
          ))}
        </div>
      )}

      {editable && (
        <div className="mt-4 flex justify-end">
          <button type="button" onClick={() => void save()} disabled={busy} className="admin-btn-primary">
            {busy ? <Spinner size={16} className="animate-spin" /> : <FloppyDisk size={16} weight="bold" />}
            Lưu candidate
          </button>
        </div>
      )}
    </article>
  );
}

export default function AmendmentReviewPage() {
  const [items, setItems] = useState<AmendmentReviewSummary[]>([]);
  const [batch, setBatch] = useState<AmendmentReviewBatch | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sourceId, setSourceId] = useState('');

  const loadList = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiGet<ReviewListResponse>('/admin/legal/amendment-reviews?limit=100');
      setItems(data.items ?? []);
      setError(null);
      setSelectedId((current) => current ?? data.items?.[0]?.batch_id ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không tải được amendment review');
    } finally {
      setLoading(false);
    }
  }, []);

  const loadBatch = useCallback(async (batchId: string) => {
    try {
      const data = await apiGet<AmendmentReviewBatch>(`/admin/legal/amendment-reviews/${batchId}`);
      setBatch(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không tải được chi tiết review');
    }
  }, []);

  useEffect(() => { void loadList(); }, [loadList]);
  useEffect(() => { if (selectedId) void loadBatch(selectedId); }, [loadBatch, selectedId]);

  const refresh = async () => {
    await loadList();
    if (selectedId) await loadBatch(selectedId);
  };

  const transition = async (action: 'submit' | 'approve' | 'reject' | 'commit') => {
    if (!batch) return;
    if (action === 'commit' && !window.confirm('Ghi các thay đổi đã duyệt vào đồ thị pháp luật? Thao tác này được bảo vệ bằng idempotency và checksum.')) return;
    setBusy(true);
    setError(null);
    try {
      let updated: AmendmentReviewBatch;
      if (action === 'submit') {
        updated = await apiPost<AmendmentReviewBatch>(`/admin/legal/amendment-reviews/${batch.batch_id}/submit`, { expected_revision: batch.revision });
      } else if (action === 'approve' || action === 'reject') {
        updated = await apiPost<AmendmentReviewBatch>(`/admin/legal/amendment-reviews/${batch.batch_id}/decision`, { expected_revision: batch.revision, action, note: null });
      } else {
        const data = await apiPost<{ batch: AmendmentReviewBatch }>(`/admin/legal/amendment-reviews/${batch.batch_id}/commit`, {
          expected_revision: batch.revision,
          idempotency_key: stableCommitKey(batch.batch_id),
          amending_source_vb_id: sourceId.trim() || null,
        });
        updated = data.batch;
      }
      setBatch(updated);
      await loadList();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể chuyển trạng thái review');
    } finally {
      setBusy(false);
    }
  };

  const replaceCandidate = (updated: AmendmentCandidate) => {
    setBatch((current) => current ? { ...current, candidates: current.candidates.map((item) => item.candidate_id === updated.candidate_id ? updated : item) } : current);
  };

  return (
    <div className="mx-auto max-w-7xl space-y-6 pb-12">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold tracking-tight text-ink">
            <GitDiff size={28} weight="fill" className="text-primary" /> Duyệt sửa đổi pháp luật
          </h1>
          <p className="mt-1 text-sm text-muted">Kiểm tra cặp phiên bản, ngày hiệu lực và diff trước khi ghi temporal graph.</p>
        </div>
        <button type="button" onClick={() => void refresh()} className="admin-btn-secondary">
          <Spinner size={16} className={loading ? 'animate-spin' : 'hidden'} /> Làm mới
        </button>
      </header>

      {error && <div className="flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm font-medium text-rose-700"><WarningCircle size={20} weight="fill" />{error}</div>}

      <div className="grid gap-5 lg:grid-cols-[320px_minmax(0,1fr)]">
        <aside className="self-start rounded-2xl border border-border bg-surface p-3 shadow-sm lg:sticky lg:top-6">
          <div className="flex items-center justify-between px-2 py-2">
            <p className="flex items-center gap-2 text-sm font-bold text-ink"><ListChecks size={18} /> Review batches</p>
            <span className="text-xs font-bold text-muted">{items.length}</span>
          </div>
          <div className="max-h-[70vh] space-y-2 overflow-y-auto">
            {items.map((item) => (
              <button key={item.batch_id} type="button" onClick={() => setSelectedId(item.batch_id)} className={`w-full rounded-xl border p-3 text-left transition ${selectedId === item.batch_id ? 'border-primary bg-primary-soft/50' : 'border-border bg-white hover:border-primary/40'}`}>
                <div className="flex items-start justify-between gap-2">
                  <p className="text-sm font-bold text-ink">{item.target_logical_vb_id}</p>
                  <span className={`rounded border px-1.5 py-0.5 text-[10px] font-bold ${statusClass(item.status)}`}>{amendmentStatusLabel(item.status)}</span>
                </div>
                <p className="mt-2 text-xs text-muted">{item.candidate_count} candidate · {item.pending_count} chờ quyết định</p>
                <p className="mt-1 truncate font-mono text-[10px] text-slate-400">{item.batch_id}</p>
              </button>
            ))}
            {!loading && items.length === 0 && <p className="p-5 text-center text-sm text-muted">Chưa có amendment review.</p>}
          </div>
        </aside>

        <section className="min-w-0 space-y-4">
          {!batch ? (
            <div className="rounded-2xl border border-border bg-surface p-12 text-center text-muted"><ShieldCheck size={46} className="mx-auto mb-3 text-slate-300" />Chọn một batch để thẩm định.</div>
          ) : (
            <>
              <div className="rounded-2xl border border-border bg-surface p-5 shadow-sm">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <h2 className="text-lg font-bold text-ink">{batch.target_logical_vb_id}</h2>
                      <span className={`rounded border px-2 py-1 text-xs font-bold ${statusClass(batch.status)}`}>{amendmentStatusLabel(batch.status)}</span>
                      <span className="font-mono text-xs text-muted">rev {batch.revision}</span>
                    </div>
                    <p className="mt-3 whitespace-pre-wrap text-sm leading-relaxed text-slate-700">{batch.amendment_text}</p>
                    <p className="mt-2 flex items-center gap-1 text-xs text-muted"><Clock size={13} /> Cập nhật {batch.updated_at?.replace('T', ' ').slice(0, 19)}</p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {batch.status === 'draft' && <button type="button" onClick={() => void transition('submit')} disabled={busy} className="admin-btn-primary">Gửi thẩm định</button>}
                    {batch.status === 'in_review' && <><button type="button" onClick={() => void transition('approve')} disabled={busy} className="admin-btn-primary"><CheckCircle size={17} /> Phê duyệt</button><button type="button" onClick={() => void transition('reject')} disabled={busy} className="admin-btn-secondary !text-rose-600"><XCircle size={17} /> Từ chối</button></>}
                  </div>
                </div>

                {batch.status === 'approved' && (
                  <div className="mt-5 rounded-xl border border-amber-200 bg-amber-50 p-4">
                    <div className="flex items-start gap-2 text-sm text-amber-800"><WarningCircle size={20} weight="fill" className="shrink-0" /><p><strong>Commit riêng biệt:</strong> PostgreSQL đã phê duyệt nhưng Neo4j chưa thay đổi. Split, merge, uncertain và ngày lệch immutable ID sẽ bị backend từ chối.</p></div>
                    <div className="mt-3 flex flex-wrap gap-2">
                      <input value={sourceId} onChange={(event) => setSourceId(event.target.value)} placeholder="Amending source vb_id (để trống nếu tự suy ra được)" className="min-w-[280px] flex-1 rounded-control border border-amber-200 bg-white px-3 py-2 text-xs font-mono" />
                      <button type="button" onClick={() => void transition('commit')} disabled={busy || !canCommitAmendmentBatch(batch)} className="admin-btn-primary disabled:opacity-50"><ShieldCheck size={17} /> Commit temporal graph</button>
                    </div>
                  </div>
                )}

                {batch.status === 'committed' && <div className="mt-5 flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm font-bold text-emerald-700"><CheckCircle size={21} weight="fill" />Đã ghi temporal graph lúc {batch.committed_at?.replace('T', ' ').slice(0, 19)} bởi {batch.committed_by}.</div>}
              </div>

              <div className="space-y-4">
                {batch.candidates.map((candidate) => <CandidateEditor key={candidate.candidate_id} candidate={candidate} batchStatus={batch.status} busy={busy} onSaved={replaceCandidate} />)}
              </div>
            </>
          )}
        </section>
      </div>
    </div>
  );
}
