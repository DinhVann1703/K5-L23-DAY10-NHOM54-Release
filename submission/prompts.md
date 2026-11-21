# Dùng AI

| # | Ai dùng | Công cụ | Prompt (tóm tắt) | AI sai ở đâu | Nhóm kiểm lại thế nào |
|---|---|---|---|---|---|
| 1 | Nguyễn Hán Trường Giang | AI Assistant | Thiết kế và kiểm thử logic 9 luật kiểm tra delivery (`validate.py`) theo chuẩn thư viện Python | Gợi ý ngưỡng overlap quá chặt ban đầu dễ gây nhầm với cặp box chồng tự nhiên của COCO | Chạy kiểm thử trên nhiều seed bằng `inject_release.py` và lô sạch `--no-faults`, đối chiếu `score_findings.py` |
| 2 | Cù Việt Đức | AI Assistant | Xây dựng thuật toán đối chiếu detection ↔ panoptic, sinh `candidates.json` và vẽ ảnh đối chiếu (`tools/viz_candidates.py`) | Đề xuất dựa đơn thuần vào IoU bbox ban đầu nên chưa bắt rõ độ lệch pixel mask và `instance_merge` | Bổ sung phân tích pixel mask, trực quan hóa ảnh bằng `tools/viz_candidates.py` và ghi `review_log.csv` (`confirmed` / `rejected`) |
| 3 | Nguyễn Văn Hoà | AI Assistant | Xử lý quy trình bàn giao `v2` (`rework_queue.csv`, `manifest.csv`, `label_summary.csv`, `truyvet.csv`, `README.txt`) và `lineage.py` | Nhắc nhầm định dạng dòng `QC v1` ở bản nháp đầu khiến `check_handover.py` báo `H13` | Chuẩn hóa định dạng `QC v1 16/250 = 6.4% ⇒ Hold` và chạy `check_handover.py` xác nhận 17 PASS, 0 FAIL |
| 4 | Bùi Lê Đình Văn | AI Assistant | Xây dựng logic truy vết `trace.json` (`tier_a`, `tier_b`, `notify`), rà soát `security.md`, báo cáo và đóng gói `submission/` | Dễ nhầm lẫn lấy guideline theo từng ảnh thay vì lấy theo `job_id` từ `jobs.csv` | Đối chiếu trực tiếp `jobs.csv`, kiểm tra `score_findings.py`, chạy `export_submission.py` và rà soát `git status` |
