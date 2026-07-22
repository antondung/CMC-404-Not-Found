// LAWGIC core v2 acceptance queries (T01-T15).
// Parameters are supplied by the temporal fixture loader. These queries are read-only.

// T01 — parser/writer preserved every Điểm expected for one Khoản.
MATCH (k:LegalProvision:Khoan {lineage_id: $khoan_lineage})-[:CO_DIEM]->(p:LegalProvision:Diem)
RETURN collect(DISTINCT p.lineage_id) AS diem_lineages, count(DISTINCT p) AS diem_count;

// T02 — deepest leaf: a Khoản with active Điểm must not be returned as a leaf.
MATCH (k:LegalProvision:Khoan {lineage_id: $khoan_lineage})
WHERE date(k.effective_from) <= date($as_of)
  AND (k.effective_to IS NULL OR date($as_of) < date(k.effective_to))
OPTIONAL MATCH (k)-[:CO_DIEM]->(p:LegalProvision:Diem)
WHERE date(p.effective_from) <= date($as_of)
  AND (p.effective_to IS NULL OR date($as_of) < date(p.effective_to))
RETURN k.provision_id AS khoan_id, collect(p.provision_id) AS active_diem_ids;

// T03 — a Khoản without active Điểm is itself a leaf.
MATCH (k:LegalProvision:Khoan {lineage_id: $leaf_khoan_lineage})
WHERE date(k.effective_from) <= date($as_of)
  AND (k.effective_to IS NULL OR date($as_of) < date(k.effective_to))
  AND NOT EXISTS {
    MATCH (k)-[:CO_DIEM]->(p:LegalProvision:Diem)
    WHERE date(p.effective_from) <= date($as_of)
      AND (p.effective_to IS NULL OR date($as_of) < date(p.effective_to))
  }
RETURN k.provision_id AS leaf_id;

// T04 — an Điều without active Khoản is itself a leaf.
MATCH (d:LegalProvision:Dieu {lineage_id: $leaf_dieu_lineage})
WHERE date(d.effective_from) <= date($as_of)
  AND (d.effective_to IS NULL OR date($as_of) < date(d.effective_to))
  AND NOT EXISTS {
    MATCH (d)-[:CO_KHOAN]->(k:LegalProvision:Khoan)
    WHERE date(k.effective_from) <= date($as_of)
      AND (k.effective_to IS NULL OR date($as_of) < date(k.effective_to))
  }
RETURN d.provision_id AS leaf_id;

// T05 — partial amendment changes only Điểm a; Điểm b stays open-ended.
MATCH (a:LegalProvision:Diem {lineage_id: $diem_a_lineage})
MATCH (b:LegalProvision:Diem {lineage_id: $diem_b_lineage})
RETURN collect(a.provision_id) AS diem_a_versions,
       collect(b.provision_id) AS diem_b_versions,
       collect(b.effective_to) AS diem_b_effective_to;

// T06 — V1 → V2 → V3 is ordered and contains no directed cycle.
MATCH path=(first:LegalProvision {lineage_id: $lineage})-[:SUPERSEDED_BY*1..10]->(last:LegalProvision)
WHERE NOT EXISTS { MATCH (:LegalProvision)-[:SUPERSEDED_BY]->(first) }
  AND NOT EXISTS { MATCH (last)-[:SUPERSEDED_BY]->(:LegalProvision) }
RETURN [node IN nodes(path) | node.provision_id] AS version_path,
       length(path) AS hops;

// T07 — future-effective versions are absent before their start date.
MATCH (p:LegalProvision {lineage_id: $future_lineage})
WHERE date(p.effective_from) <= date($as_of)
  AND (p.effective_to IS NULL OR date($as_of) < date(p.effective_to))
RETURN collect(p.provision_id) AS active_ids;

// T08 — repealed provisions are absent at and after exclusive effective_to.
MATCH (p:LegalProvision {lineage_id: $repealed_lineage})
WHERE date(p.effective_from) <= date($as_of)
  AND (p.effective_to IS NULL OR date($as_of) < date(p.effective_to))
RETURN collect(p.provision_id) AS active_ids;

// T09 — provision_id is globally unique after repeated ingest.
MATCH (p:LegalProvision)
WITH p.provision_id AS id, count(*) AS occurrences
WHERE occurrences > 1
RETURN id, occurrences;

// T10 — every v2 provision has canonical text/checksum, interval start and explicit publication metadata.
MATCH (p:LegalProvision)
WHERE p.noi_dung IS NULL
   OR p.text_checksum IS NULL
   OR p.effective_from IS NULL
   OR p.visibility IS NULL
   OR p.review_status IS NULL
RETURN p.provision_id AS invalid_id, labels(p) AS labels;

// T11 — canonical citation material is loaded from Neo4j by physical ID, never Qdrant text.
MATCH (p:LegalProvision {provision_id: $citation_node_id})
RETURN p.provision_id AS node_id,
       coalesce(p.noi_dung, p.tieu_de, '') AS canonical_text,
       p.text_checksum AS text_checksum,
       p.source_checksum AS source_checksum;

// T12 — a fabricated physical node resolves to zero canonical rows.
OPTIONAL MATCH (p:LegalProvision {provision_id: $fabricated_node_id})
RETURN count(p) AS canonical_node_count;

// T13 — an exact physical citation node must itself be effective at as_of.
MATCH (p:LegalProvision {provision_id: $citation_node_id})
WHERE date(p.effective_from) <= date($as_of)
  AND (p.effective_to IS NULL OR date($as_of) < date(p.effective_to))
  AND p.visibility = 'public'
  AND p.review_status = 'approved'
RETURN p.provision_id AS active_citation_node_id;

// T14 — the proposed quote must be an exact canonical substring after application normalization.
MATCH (p:LegalProvision {provision_id: $citation_node_id})
WHERE coalesce(p.noi_dung, p.tieu_de, '') CONTAINS $exact_quote
RETURN p.provision_id AS quote_valid_node_id;

// T15 — return canonical premise for claim-level NLI; service must refuse non-entailed edges.
MATCH (p:LegalProvision {provision_id: $citation_node_id})
RETURN p.provision_id AS node_id,
       coalesce(p.noi_dung, p.tieu_de, '') AS nli_premise,
       $claim_text AS nli_hypothesis;

// T16 — an approved deterministic amendment is committed with a closed interval
// and retry identity on both temporal edges.
MATCH (old:LegalProvision {provision_id: $old_provision_id})
      -[superseded:SUPERSEDED_BY]->
      (new:LegalProvision {provision_id: $new_provision_id})
MATCH (old)-[amended:AMENDED_BY]->(source:VanBanPhapLuat {vb_id: $source_vb_id})
WHERE old.effective_to = new.effective_from
  AND superseded.review_id = $review_id
  AND superseded.commit_key = $commit_key
  AND amended.review_id = $review_id
  AND amended.commit_key = $commit_key
RETURN old.provision_id AS old_id,
       new.provision_id AS new_id,
       source.vb_id AS source_vb_id,
       superseded.change_type AS change_type;

// T17 — split/merge/uncertain reviews must never produce an automatic
// SUPERSEDED_BY edge. A non-empty result is an acceptance failure.
MATCH (:LegalProvision)-[edge:SUPERSEDED_BY]->(:LegalProvision)
WHERE edge.review_id = $ambiguous_review_id
RETURN edge.review_id AS invalid_review_id, edge.change_type AS invalid_change_type;

// N01 — every misconception occurrence retains source-neutral provenance and
// a canonical legal contradiction anchor.
MATCH (content:BaiDang:NoiDungNguon)-[:CO_YKIEN]->(claim:YKien)
      -[instance:INSTANCE_OF]->(misconception:Misconception)
MATCH (misconception)-[:CONTRADICTS]->(legal)
WHERE instance.content_id = content.content_id
  AND instance.canonical_url IS NOT NULL
  AND instance.content_hash IS NOT NULL
  AND instance.published_at IS NOT NULL
  AND instance.evidence_start IS NOT NULL
  AND instance.evidence_end > instance.evidence_start
RETURN content.content_id AS content_id,
       claim.uuid AS claim_occurrence_id,
       misconception.uuid AS misconception_id,
       coalesce(legal.provision_id, legal.khoan_id) AS legal_anchor_id;

// N02 — a claim occurrence must not be assigned to competing clusters.
// Any returned row is an acceptance failure.
MATCH (claim:YKien)-[:INSTANCE_OF]->(misconception:Misconception)
WITH claim.uuid AS claim_occurrence_id, count(DISTINCT misconception) AS cluster_count
WHERE cluster_count > 1
RETURN claim_occurrence_id, cluster_count;

// T18 — a claim that was supported at publication but contradicted by a
// different current version is explicitly backed by both immutable versions.
MATCH (claim:YKien)-[:HAS_TEMPORAL_EVALUATION]->
      (evaluation:TemporalMisconceptionEvaluation {
        verdict: 'OUTDATED_BUT_PREVIOUSLY_TRUE'
      })
MATCH (evaluation)-[:HISTORICAL_BASIS]->(old:LegalProvision)
MATCH (evaluation)-[:CURRENT_BASIS]->(current:LegalProvision)
WHERE evaluation.historical_label = 'khop'
  AND evaluation.current_label = 'mau_thuan'
  AND evaluation.historical_checksum = old.text_checksum
  AND evaluation.current_checksum = current.text_checksum
  AND evaluation.historical_lineage_id = old.lineage_id
  AND evaluation.current_lineage_id = current.lineage_id
  AND old.lineage_id = current.lineage_id
  AND old.provision_id <> current.provision_id
RETURN claim.uuid AS claim_occurrence_id,
       old.provision_id AS historical_id,
       current.provision_id AS current_id;

// T19 — an outdated verdict without two valid immutable bases is forbidden.
// Any returned row is an acceptance failure.
MATCH (evaluation:TemporalMisconceptionEvaluation {
  verdict: 'OUTDATED_BUT_PREVIOUSLY_TRUE'
})
OPTIONAL MATCH (evaluation)-[:HISTORICAL_BASIS]->(old:LegalProvision)
OPTIONAL MATCH (evaluation)-[:CURRENT_BASIS]->(current:LegalProvision)
WITH evaluation, collect(DISTINCT old) AS old_versions,
     collect(DISTINCT current) AS current_versions
WITH evaluation, old_versions, current_versions,
     head(old_versions) AS old_version,
     head(current_versions) AS current_version
WHERE size(old_versions) <> 1 OR size(current_versions) <> 1
   OR coalesce(evaluation.historical_checksum, '') <> coalesce(old_version.text_checksum, '')
   OR coalesce(evaluation.current_checksum, '') <> coalesce(current_version.text_checksum, '')
   OR coalesce(evaluation.historical_lineage_id, '') <> coalesce(old_version.lineage_id, '')
   OR coalesce(evaluation.current_lineage_id, '') <> coalesce(current_version.lineage_id, '')
   OR coalesce(old_version.lineage_id, '') <> coalesce(current_version.lineage_id, '')
RETURN evaluation.evaluation_id AS invalid_evaluation_id;

// T20 — raw alerts or unreviewed correction drafts must never masquerade as
// published citizen briefs. Any returned row is an acceptance failure.
MATCH (raw)
WHERE (raw:AlertMeta OR raw:DeXuatDinhChinh)
  AND raw:BaiTomTat
  AND raw.status = 'published'
RETURN coalesce(raw.uuid, elementId(raw)) AS leaked_raw_item_id, labels(raw) AS labels;
