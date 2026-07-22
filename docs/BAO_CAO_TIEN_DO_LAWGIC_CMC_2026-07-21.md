# Báo cáo tiến độ nâng cấp CMC theo lõi LAWGIC

**Cập nhật:** 21/07/2026
**Trạng thái tổng thể:** Đã hoàn thành L0–L6.2B và L7.1A trong phạm vi code/kiểm thử. L6.2 đã được hardening thêm về lineage, checksum và chống bài đăng lại làm phồng cảnh báo. Bộ evaluation, CI, acceptance catalog và demo contract đã có; release vẫn `NO_GO` cho đến khi có holdout độc lập và bằng chứng từ datastore thật. Mọi feature flag vẫn tắt; chưa áp schema/migration hoặc ghi thay đổi lên môi trường thật.

## Mục tiêu

CMC được nâng cấp để có ba đặc tính lõi của LAWGIC:

1. Hiểu đúng quy định theo thời điểm hiệu lực, đến cấp Điều–Khoản–Điểm.
2. Trả lời có căn cứ pháp lý chuẩn, lấy nguyên văn từ Neo4j thay vì tin vào vector database hoặc output của mô hình.
3. Phát hiện và xử lý hiểu nhầm, đặc biệt trường hợp thông tin từng đúng nhưng đã lỗi thời do luật mới thay đổi.

## Những phần đã hoàn thành

| Phase | Kết quả đã có | Trạng thái |
|---|---|---|
| L0 | Contract pháp lý bất biến, ontology v2, constraints/index additive, fixture thời gian, feature flags | Hoàn thành |
| L1 | Parser giữ Điều–Khoản–Điểm; immutable Neo4j writer, checksum và conflict guard | Hoàn thành trong code |
| L2 | Qdrant `legal_provision`, dual-index, migration/reindex dry-run, báo cáo parity Neo4j–Qdrant | Hoàn thành phần chuẩn bị; chưa chạy apply lên môi trường thật |
| L3 | `TemporalLawService`, truy vấn `law_as_of`, timeline, compare và API read-only Admin/Citizen | Hoàn thành |
| L4 | Hybrid retrieval, Citation Contract v2, strict refusal, giao diện citation/timeline | Hoàn thành trong code; flags vẫn tắt |
| L5.1 | Amendment preview: parser, matcher, classifier, API Admin, fail-closed review | Hoàn thành |
| L5.2 | PostgreSQL review batch/candidate/audit, idempotency, revision guard và API pháp chế | Hoàn thành |
| L5.3 | Commit Neo4j theo transaction, reconciliation PostgreSQL và giao diện Admin review | Hoàn thành trong code; flag vẫn tắt |
| L6.1 | Evidence source-neutral, `Misconception` clustering, alert linkage và API Admin | Hoàn thành trong code; flag vẫn tắt |
| L6.2/L6.2B | Verdict hai thời điểm, old/new evidence, risk score, chống lệch lineage và chống bài đăng lại làm phồng cảnh báo | Hoàn thành và hardening trong code; flag vẫn tắt |
| L7.1A | Evaluation 8 suite, release gates, T01–T20/N01–N02, CI và ba demo khóa | Hoàn thành contract/smoke; release evidence vẫn `NO_GO` |

### 1. Temporal legal graph

- Mỗi phiên bản Điều, Khoản hoặc Điểm có ID vật lý bất biến, `lineage_id`, checksum và khoảng hiệu lực nửa mở.
- Cùng một câu hỏi có thể trả về quy định khác nhau theo ngày hỏi.
- Sửa đổi một Điểm không làm mất hiệu lực các Điểm khác trong cùng Khoản.
- Citizen chỉ đọc dữ liệu `public + approved`; API lịch sử và so sánh đã có sẵn nhưng vẫn nằm sau feature flags.

### 2. Retrieval và citation có căn cứ

- Qdrant chỉ tìm candidate ID; Neo4j là nguồn nguyên văn duy nhất cho citation.
- Citation v2 kiểm tra node vật lý đúng phiên bản, ngày hiệu lực, checksum, trích đoạn nguyên văn, mapping claim–citation và entailment.
- Nếu không đủ căn cứ, node giả, sai ngày hoặc quote không khớp, QA trả về `refused` thay vì tạo citation giả.
- Frontend đã đọc được cả response v1 lẫn Citation Contract v2, hiển thị Điều/Khoản/Điểm, khoảng hiệu lực, `as_of`, timeline và version diff.

### 3. Cảnh báo hiểu nhầm: nền tảng news-first

- Pipeline ingest, claim check, alert signal, admin alerts và citizen/admin UI đã được nâng cấp trong các phase trước.
- Nền tảng hiện hỗ trợ review có nguồn gốc, mức độ rủi ro và luồng xuất bản có kiểm duyệt.
- Temporal verdict `OUTDATED_BUT_PREVIOUSLY_TRUE` đã được triển khai trong L6.2, nối claim với cả quy định tại ngày đăng và quy định hiện hành.
- L6.1 gom nhiều claim occurrence từ bài báo/MXH vào một `Misconception` có provenance; L6.2/L6.2B bổ sung temporal verdict, risk và các guard lineage/syndication.
- L6.2 đã đối chiếu từng occurrence tại ngày đăng và hiện tại, lưu cả hai căn cứ bất biến và chỉ kết luận lỗi thời khi đủ điều kiện chặt.

### 4. Amendment Preview Engine (L5.1)

- Phân tích chỉ dẫn sửa đổi tiếng Việt ở cấp Điều/Khoản/Điểm và thay thế cụm từ được trích dẫn.
- Hydrate toàn bộ candidate old/new theo immutable ID từ Neo4j trước khi so khớp.
- Chấm điểm có thể giải thích bằng: dẫn chiếu tường minh, tọa độ pháp lý, cấp node, tương đồng văn bản, số liệu và thuật ngữ pháp lý.
- Phân loại bảo thủ: `UNCHANGED`, `REWORDED`, `TIGHTENED`, `LOOSENED`, `ADDED`, `REMOVED`, `SPLIT`, `MERGED`, `UNCERTAIN`.
- Split/merge, tọa độ thiếu, ngày không hợp lệ, candidate sai văn bản hoặc phrase không khớp nguyên văn đều buộc review.
- Endpoint Admin: `POST /admin/legal/amendments/preview`.

### 5. Amendment Review Workflow (L5.2)

- Lưu batch, candidate và audit event bằng migration `011_amendment_reviews.sql`.
- Tạo batch idempotent bằng request hash; tái sử dụng key cho request khác trả về conflict.
- Dùng revision guard cho mọi thay đổi candidate và chuyển trạng thái batch.
- Workflow hiện tại: `draft → in_review → approved/rejected`.
- Reviewer được chỉnh cặp old/new, ngày hiệu lực, loại thay đổi và quyết định candidate.
- Khi đổi cặp, hệ thống xóa score/reference cũ, tính lại diff và buộc mandatory review.
- Chỉ vai trò `admin_phap_che` được sử dụng API review persistence.
- Trạng thái `approved` chỉ là đã duyệt trong PostgreSQL, không phải đã commit vào Neo4j.

### 6. Transactional Amendment Commit và Admin UI (L5.3)

- Chỉ các candidate đã được reviewer chấp nhận và có loại thay đổi xác định mới được commit: `REWORDED`, `TIGHTENED`, `LOOSENED`, `ADDED`, `REMOVED`.
- `UNCHANGED`, `SPLIT`, `MERGED`, `UNCERTAIN`, sai lineage/cấp node/ngày/checksum đều bị từ chối trước khi ghi graph.
- Hệ thống đọc lại phiên bản canonical ngay trước commit và ghi toàn bộ batch trong một managed transaction Neo4j.
- Transaction đóng interval cũ, duyệt phiên bản mới và tạo `SUPERSEDED_BY`/`AMENDED_BY`; một conflict làm rollback toàn batch.
- Cạnh graph mang `review_id` và `commit_key`. Nếu graph thành công nhưng PostgreSQL reconciliation lỗi, retry cùng key hoàn tất PostgreSQL mà không tạo cạnh trùng.
- Migration `012_amendment_commits.sql` lưu actor, thời điểm, idempotency key và commit report.
- Endpoint commit chỉ dành cho `admin_phap_che` và chỉ xuất hiện khi toàn bộ legal/preview/review/commit flags được bật.
- Trang Admin mới cho phép xem batch, sửa candidate, xem diff/lý do, submit, approve/reject và xác nhận commit riêng biệt.
- `commit_allowed=false` vẫn được giữ để ngăn auto-commit; endpoint L5.3 là hành động có chủ đích sau human review.

### 7. Misconception Clustering news-first (L6.1)

- Dùng chung `ContentItem` cho bài báo, social post, video/comment và forum; mở rộng nguồn sau này không phải đổi contract lõi.
- Mỗi occurrence bắt buộc có URL canonical, thời điểm đăng có timezone, checksum nội dung, evidence span và offsets khớp nguyên văn.
- Chỉ claim `mau_thuan` đạt confidence threshold mới được đưa vào clustering.
- Cluster được giới hạn theo chủ đề và căn cứ pháp lý. Khác con số hoặc dấu phủ định sẽ tạo cụm riêng để tránh ghép sai nghĩa pháp lý.
- Quan hệ graph: `YKien → INSTANCE_OF → Misconception → CONTRADICTS → LegalProvision|Khoan`.
- Cảnh báo có thể nối bằng `AlertMeta → CANH_BAO_VE → Misconception`; khi flag tắt vẫn dùng grouping topic/Khoản cũ.
- API Admin mới: `GET /admin/misconceptions` và `GET /admin/misconceptions/{id}`.
- L6.1 chưa kết luận claim từng đúng hay không, chưa tính temporal risk score và chưa công khai ra Citizen.

### 8. Temporal Misconception và Explainable Risk (L6.2)

- Mỗi claim được resolve đúng phiên bản pháp luật tại ngày đăng và tại `current_as_of`.
- `OUTDATED_BUT_PREVIOUSLY_TRUE` chỉ xuất hiện khi căn cứ lịch sử `khop`, căn cứ hiện tại `mau_thuan`, cả hai đủ confidence và là hai physical version khác nhau.
- Claim mâu thuẫn ở cả hai thời điểm được gắn `CONTRADICTED`, không bị gắn nhầm là “từng đúng”.
- Thiếu phiên bản pháp luật trả `UNVERIFIABLE`; NLI confidence thấp hoặc cùng một version cho kết quả bất nhất trả `NEEDS_REVIEW`.
- Mỗi lần đánh giá được lưu thành node bất biến với `HISTORICAL_BASIS` và `CURRENT_BASIS`, kèm checksum, model, score và reason codes.
- Risk score trả đủ tám thành phần: legal impact, source reach, contradiction confidence, velocity, source diversity, recent law change, engagement và provenance penalty.
- Alert dùng risk severity khi có temporal assessment; khi flag tắt vẫn dùng logic volume cũ.
- API đánh giá chỉ dành cho `admin_phap_che`; trang Admin hiển thị nguồn gốc, hai căn cứ và đóng góp từng risk factor.
- Chưa publish temporal verdict tự động ra Citizen; publish gate vẫn giữ nguyên.

## Rào an toàn đang áp dụng

```text
AMENDMENT_PREVIEW_V2=false
AMENDMENT_REVIEW_V2=false
AMENDMENT_COMMIT_V2=false
MISCONCEPTION_CLUSTER_V2=false
MISCONCEPTION_TEMPORAL_V2=false
commit_allowed=false
auto_approve_eligible=false
```

- Code đã có đường commit tường minh sau human review, nhưng đường này bị ẩn hoàn toàn khi `AMENDMENT_COMMIT_V2=false`.
- Chưa bật feature flag trong môi trường.
- Không chạy migration `--apply`, không sửa Neo4j/Qdrant live hoặc staging.
- Auto-approve chỉ có thể được xem xét sau khi bộ gold độc lập chứng minh pairing precision tối thiểu 95%.

## Kiểm thử và bằng chứng hiện tại

- 64 kiểm thử tập trung cho amendment commit/review/preview/temporal đã đạt.
- 38 kiểm thử tập trung cho temporal misconception/clustering/news/social đã đạt.
- 298/298 kiểm thử backend đã đạt; Python compileall đã đạt.
- 8/8 kiểm thử contract frontend đã đạt; production build và lint đã đạt.
- Lint còn một cảnh báo Fast Refresh có sẵn trong `CitizenChrome.tsx`, không liên quan phần amendment mới.

### Bổ sung L7.1A

- 8 kiểm thử tập trung cho evaluation/acceptance đã đạt.
- 230 kiểm thử trong bộ backend hiện được thu thập đã đạt; Python compileall đã đạt.
- Smoke evaluation đã qua toàn bộ blocking gate và ghi báo cáo JSON, nhưng kết luận release đúng chủ đích là `NO_GO` vì dữ liệu bundled là synthetic, chưa được review độc lập và chưa đủ cỡ mẫu.
- Catalog có đủ 22 kiểm tra T01–T20 và N01–N02; T20 bảo vệ raw alert/draft không giả dạng nội dung Citizen đã xuất bản.
- 8 kiểm thử contract frontend, production build và lint đã đạt; còn cảnh báo Fast Refresh và bundle size có sẵn, không chặn L7.
- Chưa chạy integration acceptance trên Neo4j/PostgreSQL/Qdrant thật, chưa đo P95 shadow-read thật và chưa bật bất kỳ flag nào.

### Bổ sung hardening L6.2B

- Hai căn cứ historical/current khác lineage bị chuyển thẳng sang `NEEDS_REVIEW`, không thể tạo verdict “từng đúng nhưng đã lỗi thời”.
- Transaction lưu evaluation kiểm tra lại checksum và lineage của cả hai node canonical, đồng thời khóa claim, ngày đăng và ngày đánh giá khi retry.
- `source_count`, velocity, diversity và alert volume dùng `content_hash`, vì vậy nhiều báo đăng lại cùng nội dung chỉ được tính là một nguồn nội dung độc lập.
- Worker truyền `content_hash` xuyên suốt; Admin UI tách rõ số claim, nội dung độc lập và nhà cung cấp.
- T18/T19 đã được siết theo same-lineage và checksum; catalog vẫn đủ 22 kiểm tra.
- Kết quả mới nhất: 54 kiểm thử tập trung đạt, 234 backend tests đạt, 9 frontend contract tests đạt; compile, build và lint đạt.

## Phần cần làm tiếp theo

### L7.1B — Release evidence và rollout

1. Gán nhãn holdout độc lập cho parser, retrieval, temporal QA, citation, amendment, misinformation và safety với hai reviewer cùng bước adjudication.
2. Nạp fixture đã duyệt và chạy T01–T20/N01–N02 read-only trên Neo4j thật; bổ sung parity acceptance cho PostgreSQL/Qdrant.
3. Thực hiện shadow read, đo P95 latency/cost/failure thực, lưu snapshot và báo cáo go/no-go.
4. Chạy lại evaluation bằng `--release`; chỉ cân nhắc bật flag khi kết quả là `GO`.

## Tài liệu liên quan

- [Tiến độ chi tiết Lõi LAWGIC](lawgic-core/PROGRESS.md)
- [Chi tiết triển khai](lawgic-core/IMPLEMENTATION.md)
- [Nghiên cứu và quyết định kỹ thuật](lawgic-core/RESEARCH.md)
- [Kế hoạch thực thi v2](architecture/lawgic-core-execution-plan-v2.md)
- [ADR Amendment có deterministic matching và human review](architecture/adr/003-deterministic-amendment-human-review.md)

## Kết luận

CMC hiện đã có temporal legal core, citation grounding, chuỗi amendment hoàn chỉnh, temporal misconception có risk score giải thích được và cổng evaluation/CI fail-closed. Toàn bộ tính năng mới vẫn tắt mặc định và chưa tác động môi trường thật. Chặng tiếp theo là L7.1B: tạo holdout độc lập, chạy acceptance trên datastore thật, đo shadow-read và chỉ rollout khi báo cáo release trả `GO`.
