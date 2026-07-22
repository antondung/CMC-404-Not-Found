import { useCallback, useEffect, useState } from 'react';
import {
  ArrowRight,
  Clock,
  Newspaper,
  Scales,
  ShieldCheck,
  Spinner,
  TrendUp,
  WarningCircle,
} from '@phosphor-icons/react';

import { apiGet, apiPost } from '../../../lib/api';
import {
  riskPercent,
  sourceDiversityLabel,
  verdictLabel,
  type MisconceptionDetail,
  type MisconceptionEvaluationReport,
  type MisconceptionSummary,
  type RiskFactor,
  type TemporalLegalCheck,
  type TemporalMisconceptionVerdict,
} from '../../../lib/misconceptionContract';

interface ListResponse {
  items: MisconceptionSummary[];
  count: number;
  limit: number;
  offset: number;
}

function todayIso(): string {
  const now = new Date();
  return new Date(now.getTime() - now.getTimezoneOffset() * 60_000).toISOString().slice(0, 10);
}

function verdictClass(verdict: TemporalMisconceptionVerdict | null): string {
  if (verdict === 'OUTDATED_BUT_PREVIOUSLY_TRUE') return 'border-violet-200 bg-violet-50 text-violet-700';
  if (verdict === 'CONTRADICTED') return 'border-rose-200 bg-rose-50 text-rose-700';
  if (verdict === 'SUPPORTED') return 'border-emerald-200 bg-emerald-50 text-emerald-700';
  if (verdict === 'NEEDS_REVIEW') return 'border-amber-200 bg-amber-50 text-amber-700';
  return 'border-slate-200 bg-slate-50 text-slate-600';
}

function FactorRow({ factor }: { factor: RiskFactor }) {
  const width = Math.max(0, Math.min(100, factor.score * 100));
  return (
    <div className="rounded-xl border border-border bg-white p-3">
      <div className="flex items-center justify-between gap-3 text-xs">
        <span className="font-bold text-ink">{factor.code}</span>
        <span className={`font-mono font-bold ${factor.contribution < 0 ? 'text-rose-600' : 'text-primary'}`}>
          {factor.contribution >= 0 ? '+' : ''}{(factor.contribution * 100).toFixed(1)}
        </span>
      </div>
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-100">
        <div className="h-full rounded-full bg-primary" style={{ width: `${width}%` }} />
      </div>
      <p className="mt-2 text-[11px] leading-relaxed text-muted">{factor.explanation}</p>
    </div>
  );
}

function LegalCheckCard({ title, check }: { title: string; check: TemporalLegalCheck | null }) {
  if (!check) {
    return <div className="rounded-xl border border-dashed border-slate-300 p-4 text-sm text-muted">{title}: chưa có căn cứ canonical.</div>;
  }
  return (
    <div className="rounded-xl border border-border bg-slate-50 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs font-black uppercase tracking-wide text-muted">{title} · {check.as_of}</p>
        <span className={`rounded px-2 py-1 text-xs font-bold ${check.label === 'khop' ? 'bg-emerald-100 text-emerald-700' : check.label === 'mau_thuan' ? 'bg-rose-100 text-rose-700' : 'bg-slate-200 text-slate-600'}`}>
          {check.label} {(check.score * 100).toFixed(0)}%
        </span>
      </div>
      <p className="mt-3 text-sm leading-relaxed text-ink">{check.legal_text}</p>
      <p className="mt-3 break-all font-mono text-[10px] text-slate-400">{check.provision_id}</p>
      <p className="mt-1 text-[11px] text-muted">Hiệu lực {check.effective_from} → {check.effective_to ?? 'hiện tại'}</p>
    </div>
  );
}

export default function MisconceptionsPage() {
  const [items, setItems] = useState<MisconceptionSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<MisconceptionDetail | null>(null);
  const [evaluation, setEvaluation] = useState<MisconceptionEvaluationReport | null>(null);
  const [asOf, setAsOf] = useState(todayIso());
  const [dryRun, setDryRun] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadList = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiGet<ListResponse>('/admin/misconceptions?limit=100');
      setItems(data.items ?? []);
      setSelectedId((current) => current ?? data.items?.[0]?.misconception_id ?? null);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không tải được cụm hiểu nhầm');
    } finally {
      setLoading(false);
    }
  }, []);

  const loadDetail = useCallback(async (id: string) => {
    try {
      const data = await apiGet<MisconceptionDetail>(`/admin/misconceptions/${id}`);
      setDetail(data);
      setEvaluation(null);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không tải được bằng chứng cụm');
    }
  }, []);

  useEffect(() => { void loadList(); }, [loadList]);
  useEffect(() => { if (selectedId) void loadDetail(selectedId); }, [loadDetail, selectedId]);

  const evaluate = async () => {
    if (!detail || busy) return;
    setBusy(true);
    setError(null);
    try {
      const report = await apiPost<MisconceptionEvaluationReport>(
        `/admin/misconceptions/${detail.misconception_id}/evaluate`,
        { current_as_of: asOf, dry_run: dryRun },
      );
      setEvaluation(report);
      if (!dryRun) {
        await Promise.all([loadList(), loadDetail(detail.misconception_id)]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể đánh giá hai thời điểm');
    } finally {
      setBusy(false);
    }
  };

  const shownVerdict = evaluation?.cluster_verdict ?? detail?.temporal_verdict ?? null;
  const shownRisk = evaluation?.risk.risk_score ?? detail?.risk_score ?? null;
  const shownFactors = evaluation?.risk.factors ?? detail?.risk_factors ?? [];
  const shownEvaluations = evaluation?.evaluations ?? detail?.temporal_evaluations ?? [];

  return (
    <div className="mx-auto max-w-7xl space-y-6 pb-12">
      <header>
        <h1 className="flex items-center gap-2 text-2xl font-bold tracking-tight text-ink">
          <WarningCircle size={29} weight="fill" className="text-amber-500" /> Cụm hiểu nhầm pháp luật
        </h1>
        <p className="mt-1 text-sm text-muted">Đối chiếu cùng một claim tại ngày đăng và hiện tại, kèm căn cứ và risk score giải thích được.</p>
      </header>

      {error && <div className="flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm font-medium text-rose-700"><WarningCircle size={20} weight="fill" />{error}</div>}

      <div className="grid gap-5 lg:grid-cols-[340px_minmax(0,1fr)]">
        <aside className="self-start rounded-2xl border border-border bg-surface p-3 shadow-sm lg:sticky lg:top-6">
          <div className="flex items-center justify-between px-2 py-2">
            <p className="text-sm font-bold text-ink">Misconception clusters</p>
            <span className="text-xs font-bold text-muted">{items.length}</span>
          </div>
          <div className="max-h-[74vh] space-y-2 overflow-y-auto">
            {items.map((item) => (
              <button key={item.misconception_id} type="button" onClick={() => setSelectedId(item.misconception_id)} className={`w-full rounded-xl border p-3 text-left transition ${selectedId === item.misconception_id ? 'border-primary bg-primary-soft/50' : 'border-border bg-white hover:border-primary/40'}`}>
                <p className="line-clamp-3 text-sm font-bold leading-snug text-ink">{item.canonical_claim}</p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  <span className="rounded bg-slate-100 px-2 py-1 text-[10px] font-bold text-slate-600">#{item.topic}</span>
                  <span className={`rounded border px-2 py-1 text-[10px] font-bold ${verdictClass(item.temporal_verdict)}`}>{verdictLabel(item.temporal_verdict)}</span>
                </div>
                <p className="mt-2 text-xs text-muted">{sourceDiversityLabel(item.occurrence_count, item.source_count, item.provider_count)}</p>
              </button>
            ))}
            {!loading && items.length === 0 && <p className="p-6 text-center text-sm text-muted">Chưa có cụm hiểu nhầm.</p>}
            {loading && <p className="flex items-center justify-center gap-2 p-6 text-sm text-muted"><Spinner size={18} className="animate-spin" />Đang tải</p>}
          </div>
        </aside>

        <main className="min-w-0 space-y-4">
          {!detail ? (
            <div className="rounded-2xl border border-border bg-surface p-12 text-center text-muted"><ShieldCheck size={48} className="mx-auto mb-3 text-slate-300" />Chọn một cụm để kiểm tra căn cứ.</div>
          ) : (
            <>
              <section className="rounded-2xl border border-border bg-surface p-5 shadow-sm">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div className="max-w-3xl">
                    <span className={`inline-flex rounded border px-2 py-1 text-xs font-bold ${verdictClass(shownVerdict)}`}>{verdictLabel(shownVerdict)}</span>
                    <h2 className="mt-3 text-xl font-black leading-snug text-ink">{detail.canonical_claim}</h2>
                    <p className="mt-2 break-all font-mono text-[10px] text-slate-400">{detail.misconception_id}</p>
                  </div>
                  <div className="min-w-28 rounded-2xl border border-border bg-slate-50 p-4 text-center">
                    <p className="text-3xl font-black text-primary">{riskPercent(shownRisk)}%</p>
                    <p className="mt-1 text-[10px] font-black uppercase tracking-wider text-muted">Risk score</p>
                  </div>
                </div>

                <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                  <div className="rounded-xl bg-slate-50 p-3"><p className="text-xs text-muted">Occurrences</p><p className="text-lg font-black text-ink">{detail.occurrence_count}</p></div>
                  <div className="rounded-xl bg-slate-50 p-3"><p className="text-xs text-muted">Nguồn nội dung độc lập</p><p className="text-lg font-black text-ink">{detail.source_count}</p></div>
                  <div className="rounded-xl bg-slate-50 p-3"><p className="text-xs text-muted">Nhà cung cấp</p><p className="text-lg font-black text-ink">{detail.provider_count}</p></div>
                  <div className="rounded-xl bg-slate-50 p-3"><p className="text-xs text-muted">Căn cứ neo</p><p className="truncate font-mono text-xs font-bold text-ink">{detail.legal_anchor_id}</p></div>
                </div>

                <div className="mt-5 flex flex-wrap items-end gap-3 rounded-xl border border-blue-100 bg-blue-50/60 p-4">
                  <label className="text-xs font-bold text-blue-900">Đánh giá đến ngày
                    <input type="date" value={asOf} onChange={(event) => setAsOf(event.target.value)} className="mt-1 block rounded-control border border-blue-200 bg-white px-3 py-2 text-sm text-ink" />
                  </label>
                  <label className="flex items-center gap-2 pb-2 text-sm font-bold text-blue-900"><input type="checkbox" checked={dryRun} onChange={(event) => setDryRun(event.target.checked)} />Chạy thử, không lưu</label>
                  <button type="button" onClick={() => void evaluate()} disabled={busy || !asOf} className="admin-btn-primary ml-auto disabled:opacity-50">
                    {busy ? <Spinner size={17} className="animate-spin" /> : <Scales size={17} weight="bold" />} Đối chiếu hai thời điểm
                  </button>
                </div>
              </section>

              {shownFactors.length > 0 && (
                <section className="rounded-2xl border border-border bg-surface p-5 shadow-sm">
                  <h3 className="flex items-center gap-2 font-black text-ink"><TrendUp size={20} className="text-primary" />Risk factors</h3>
                  <div className="mt-4 grid gap-3 md:grid-cols-2">{shownFactors.map((factor) => <FactorRow key={factor.code} factor={factor} />)}</div>
                </section>
              )}

              {shownEvaluations.length > 0 && (
                <section className="space-y-4">
                  {shownEvaluations.map((item) => (
                    <article key={item.evaluation_id} className="rounded-2xl border border-border bg-surface p-5 shadow-sm">
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div><p className="text-sm font-black text-ink">{item.claim_text}</p><p className="mt-1 flex items-center gap-1 text-xs text-muted"><Clock size={13} />Đăng lúc {item.published_at.replace('T', ' ').slice(0, 19)}</p></div>
                        <span className={`rounded border px-2 py-1 text-xs font-bold ${verdictClass(item.verdict)}`}>{verdictLabel(item.verdict)}</span>
                      </div>
                      <div className="mt-4 grid items-center gap-3 lg:grid-cols-[1fr_auto_1fr]">
                        <LegalCheckCard title="Căn cứ tại ngày đăng" check={item.historical} />
                        <ArrowRight size={22} className="mx-auto rotate-90 text-slate-300 lg:rotate-0" />
                        <LegalCheckCard title="Căn cứ hiện tại" check={item.current} />
                      </div>
                      {item.reason_codes.length > 0 && <div className="mt-3 flex flex-wrap gap-1.5">{item.reason_codes.map((code) => <code key={code} className="rounded bg-amber-50 px-2 py-1 text-[10px] text-amber-700">{code}</code>)}</div>}
                    </article>
                  ))}
                </section>
              )}

              <section className="rounded-2xl border border-border bg-surface p-5 shadow-sm">
                <h3 className="flex items-center gap-2 font-black text-ink"><Newspaper size={20} className="text-primary" />Nguồn xuất hiện</h3>
                <div className="mt-4 space-y-3">
                  {detail.occurrences.map((item) => (
                    <div key={item.ykien_id} className="rounded-xl border border-border bg-slate-50 p-4">
                      <div className="flex flex-wrap items-center gap-2 text-xs text-muted"><span className="font-bold text-ink">{item.provider}</span><span>{item.source_type}</span><span>·</span><span>{item.published_at?.replace('T', ' ').slice(0, 19)}</span></div>
                      <p className="mt-2 text-sm leading-relaxed text-ink">{item.evidence_span || item.claim_text}</p>
                      {item.canonical_url && <a href={item.canonical_url} target="_blank" rel="noreferrer" className="mt-2 block truncate text-xs font-bold text-blue-600 hover:underline">Mở nguồn gốc</a>}
                    </div>
                  ))}
                </div>
              </section>
            </>
          )}
        </main>
      </div>
    </div>
  );
}
