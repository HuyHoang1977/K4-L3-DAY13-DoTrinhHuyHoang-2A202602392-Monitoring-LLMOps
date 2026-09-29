# Alert và runbook

Cả ba alert đều phát ra từ **triệu chứng người dùng / SLO**, không trigger trực tiếp từ tên
hàm hay tên biến nội bộ. Nguồn sự kiện là structured log `data/logs.jsonl` (`event`,
`latency_ms`, `ttft_ms`, `cost_usd`, `tokens_in`, `tokens_out`, `tool_name`, `tool_success`)
và trace tương ứng trên Langfuse. Kênh thông báo: Slack.

Quy ước chung:

- `correlation_id` (`req-<8 hex>`) là khóa nối giữa log, response header `x-request-id` và
  metadata của trace Langfuse.
- Mọi mốc thời gian trong runbook lấy từ trường `ts` của log (UTC) hoặc timestamp của trace.

## Alert 1

- Tên: `user_visible_latency_burn`
- Severity: critical
- Duration: 5m
- Kênh thông báo: Slack `#llm-ops-oncall`
- SLI/SLO liên quan: `fast_successful_requests` (target 99.5%, window 28d)
- Điều kiện và thời gian duy trì: burn rate 28d > 2 **và** P95 `latency_ms` của
  `event == "response_sent"` > 3000ms trong 5 phút liên tục.
- Ảnh hưởng tới người dùng: request `/chat` phải chờ > 3s, người dùng thấy app như bị treo
  dù LLM vẫn sinh câu trả lời. Trong practice `rag_slow`, latency nhảy từ ~153ms lên ~2650ms.
- Ba bước kiểm tra đầu tiên:
  1. Dashboard panel `latency`: xác nhận khoảng thời gian bắt đầu lỗi và P95 có vượt 3000 không.
  2. Panel `traffic` + `errors`: loại trừ traffic spike làm đầy hàng đợi.
  3. Lọc `data/logs.jsonl` theo khoảng thời gian đó, lấy `correlation_id` của một
     `response_sent` chậm nhất.
- Mitigation tạm thời:
  1. Mở trace của `correlation_id` đó, so sánh span `retrieval` với `llm-call`.
  2. Nếu span `retrieval` chiếm gần hết latency: giảm `top-k`/timeout của retriever hoặc
     bật cache retrieval; nếu `llm-call` chiếm phần lớn: rollback prompt về version gần nhất
     đã được duyệt (xem [PROMPT_VERSIONING.md](PROMPT_VERSIONING.md)).
  3. Nếu không xác định được, hạ tải: tạm dừng feature đang lỗi ở API gateway.
- Owner: Duty engineer k4-l3a (học viên trực)

## Alert 2

- Tên: `retrieval_degradation`
- Severity: critical
- Duration: 10m
- Kênh thông báo: Slack `#llm-ops-oncall`
- SLI/SLO liên quan: `fast_successful_requests` + guardrail `retrieval_success_rate_pct_min = 90`
- Điều kiện và thời gian duy trì: tỉ lệ `tool_name == "retrieval" && tool_success == false`
  trên 5% trong 10 phút.
- Ảnh hưởng tới người dùng: câu trả lời thiếu ngữ cảnh tài liệu hoặc request lỗi 500; ví dụ
  incident `tool_fail` làm retrieval raise `RuntimeError("Vector store timeout")`.
- Ba bước kiểm tra đầu tiên:
  1. Panel `errors` xem `error_breakdown` có `RuntimeError` tăng vọt không.
  2. Lọc log `event == "request_failed"` và gom `error_type`.
  3. Mở trace của `correlation_id` lỗi, kiểm tra span `retrieval` có status `ERROR` và
     exception type nào.
- Mitigation tạm thời:
  1. Fail-open: trả lời bằng prompt không kèm tài liệu thay vì trả 500 cho người dùng
     (giữ `quality_score` để phát hiện chất lượng giảm).
  2. Giảm timeout của vector store và bật retry có backoff giới hạn.
  3. Kiểm tra index/collection có bị rebuild giữa chừng không; nếu có, dừng rebuild.
- Owner: Duty engineer k4-l3a (học viên trực)

## Alert 3

- Tên: `daily_cost_runway`
- Severity: warning
- Kênh thông báo: Slack `#llm-ops-cost`
- Duration: 30m
- SLI/SLO liên quan: guardrail `daily_cost_usd_max = 2.5`
- Điều kiện và thời gian duy trì: tổng `cost_usd` trong ngày > 2.5 USD **hoặc** trung bình
  `tokens_out` tăng > 3x so với 7 ngày trước, giữ liên tục 30 phút.
- Ảnh hưởng tới người dùng: hóa đơn LLM vượt ngân sách dù chất lượng chưa tăng; ở mức lab,
  `tokens_out` tăng 4x khiến một ngày có nguy cơ vượt runway tháng.
- Ba bước kiểm tra đầu tiên:
  1. Dashboard panel `cost` và panel `tokens` để xem `tokens_out` tăng ở feature nào.
  2. So sánh prompt version đang chạy (`prompt_version` trong trace) với version trước đó.
  3. Kiểm tra có retry loop hoặc request lặp lại không (`correlation_id` trùng payload).
- Mitigation tạm thời:
  1. Giới hạn `max_tokens` cho generation span.
  2. Rollback `production` về prompt version ngắn hơn nếu thay đổi prompt làm lệch.
  3. Bật cache cho câu hỏi trùng (`session_id` + hash message).
- Owner: Duty engineer k4-l3a (học viên trực)

## Liên kết cấu hình

Nguồn máy đọc được nằm ở [config/alert_rules.yaml](../config/alert_rules.yaml); SLO và error
budget nằm ở [config/slo.yaml](../config/slo.yaml).
