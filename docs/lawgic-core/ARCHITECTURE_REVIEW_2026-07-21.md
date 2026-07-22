# LAWGIC Core Architecture Review — 2026-07-21

## Kết luận

Lõi v2 đã bám đúng kiến trúc LAWGIC ở các đường đi chính: dữ liệu pháp luật bất biến, Neo4j canonical, truy vấn nửa mở theo thời điểm, Citation Contract v2 fail-closed, amendment có human review trước graph commit, và misconception dùng hai căn cứ cùng lineage. Trạng thái phát hành vẫn là `NO_GO` vì chưa có holdout pháp lý độc lập và shadow production-like.

## Phạm vi đối chiếu

Review lần theo các luồng runtime từ API đến service, adapter và datastore cho:

1. Immutable Điều–Khoản–Điểm và dual index.
2. TemporalLawService và public visibility.
3. Hybrid retrieval, canonical hydration và Citation Contract v2.
4. Amendment preview/review/commit và reconciliation.
5. Misconception clustering, dual-time verdict và alert aggregation.
6. Publish gate, evaluation gate và feature-flag rollout.

## Ma trận invariant

| Invariant LAWGIC | Kết quả | Bằng chứng chính |
|---|---|---|
| Node pháp luật đã công bố không bị ghi đè | Đạt | Writer preflight checksum/interval/source và managed write transaction |
| Neo4j canonical; Qdrant chỉ discovery ID | Đạt | Qdrant payload không chứa canonical text; citation hydrate lại từ Neo4j |
| `effective_from <= as_of < effective_to` | Đạt | Temporal repository và model cùng kiểm tra khoảng nửa mở |
| Temporal read v2 qua một service | Đạt | API, retrieval, citation, amendment và misconception dùng `TemporalLawService` |
| Citation dùng deepest active leaf | Đạt sau hardening | Retrieval loại node cha khi node con active đã được graph expansion hydrate |
| Citizen QA thiếu căn cứ phải từ chối | Đạt sau hardening | Citation v2 cần đủ read/temporal/strict flags và mọi edge phải qua canonical/NLI validation |
| Amendment không chắc chắn không tự commit | Đạt | Split/merge/uncertain/unchanged bị chặn; chỉ batch approved mới commit |
| Alert không bị syndicated copy thổi volume | Đạt sau hardening | Provenance cần SHA-256 content hash và dedupe theo body + legal/claim identity |
| Release thiếu bằng chứng độc lập phải fail closed | Đạt | `--release` trả non-zero và report giữ `NO_GO` |

## Finding đã sửa

### A1 — Public metadata từng fail-open

- Mức độ: High.
- Bằng chứng: temporal/retrieval query và Qdrant reindex từng dùng `coalesce(..., 'public'/'approved')`.
- Rủi ro: node thiếu metadata có thể trở thành dữ liệu Citizen nhìn thấy.
- Sửa: public read giờ chỉ chấp nhận giá trị `visibility='public'` và `review_status='approved'` được lưu rõ ràng; payload reindex thiếu metadata bị từ chối.
- Confidence: High.

### A2 — Strict-grounding flag chưa tham gia dependency gate

- Mức độ: High.
- Bằng chứng: cấu hình có `QA_STRICT_GROUNDING_V2` nhưng dispatch Citation v2 chỉ kiểm hai read flags.
- Rủi ro: cấu hình tắt strict grounding vẫn có thể chạy đường QA v2.
- Sửa: delegate v2 không được gọi nếu strict grounding không bật; trả refusal contract.
- Confidence: High.

### A3 — Alert provenance chưa bắt buộc content hash

- Mức độ: High.
- Bằng chứng: khi thiếu hash, alert dedupe từng rơi về `ykien_id`/post identity.
- Rủi ro: các bản syndicated giống nhau có thể được tính như nguồn độc lập.
- Sửa: chỉ tín hiệu có content hash SHA-256 hợp lệ mới đủ provenance để tạo alert.
- Confidence: High.

### A4 — Publish và audit chưa nằm trong một transaction rõ ràng

- Mức độ: Medium.
- Bằng chứng: publish update và audit insert dùng cùng connection nhưng không mở transaction; service còn có nhánh báo thành công khi thiếu pool.
- Rủi ro: brief có thể published nhưng audit thất bại, hoặc caller nhận false success khi Postgres không khả dụng.
- Sửa: bắt buộc transactional Postgres; mọi lỗi rollback và trả `PublishGateError`.
- Confidence: High.

### A5 — Retrieval có thể giữ node cha cùng node con

- Mức độ: High.
- Bằng chứng: canonical hydration trước đây không loại Khoản/Điều khi graph expansion đồng thời trả Điểm/Khoản con active.
- Rủi ro: Citation v2 có thể trích node không phải deepest leaf.
- Sửa: sau hydration, loại mọi provision có lineage đang là parent của một active canonical candidate.
- Confidence: High cho trường hợp graph expansion trả đủ quan hệ; Medium cho graph dữ liệu không đầy đủ.

### A6 — Heuristic NLI từng có thể tự xác nhận entailment

- Mức độ: High.
- Bằng chứng: heuristic có thể trả `khop` trên token overlap mà không đặt `needs_review`.
- Rủi ro: nếu operator bật flag v2 trước khi cấu hình model NLI được phê duyệt, Citation v2 hoặc verdict temporal có thể dựa vào heuristic.
- Sửa: Citation v2 từ chối và temporal misconception chuyển sang review khi model là `heuristic-nli`; đường QA v1 tương thích không bị thay đổi trong rollout này.
- Confidence: High.

## Rủi ro còn mở

1. **Release evidence — blocking:** chưa có holdout thật được hai reviewer độc lập gán nhãn, adjudicate và đóng băng checksum.
2. **Production-like performance — blocking:** shadow localhost đạt ngưỡng nhưng không thay thế tải và topology gần production.
3. **Approved NLI model — High:** heuristic đã fail-closed nhưng model production vẫn phải được cấu hình và chứng minh precision/F1 trên holdout trước khi bật Citizen v2 hoặc temporal misconception.
4. **Cross-database amendment reconciliation — Medium:** Neo4j commit rồi PostgreSQL mark-committed là retry-safe saga, không phải distributed transaction. Cần giám sát PG03/PG07 và retry cùng idempotency key.
5. **Legacy QA v1 — Medium:** khi flag v2 tắt, đường tương thích cũ vẫn dùng temporal logic cấp văn bản. Đây là chủ ý rollout, không tương đương partial-amendment LAWGIC; không được coi v1 là bằng chứng hoàn thành v2.
6. **Editorial brief policy — Medium:** brief citations hiện là optional và trạng thái `review` chưa có workflow phê duyệt riêng. Cần quyết định sản phẩm trước khi dùng brief làm kênh đính chính pháp lý công khai.

## Quyết định rollout

- Giữ toàn bộ flag v2 tắt.
- Không đổi `NO_GO` từ bằng chứng local synthetic.
- Chỉ chạy release gate sau independent holdout và production-like shadow.
- Không xóa đường v1 trong cùng release; rollback chỉ tắt read flags.

## Addendum - amendment reconciliation observability

The open cross-database observability item now has a read-only implementation:

- graph commit stamps are scanned with explicit Neo4j read access;
- PostgreSQL status, idempotency key, actor/time/result metadata and the `graph_commit_reconciled` audit event are cross-checked;
- missing or mismatched evidence returns `degraded` and is logged by an opt-in legal-worker job;
- no automatic repair occurs, so canonical legal state cannot be changed by monitoring.

The architectural risk is reduced from undetected drift to an observable retry-safe saga. It remains a saga rather than a distributed transaction; operational retry must use the same idempotency key. The local live scan returned `healthy` with one commit and zero issues.
