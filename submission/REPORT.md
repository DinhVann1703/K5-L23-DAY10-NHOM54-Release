# Báo cáo nhóm 54

## 1. Số liệu luyện tập
- **Thông tin lô luyện tập:** Seed `54007`, Release ID `lab250_e815148e1805`, tổng số ảnh `250`, số lỗi luật phát hiện `11` (tổng lỗi chốt trong `errors.json`: `17` lỗi trên `16` ảnh sau khi gộp `6` lỗi gán nhãn `confirmed`).
- **F1 theo seed (rule / cross_check / overall):** `rule F1 ≈ 1.0`, `cross_check F1 ≈ 0.2` (trên kết quả tự đo), `overall F1 ≈ 0.7` (17/17 PASS trên `check_handover.py`).
- **Số ứng viên trên lô sạch (`--no-faults`):** Seed `5`, `50` ảnh, `0` lỗi luật, tổng cộng `110` ứng viên semantic trên `30` ảnh (`instance_merge`: `100`, `missing_box`: `9`, `class_swap_or_category_swap`: `1`).
- **Hàng đợi trên seed luyện tập (`r54007`):** `396` ứng viên semantic trên `125` ảnh (`instance_merge`: `338`, `missing_box`: `44`, `bbox_drift`: `4`, `class_swap_or_category_swap`: `10`). Nhóm rà soát `14` trường hợp (`6 confirmed`, `8 rejected`), kết hợp công cụ trực quan hóa (`tools/viz_candidates.py`).
- **Ngưỡng đã chọn và cách chọn (không dùng `_private`):** Đối chiếu pixel giữa detection box và panoptic segment kết hợp đối chiếu lớp (`classes.txt` ↔ `categories`); dùng ngưỡng `coverage = 0.15` cho `instance_merge` và có khảo sát thêm dải coverage `0.15` đến `0.60` với segment tối thiểu `1024` pixel. Lô sạch dùng để đo nhiễu tự nhiên, vẫn cần kiểm tra hình ảnh thực tế trước khi đưa vào `errors.json`.

## 2. Vì sao báo hết ứng viên làm F1 giảm?
Ứng viên do validator sinh ra chỉ là dấu hiệu nghi vấn, không phải lỗi đã xác nhận. Ngay trên lô sạch (`seed 5`, `--no-faults`) vẫn có `110` ứng viên trên `30` ảnh do nhiễu tự nhiên của COCO (vật thể bị che khuất, chồng lấn hoặc khác biệt cách biểu diễn giữa detection và panoptic), và trên `r54007` chỉ có `6/14` mục review được `confirmed`. Nếu đưa toàn bộ ứng viên thô vào `errors.json`, số dương tính giả (**FP**) tăng mạnh làm **Precision** giảm và kéo **F1** đi xuống.

## 3. Quyết định và lineage
- **QC v1 (`lab250_e815148e1805`):** `16/250` ảnh lỗi (**6.4%**, vượt ngưỡng **2%** theo quy định Day 7; riêng lỗi luật đã là `11/250 = 4.4%`) → quyết định **`HOLD`**.
- **Ảnh hưởng training run & lý do:** Chạy `lineage.py impact` trả về **`R-021: affected=True action=review_or_retrain`**. Tạo release `v2` để làm sạch dữ liệu không tự động cập nhật trọng số của mô hình đã train trên `v1`, nên run phụ thuộc vào release đang `HOLD` cần được xem xét hoặc huấn luyện lại.

## 4. Hash chứng minh gì, không chứng minh gì?
- **SHA-256 chứng minh:** tính toàn vẹn byte-level của file tại thời điểm đọc ở chế độ nhị phân (`rb`) — xác nhận nội dung file không bị đổi hoặc hỏng so với `manifest.csv` / `.sha256` (nếu báo `wrong_hash`, mở ảnh kiểm tra trước: ảnh còn nguyên thì sửa manifest, ảnh hỏng thì chuyển sang `rework_queue.csv`).
- **SHA-256 không chứng minh:** tính đúng ngữ nghĩa nhãn (`bbox_drift`, `class_swap`/`category_swap`, `instance_merge`), tính đúng split/guideline (`scene_leak`, `guideline_mismatch`), hay việc ảnh không có thông tin nhạy cảm (như khuôn mặt rõ).

## 5. Truy vết
- **Tiêu chí tầng a/b:** `tier_a` gồm các ảnh thuộc cảnh team AI báo lỗi, nằm ở job dùng guideline cũ và có ít nhất một box detection thuộc lớp bị đổi quy tắc; `tier_b` gồm các ảnh khác cùng điều kiện (job guideline cũ, có lớp bị đổi quy tắc) chưa được báo; `notify` gồm mã `annotator` và `reviewer` của các job liên quan.
- **Vì sao lấy guideline theo job:** guideline gắn trên từng bản ghi ảnh có thể sai lệch (`guideline_mismatch`), nên lấy theo `job_id` trong `jobs.csv` sẽ đảm bảo đúng nguồn cấu hình của job.

## 6. Bug hoặc điểm chưa rõ trong lab (nếu có)
Luồng bàn giao chạy ổn định (`check_handover.py` đạt 17 PASS / 0 FAIL); cần chú ý thống nhất tên khóa khi đọc JSON/CSV trong script tự viết và chạy lại `pack_release.py` mỗi khi cập nhật file trong `handover/*_v2`.
