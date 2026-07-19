import { useEffect, useMemo, useRef, useState } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import { Gauge, Graph, Hash, Spinner, WarningCircle } from '@phosphor-icons/react';
import { apiGet } from '../../../lib/api';

interface Topic {
  slug?: string;
  ten?: string;
  name?: string;
  chu_de?: string;
  post_count?: number;
  so_bai?: number;
  monitored?: boolean;
}

interface Post {
  bai_dang_id?: string;
  id?: string;
  chu_de?: string;
  source_topic?: string;
  source_query?: string;
  video_title?: string;
  noi_dung?: string;
  content?: string;
  needs_review?: boolean;
}

interface ClarityItem {
  slug?: string;
  ten?: string;
  volume: number;
  doi_chieu?: number;
  mau_thuan?: number;
  khong_ro?: number;
  needs_review?: number;
  clarity_risk: number;
}

interface ListResp<T> {
  items: T[];
  total: number;
}

function topicLabel(t: Topic): string {
  return t.ten ?? t.name ?? t.chu_de ?? t.slug ?? 'Chủ đề';
}

function topicKey(t: Topic): string {
  return (t.slug ?? t.chu_de ?? topicLabel(t)).toLowerCase();
}

type FgNode = {
  id: string;
  name: string;
  kind: 'topic' | 'issue';
  val: number;
  count: number;
};

type FgLink = { source: string; target: string; label: string };

/** Keyword bubbles sized by post volume + force-graph + topic clarity risk. */
export function SocialInsightsPanel() {
  const [topics, setTopics] = useState<Topic[]>([]);
  const [posts, setPosts] = useState<Post[]>([]);
  const [clarity, setClarity] = useState<ClarityItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dims, setDims] = useState({ width: 720, height: 420 });
  const graphWrap = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    Promise.all([
      apiGet<ListResp<Topic>>('/admin/social/topics'),
      apiGet<ListResp<Post>>('/admin/social/posts'),
      apiGet<{ items: ClarityItem[] }>('/admin/social/clarity-index?min_volume=1').catch(() => ({ items: [] })),
    ])
      .then(([t, p, c]) => {
        if (!alive) return;
        setTopics(t.items ?? []);
        setPosts(p.items ?? []);
        setClarity(c.items ?? []);
        setError(null);
      })
      .catch((e) => {
        if (!alive) return;
        setError(e instanceof Error ? e.message : 'Không tải được dữ liệu radar');
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    const el = graphWrap.current;
    if (!el) return;
    const ro = new ResizeObserver(() => {
      setDims({ width: el.clientWidth || 720, height: Math.max(360, el.clientHeight || 420) });
    });
    ro.observe(el);
    setDims({ width: el.clientWidth || 720, height: Math.max(360, el.clientHeight || 420) });
    return () => ro.disconnect();
  }, [loading]);

  const ranked = useMemo(() => {
    const fromApi = topics
      .map((t) => ({
        key: topicKey(t),
        label: topicLabel(t),
        count: Number(t.post_count ?? t.so_bai ?? 0),
      }))
      .filter((r) => r.label);

    // Client fallback: derive topics from posts when ChuDe list is empty / zero counts.
    if (!fromApi.length || fromApi.every((r) => r.count === 0)) {
      const counts = new Map<string, { label: string; count: number }>();
      for (const p of posts) {
        const raw = (p.chu_de || p.source_topic || '').trim();
        if (!raw) continue;
        const key = raw.toLowerCase();
        const cur = counts.get(key) ?? { label: raw, count: 0 };
        cur.count += 1;
        counts.set(key, cur);
      }
      if (counts.size) {
        const rows = [...counts.entries()].map(([key, v]) => ({ key, label: v.label, count: v.count }));
        const max = Math.max(1, ...rows.map((r) => r.count));
        return rows.sort((a, b) => b.count - a.count).map((r) => ({ ...r, score: r.count / max }));
      }
    }

    const max = Math.max(1, ...fromApi.map((r) => r.count), 1);
    return fromApi
      .sort((a, b) => b.count - a.count)
      .map((r) => ({ ...r, score: r.count / max }));
  }, [topics, posts]);

  const graphData = useMemo(() => {
    const nodes: FgNode[] = [];
    const links: FgLink[] = [];
    const topicIds = new Set<string>();

    for (const t of ranked.slice(0, 24)) {
      const id = `topic:${t.key}`;
      topicIds.add(id);
      nodes.push({
        id,
        name: t.label,
        kind: 'topic',
        count: t.count,
        val: 6 + t.score * 18,
      });
    }

    const issueMap = new Map<string, { label: string; topics: Set<string>; n: number }>();
    for (const p of posts) {
      const topic = (p.chu_de || p.source_topic || '').trim().toLowerCase();
      if (!topic) continue;
      const tid = `topic:${topic}`;
      if (!topicIds.has(tid)) continue;
      const raw = (p.source_query || p.video_title || '').trim();
      if (!raw) continue;
      const label = raw.length > 42 ? `${raw.slice(0, 40)}…` : raw;
      const key = label.toLowerCase();
      const cur = issueMap.get(key) ?? { label, topics: new Set<string>(), n: 0 };
      cur.topics.add(tid);
      cur.n += 1;
      issueMap.set(key, cur);
    }

    const issues = [...issueMap.entries()]
      .sort((a, b) => b[1].n - a[1].n)
      .slice(0, 28);

    for (const [key, issue] of issues) {
      const iid = `issue:${key}`;
      nodes.push({
        id: iid,
        name: issue.label,
        kind: 'issue',
        count: issue.n,
        val: 4 + Math.min(12, issue.n * 1.5),
      });
      for (const tid of issue.topics) {
        links.push({ source: tid, target: iid, label: 'liên quan' });
      }
    }

    const co = new Map<string, number>();
    for (const issue of issueMap.values()) {
      const ts = [...issue.topics];
      for (let i = 0; i < ts.length; i++) {
        for (let j = i + 1; j < ts.length; j++) {
          const a = ts[i] < ts[j] ? ts[i] : ts[j];
          const b = ts[i] < ts[j] ? ts[j] : ts[i];
          const k = `${a}|${b}`;
          co.set(k, (co.get(k) ?? 0) + 1);
        }
      }
    }
    for (const [k, n] of [...co.entries()].sort((a, b) => b[1] - a[1]).slice(0, 12)) {
      if (n < 1) continue;
      const [a, b] = k.split('|');
      links.push({ source: a, target: b, label: 'cùng vấn đề' });
    }

    return { nodes, links };
  }, [ranked, posts]);

  const riskColor = (r: number) => (r >= 0.66 ? 'bg-red-500' : r >= 0.33 ? 'bg-amber-500' : 'bg-emerald-500');
  const riskText = (r: number) => (r >= 0.66 ? 'text-red-600' : r >= 0.33 ? 'text-amber-600' : 'text-emerald-600');

  if (loading) {
    return (
      <div className="flex items-center justify-center gap-2 rounded-2xl border border-slate-200 bg-white py-16 text-sm font-semibold text-slate-400">
        <Spinner size={20} className="animate-spin" /> Đang dựng bản đồ vấn đề…
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold text-red-700">
        {error}
      </div>
    );
  }

  if (ranked.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-12 text-center text-sm font-semibold text-slate-500">
        <WarningCircle size={28} className="mx-auto mb-2 text-slate-300" />
        Chưa có chủ đề để vẽ bubble / đồ thị. Cấu hình{' '}
        <code className="font-mono text-xs">BE2_SOCIAL_MONITOR_TOPICS</code> rồi bấm Crawl (không dùng dry-run).
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <section className="overflow-hidden rounded-[1.75rem] border border-violet-200 bg-white shadow-sm">
        <div className="flex items-center gap-2 border-b border-violet-100 bg-violet-50/60 px-5 py-4">
          <Gauge size={18} className="text-violet-600" weight="fill" />
          <h2 className="text-base font-black text-slate-900">Chỉ số mù mờ pháp lý (theo chủ đề)</h2>
          <span className="ml-auto text-xs font-semibold text-violet-600/80">Từ radar MXH</span>
        </div>
        <div className="p-5">
          <p className="mb-4 text-sm font-medium text-slate-500">
            Tỷ lệ đối chiếu mâu thuẫn / không rõ (hoặc bài cần duyệt) theo từng chủ đề giám sát — tín hiệu truyền thông, không phải kết luận luật sai.
          </p>
          {clarity.length === 0 ? (
            <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50 px-4 py-8 text-center text-sm font-semibold text-slate-400">
              Chưa đủ dữ liệu đối chiếu. Sau khi crawl có bài gắn chủ đề, chỉ số sẽ xuất hiện tại đây.
            </div>
          ) : (
            <div className="space-y-3">
              {clarity.slice(0, 12).map((it) => (
                <div key={it.slug ?? it.ten} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                  <div className="mb-2 flex items-start justify-between gap-3">
                    <div>
                      <p className="font-bold text-slate-800">{it.ten ?? it.slug}</p>
                      <p className="mt-0.5 text-xs font-semibold text-slate-400">
                        {it.volume} bài · {it.doi_chieu ?? 0} đối chiếu · {it.needs_review ?? 0} cần duyệt
                      </p>
                    </div>
                    <div className="text-right">
                      <div className={`text-2xl font-black ${riskText(it.clarity_risk)}`}>
                        {Math.round(it.clarity_risk * 100)}%
                      </div>
                      <div className="text-[10px] font-bold uppercase tracking-wide text-slate-400">rủi ro mù mờ</div>
                    </div>
                  </div>
                  <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
                    <div
                      className={`h-full rounded-full ${riskColor(it.clarity_risk)}`}
                      style={{ width: `${Math.max(2, it.clarity_risk * 100)}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

      <section className="overflow-hidden rounded-[1.75rem] border border-slate-200 bg-white shadow-sm">
        <div className="flex items-center gap-2 border-b border-slate-100 px-5 py-4">
          <Hash size={18} className="text-sky-600" weight="bold" />
          <h2 className="text-base font-black text-slate-900">Từ khóa nổi bật</h2>
          <span className="ml-auto text-xs font-semibold text-slate-400">Bubble theo số bài</span>
        </div>
        <div className="relative min-h-[220px] bg-gradient-to-b from-slate-50 to-white p-5">
          <div className="flex flex-wrap items-center justify-center gap-3 py-2">
            {ranked.slice(0, 18).map((t) => {
              const size = 56 + Math.max(0.15, t.score) * 88;
              return (
                <div
                  key={t.key}
                  title={`${t.label}: ${t.count} bài`}
                  className="ls-keyword-bubble group relative flex items-center justify-center rounded-full border border-sky-200/80 bg-gradient-to-br from-sky-50 via-white to-orange-50 shadow-sm transition hover:-translate-y-1 hover:shadow-md"
                  style={{ width: size, height: size, minWidth: size }}
                >
                  <div className="px-2 text-center">
                    <p className="line-clamp-2 text-[11px] font-extrabold leading-tight text-slate-800 sm:text-xs">
                      {t.label}
                    </p>
                    <p className="mt-0.5 text-[10px] font-bold text-sky-600">{t.count}</p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      <section className="overflow-hidden rounded-[1.75rem] border border-slate-200 bg-white shadow-sm">
        <div className="flex items-center gap-2 border-b border-slate-100 px-5 py-4">
          <Graph size={18} className="text-violet-600" weight="bold" />
          <h2 className="text-base font-black text-slate-900">Đồ thị liên kết vấn đề</h2>
          <span className="ml-auto text-xs font-semibold text-slate-400">
            Chủ đề ↔ cụm vấn đề (query / video)
          </span>
        </div>
        <div className="flex flex-wrap gap-3 border-b border-slate-50 px-5 py-2 text-[11px] font-bold text-slate-500">
          <span className="inline-flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full bg-sky-500" /> Chủ đề
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full bg-violet-500" /> Vấn đề / query
          </span>
        </div>
        <div ref={graphWrap} className="h-[420px] w-full bg-[#F8FAFC]">
          {graphData.nodes.length > 0 ? (
            <ForceGraph2D
              width={dims.width}
              height={dims.height}
              graphData={graphData}
              nodeLabel={(n: any) => `${n.name} (${n.count})`}
              linkColor={() => 'rgba(100,116,139,0.35)'}
              linkWidth={1.2}
              cooldownTicks={80}
              backgroundColor="#F8FAFC"
              nodeCanvasObject={(node: any, ctx, globalScale) => {
                const r = Math.max(4, (node.val || 6) / globalScale);
                ctx.beginPath();
                ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
                ctx.fillStyle = node.kind === 'topic' ? '#0EA5E9' : '#8B5CF6';
                ctx.fill();
                ctx.strokeStyle = '#fff';
                ctx.lineWidth = 1.5 / globalScale;
                ctx.stroke();
                if (globalScale > 0.65) {
                  const label = String(node.name || '').slice(0, 28);
                  ctx.font = `${11 / globalScale}px Be Vietnam Pro, sans-serif`;
                  ctx.textAlign = 'center';
                  ctx.textBaseline = 'top';
                  ctx.fillStyle = '#334155';
                  ctx.fillText(label, node.x, node.y + r + 2 / globalScale);
                }
              }}
            />
          ) : (
            <div className="flex h-full items-center justify-center text-sm font-semibold text-slate-400">
              Chưa đủ liên kết vấn đề từ bài đăng.
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
