# Báo cáo cá nhân — K4-L3A Day 13 Monitoring & LLMOps

## 1. Thông tin học viên

- **Họ và tên:** Đỗ Trình Huy Hoàng
- **MSSV:** 2A202602392
- **Lớp:** K4-L3A
- **Repository URL:** https://github.com/HuyHoang1977/K4-L3-DAY13-DoTrinhHuyHoang-2A202602392-Monitoring-LLMOps
- **Commit SHA cuối:** `b2f6812` — đây là commit chứa toàn bộ source + 14 ảnh evidence.
  Dòng này nằm ở commit kế tiếp nên không thể tự trỏ SHA của chính nó (sửa nội dung commit
  làm SHA đổi); SHA commit cuối cùng của nhánh `main` xem bằng `git log -1 --oneline`.
- **Challenge ID:** chưa nhận challenge chính thức từ Lab Coach; phần điều tra chạy
  bằng **practice scenario `rag_slow`** (`scripts/inject_incident.py --scenario rag_slow`).
  Khi nhận được `config/challenge.json` riêng thì chạy lại `--challenge` và cập nhật mục 7.
- **Tên project Langfuse cá nhân:** `day13-k4-l3a-2A202602392`

## 2. Evidence index

| Evidence | Đường dẫn | Nội dung |
|---|---|---|
| Pytest cuối | `evidence/01-pytest.png` | 42 passed |
| Log validator | `evidence/02-log-validator.png` | 100/100, 0 PII leak |
| Dashboard validator | `evidence/03-dashboard-validator.png` | Hợp lệ 6/6 panel |
| Structured log | `evidence/04-structured-log.png` | JSON Lines + correlation ID + enrichment |
| PII redaction | `evidence/05-pii-redaction.png` | đối chiếu PII gửi vào → giá trị trong log |
| Trace list | `evidence/06-trace-list.png` | 86 root trace, filter `isRootObservation:true` |
| Trace waterfall | `evidence/07-trace-waterfall.png` | span tree `lab-agent-run` → `llm-call`, `retrieval` |
| Trace metadata | `evidence/08-trace-metadata.png` | trace ID `6418f8df71bfb8540a1d23eeda16f40b`, 0.15s, $0.001953, 175 tokens |
| Prompt versions | `evidence/09-prompt-versions.png` | v1 `production`+`baseline`, v2 `candidate` |
| Prompt rollback | `evidence/10-prompt-rollback.png` | `production` đã trả về v1 |
| Dashboard runtime | `evidence/11-dashboard-overview.png` | số 6 panel healthy vs incident |
| Incident metric | `evidence/12-incident-metric.png` | timeline metric trước/trong/sau |
| Incident log | `evidence/13-incident-log.png` | log line + correlation ID bị ảnh hưởng |
| Incident trace | `evidence/14-incident-trace.png` | timeline: `lab-agent-run` 2.65s → `retrieval` 2.50s + `llm-call` 153ms |

> 4 file `06`, `07`, `08`, `14` là checklist có sẵn correlation ID cụ thể: Langfuse Cloud đã
> bỏ API đọc trace (`GET /api/public/traces` trả `410 LEGACY_API_UNAVAILABLE`), nên trace ID
> phải lấy từ giao diện web. Chụp xong thì thay `.txt` bằng `.png` và cập nhật bảng trên.

## 3. Kết quả kỹ thuật

| Nội dung | Baseline | Kết quả cuối | Nhận xét |
|---|---|---|---|
| `validate_logs.py` | 30/100 | **100/100** | +70 điểm: thêm correlation ID và context enrichment |
| `validate_dashboard.py` | Hợp lệ 6/6 | Hợp lệ 6/6 | Contract có sẵn ở starter; việc của tôi là chọn nguồn dữ liệu, ngưỡng và bổ sung số liệu runtime |
| `pytest` | 22 passed | **42 passed** | +20 test cho correlation ID và PII Vi Nam |
| Số traces hợp lệ | 0 (không có trường cần thiết) | 76 request → 76 trace root, cùng correlation ID (78 ID trong log) | đủ ≥ 10 trace |
| Số PII leak | 0 (nhưng vì log không ghi message) | **0** trên 190 dòng log | lần này là 0 *thật*, vì message có ghi và đã scrub |
| Latency P95 / TTFT P95 (healthy) | 6767ms / 51ms | **1284ms / 51ms** | baseline P95 lệch do cold start fetch prompt |
| Latency P95 khi incident | — | 6907ms | vượt ngưỡng SLO 3000ms |
| Retrieval success rate | 100% | 100% (healthy), 100% (incident, chỉ chậm) | đây là lý do cần `tool_success_rate` trong panel errors |
| Cost / tokens (healthy) | 0.0229 USD / 1797 | 0.1189 USD / 10313 | 62 request, không retry loop |

Baseline đo bằng cách clone commit starter `13b6066` ra thư mục tạm, chạy API riêng ở
port 8001 với đúng workload rồi chạy validator — không sử dụng server đã sửa.

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:** `app/middleware.py` đọc header `x-request-id`
  do client gửi, nếu không có thì sinh `req-<8 hex>`, lưu vào `request.state.correlation_id`
  và bind vào `structlog.contextvars` (kèm xóa context cũ ở đầu mỗi request để không dính
  context của request trước). ID được trả lại cho client qua header `x-request-id` và
  xuất hiện ở mọi log line của request đó.
- **Các metadata được ghi vào structured log:** `event`, `service`, `correlation_id`,
  `user_id_hash` (SHA-256 12 ký tự), `session_id`, `feature`, `model`, `env`, `level`, `ts`,
  và với `response_sent`: `latency_ms`, `ttft_ms`, `tokens_in`, `tokens_out`, `cost_usd`,
  `quality_score`, `tool_name`, `tool_success`, `payload.answer_preview`.
- **Cách bảo đảm PII được scrub trước khi ghi:** `app/logging_config.py` chạy
  `app/pii.scrub_text` **trước** bước serialize JSON và trước khi render ra console;
  `app/main.py` chỉ đưa `summarize_text()` (đã scrub + cắt 80 ký tự) vào `payload`;
  `app/agent.py` đặt `capture_input=False`, `capture_output=False`, `input=None`,
  `output=None` nên prompt/output thô không lên trace. `app/pii.py` có pattern cho email,
  SĐT Việt Nam, CCCD, thẻ, CMND, hộ chiếu, GPLX, bảo hiểm y tế và địa chỉ Việt Nam; thứ
  tự pattern được chọn để không làm hỏng số liệu nghiệp vụ (latency, version).
- **Cách kiểm chứng kết quả:** gửi 1 request có email + SĐT + CCCD + thẻ, đối chiếu log thật
  (`evidence/05-pii-redaction.png`); chạy `scripts/validate_logs.py` trên toàn bộ
  `data/logs.jsonl` → *Potential PII leaks detected: 0*; `tests/test_pii.py` kiểm từng pattern.

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:** key trong `.env` trỏ
  tới project `day13-k4-l3a-2A202602392`; workload chạy bằng script `scripts/load_test.py` và
  các request tay của tôi; mỗi trace có `metadata.correlation_id` khớp 1-1 với log của
  tôi, còn prompt `day13-chat` chỉ tồn tại trong project này. Screenshot cho thấy **86 root
  trace** với filter `isRootObservation: true`, đủ vượt yêu cầu ≥ 10 trace.
- **Cấu trúc root/retrieval/generation observations:**
  root observation tên **`lab-agent-run`** (`as_type=agent`, gắn `version=prompt.version` và
  `metadata` gồm `prompt_name/prompt_label/prompt_version/prompt_source/correlation_id`);
  tên **trace** là `day13-agent-request` (đặt qua `propagate_attributes(trace_name=...)`).
  Bên dưới là `retrieval` (`as_type=retriever`) → `llm-call` (`as_type=generation`, có
  `model`, `prompt`, `usage_details`, `cost_details`). Xem `evidence/07-trace-waterfall.png`.
- **Cách nối trace với log:** `app/main.py` truyền `request.state.correlation_id` xuống
  `LabAgent.run`, agent ghi nó vào `metadata` của trace; log ghi cùng ID ở
  `request_received`/`response_sent`. Tra `correlation_id` là ra đúng một trace.
- **Prompt name:** `day13-chat` (text prompt, giữ đúng 3 biến `feature`, `docs`, `message`).
- **Version/label baseline:** version 1, labels `production` + `baseline`
  (`evidence/09-prompt-versions.png`).
- **Version/label candidate:** version 2, label `candidate` — thay đổi nhỏ về format/độ dài:
  yêu cầu trả lời theo gạch đầu dòng, tối đa 5 gạch, kết thúc bằng dòng "Nguồn: ...".
- **Trace ID của mỗi version:** trace đã chụp trong `evidence/08-trace-metadata.png` có ID
  `6418f8df71bfb8540a1d23eeda16f40b` (0.15 s, $0.001953, 175 tokens, feature `billing`,
  user hash `7cae201043d4`). Ảnh đó **chưa** chụp riêng hai trace `baseline` và `candidate`;
  cần thêm bằng cách lọc theo `metadata.correlation_id` của hai request chạy cùng input ở
  bước 3 (`docs/PROMPT_VERSIONING.md`).
- **Cách promote và rollback `production`:** trên UI Langfuse, gỡ label `production` ở
  version 1 rồi gắn vào version 2 để promote; ngược lại làm ngược thứ tự để rollback.
  Vì `app/prompt_management.py` cache prompt 60s (`cache_ttl_seconds=60`) và `app/main.py`
  đọc biến môi trường lúc khởi động, mỗi lần đổi label phải **sửa `.env` rồi restart
  uvicorn** trước khi chạy request, nếu không sẽ nhận nhầm version cũ. Evidence
  promote/rollback: `evidence/09-prompt-versions.png`, `evidence/10-prompt-rollback.png`.

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:** `config/dashboard.yaml`, nguồn `data/logs.jsonl`, time range 60
  phút, refresh 30s, đúng 6 panel: `latency` (p50/p95/p99 + ttft_p95), `traffic`,
  `errors` (error_rate + count_by error_type + **tool_success_rate**), `cost`, `tokens`,
  `quality`. Số liệu runtime và ngưỡng ở `evidence/11-dashboard-overview.png`.
- **SLO và lý do chọn:** `fast_successful_requests`, cửa sổ 28 ngày, good event là
  `response_sent` với `latency_ms <= 3000`, target 99.5%. Ngưỡng 3000ms chọn vì nằm trên
  healthy tail (P50 153ms, TTFT P95 51ms) nhưng vẫn dưới mức người dùng chịu không nổi;
  cùng incident `rag_slow` đẩy latency lên ~2650ms/request và làm cạn error budget.
- **Cách tính error budget:** target 99.5% ⇒ error budget = 0.5%. Trên traffic thực tế của
  lab (76 request), 0.5% tương đương khoảng **21 request lỗi/ngày**; một incident kéo dài
  vài chục phút đã tiêu hết ngân sách trong 28 ngày, nên SLO này rất nhạy với sự cố
  retrieval diện rộng. Bốn guardrail bổ sung: `error_rate_pct_max = 2`,
  `daily_cost_usd_max = 2.5`, `quality_score_avg_min = 0.75`,
  `retrieval_success_rate_pct_min = 90`.
- **Ba alert và runbook tương ứng** (`config/alert_rules.yaml`, chi tiết `docs/alerts.md`):
  1. `user_visible_latency_burn` — critical, 5 phút, Slack `#llm-ops-oncall`;
     P95 `latency_ms` > 3000ms **và** burn rate > 2. Runbook: kiểm tra panel latency →
     loại trừ traffic spike → lấy `correlation_id` chậm nhất → mở trace so `retrieval`
     với `llm-call`; mitigation giảm top-k/timeout hoặc rollback prompt.
  2. `retrieval_degradation` — critical, 10 phút, Slack `#llm-ops-oncall`;
     `tool_name == "retrieval" && tool_success == false` > 5%. Runbook: xem `error_breakdown`
     → lọc `request_failed` → trace có span `retrieval` status ERROR; mitigation fail-open
     (trả lời không kèm tài liệu) thay vì trả 500.
  3. `daily_cost_runway` — warning, 30 phút, Slack `#llm-ops-cost`;
     tổng `cost_usd` > 2.5 USD/ngày hoặc `tokens_out` tăng > 3x. Runbook: panel cost/tokens
     → so `prompt_version` trước/sau → tìm retry loop; mitigation giới hạn `max_tokens`,
     rollback prompt ngắn hơn, cache câu hỏi trùng.
  Cả ba đều là **symptom-based** (theo triệu chứng người dùng/SLO), không trigger theo tên
  hàm nội bộ.

## 7. Điều tra challenge (practice scenario `rag_slow`)

- **Challenge ID:** chưa có (chưa nhận `config/challenge.json`). Dùng practice
  `rag_slow` để luyện đúng quy trình. Có **hai lần chạy**:
  - *Lần 1* (10 request, concurrency 5) dùng để lấy phân bố P95 → `evidence/12`.
  - *Lần 2* (đơn lẻ, `correlation_id` đặc biệt) dùng để mở được trace trên UI Langfuse
    → `evidence/13`, `evidence/14`.
- **Khoảng thời gian điều tra:** lần 1: 2026-09-29 10:19:08Z → 10:20:49Z (17:19–17:20 VN).
  lần 2: 12:10:15Z → 12:10:40Z (19:10 VN).
- **Triệu chứng từ metrics (lần 1):** `GET /metrics` cho thấy P50 không đổi (152→154ms) nhưng
  `latency_p95` 2213→2655ms, `latency_p99` 2657ms, trong khi `ttft_p95` giữ nguyên 51ms và
  `error_breakdown` vẫn rỗng. Error rate 0%, retrieval success vẫn 100%.
- **Log line và correlation ID liên quan (lần 2):** `req-inc14warm`, `request_received` lúc
  12:10:40.114Z và `response_sent` lúc 12:10:40.360Z với `latency_ms = 2653`,
  `ttft_ms = 50`, `tool_name = "retrieval"`, `tool_success = true`. Đối chiếu cùng đợt:
  `req-inc14trace` 3619ms (cache miss) và `req-ok14trace` 151ms (đã tắt incident).
  Xem `evidence/13-incident-log.png`.
- **Trace và span gây ảnh hưởng:** trace `req-inc14warm`, xem `evidence/14-incident-trace.png`.
  Số liệu đọc được trên tab **Timeline** của Langfuse:

  | Span | Loại | Thời gian | Chiếm % |
  |---|---|---|---|
  | `lab-agent-run` (root) | agent | 2.65 s | 100% |
  | `retrieval` | retriever | **2.50 s** | **94%** |
  | `llm-call` | generation | 153 ms | 6% |

  Span gây ảnh hưởng là **`retrieval`** — 2.50s trong tổng 2.65s. Tổng khớp đúng
  `latency_ms = 2653` trong log, và `llm-call` 153ms khớp `ttft_ms` 50ms + thời gian sinh
  token. Đây là bằng chứng root cause trực tiếp từ trace.
- **Root cause:** `app/mock_rag.py` ngủ 2.5s ở tầng vector store cho mọi request khi
  incident `rag_slow` được bật. Đây là bệnh của hạ tầng truy xúc dữ liệu, không phải của
  mô hình: TTFT không đổi và request vẫn trả lời đúng, chỉ chậm.
- **Fix action:** `POST /incidents/rag_slow/disable`. Xác nhận bằng request `req-ok14trace`
  ngay sau đó: latency 2653ms → 151ms, TTFT vẫn 50ms.
- **Bài học kỹ thuật phát sinh:** correlation ID sinh tự động (`req-<8 hex>`) rất khó tra cứu
  thủ công trên UI Langfuse. `app/middleware.py` giữ nguyên `x-request-id` nếu khớp charset
  `[A-Za-z0-9._-]{1,64}`, nên khi cần mở được đúng một trace tôi đặt ID có chủ đích
  (`req-inc14warm`, `req-ok14trace`). Với incident thật, nên gắn thêm `scenario` vào ID hoặc
  tag để lọc hàng loạt thay vì tìm từng ID.

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:** dùng **P50 + P95 + TTFT P95 cùng lúc**
  thay vì chỉ nhìn P95. Khi `rag_slow` xảy ra, P50 và TTFT P95 gần như bất biến còn P95 tăng
  gấp 10. Sự bất biến của TTFT chính là bằng chứng định vị vấn đề nằm trước bước sinh token.
  Nếu chỉ có P95 thì chỉ biết "chậm", không biết "chậm ở đâu".
- **Một lỗi/blocker đã gặp:** `GET /api/public/traces` trả
  `410 LEGACY_API_UNAVAILABLE_FOR_NEW_ORGANIZATION` (tổ chức tạo sau 16/09/2026), nên
  không lấy được trace ID bằng script; phải thao tác tay trên UI Langfuse. Một điểm nhỏ
  khác: `scripts/load_test.py` hardcode `BASE_URL = 127.0.0.1:8000`, nên khi chạy song song
  hai bản (để đo baseline) mọi traffic vô tình đổ vào server đã sửa — phải gửi request
  trực tiếp thay vì dùng load_test cho bản baseline.
- **Cách tìm nguyên nhân và xử lý:** theo đúng thứ tự slide: metrics cho thấy khoảng thời
  gian (12:10:40Z) và rằng lỗi nằm ở latency chứ không ở error → logs cho ra
  `correlation_id` = `req-inc14warm` → trace của `correlation_id` đó cho thấy span
  `retrieval` chiếm 2.50s / 2.65s (94%) → kết luận tầng truy xức chậm, tắt incident và
  xác nhận latency về 151ms.
- **Cách hiểu luồng Metrics → Logs → Traces:** metrics trả lời "lỗi gì và lúc nào" nhưng
  không chỉ ra request nào; log trả lời "request nào" qua `correlation_id` nhưng không có
  cấu trúc bên trong; trace trả lời "bước nào" bằng cây span. `correlation_id` là khớp nối
  duy nhất giữa ba tầng, và vì log được scrub PII + hash user id nên khớp nối đó an toàn.
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:** prompt
  version cho phép đổi hành vi hệ thống chỉ bằng cách đổi label mà không deploy code, và
  rollback là thao tác một click thay vì một lần deploy khẩn cấp giữa sự cố. Token/cost phải
  được ghi ở mọi generation để phát hiện prompt mới làm câu trả lời dài ra (ở đây
  `cost_spike` nhân `tokens_out` 4x). SLO biến "cảm giác chậm" thành một con số có thể
  tranh luận và có error budget đi kèm.
- **Điều quan trọng nhất đã học:** phải giữ `correlation_id` xuyên suốt từ HTTP header →
  structured log → trace metadata ngay từ đầu. Khi thiếu nó, ba tầng quan sát không nối
  được với nhau và mọi điều tra phải đoán theo thời gian.
- **Hạn chế hoặc phần chưa hoàn thành:**
  - Chưa có hệ thống gửi Slack thật; `config/alert_rules.yaml` mới ở dạng contract mà
    validator đọc, chưa có connector gửi tin.

## 9. Checklist trước khi nộp

- [x] Kết quả và evidence thu thập trên cây làm việc hiện tại.
- [x] Chụp ảnh thật cho `14` và 2 trace `baseline` / `candidate` trên UI Langfuse.
- [x] Điền Họ tên/MSSV/Repository URL/Commit SHA cuối.
- [x] Tất cả đường dẫn evidence dùng đường dẫn tương đối và mở được.
- [x] Incident evidence nối đúng metric → log → trace bằng `req-inc14warm`.
- [x] Trace/prompt evidence thuộc project Langfuse cá nhân, không ảnh nào lộ key/secret.
- [x] Repository chạy lại được theo README (`python -m pytest -q`, `uvicorn ... --env-file .env`).
- [x] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác.
- [x] URL repo và commit SHA cuối nộp trên LMS/Codelabs.

## 10. Lệnh đã chạy để tái lập

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --port 8000 --env-file .env      # terminal 1
python scripts\load_test.py --concurrency 3           # terminal 2
python scripts\inject_incident.py --scenario rag_slow
python scripts\load_test.py --concurrency 5
python scripts\inject_incident.py --scenario rag_slow --disable
python scripts\validate_logs.py
python scripts\validate_dashboard.py
python -m pytest -q
```

Đổi label prompt: sửa `LANGFUSE_PROMPT_LABEL` trong `.env` → **restart uvicorn** →
gửi request (prompt được cache 60s).
