# Báo cáo nhóm <<XX>>

#1. Số liệu luyện tập

Seed luyện tập: 54007.

Release ID: lab250_e815148e1805.

Tổng số ảnh: 250.

F1 theo seed:

Rule F1: 1.0.

Cross-check F1: Chưa có kết quả cuối cùng vì chưa hoàn thành review thủ công.

Overall F1 sơ bộ: 0.7.

Kết quả kiểm thử lô sạch

Seed: 5.

Số ảnh: 50.

Số lỗi luật: 0.

Tổng ứng viên semantic: 110.

Số ảnh có ứng viên: 30.

Phân loại:

instance_merge: 100.

missing_box: 9.

class_swap_or_category_swap: 1.

Kết quả kiểm thử lô luyện tập

Tổng số ảnh: 250.

Số lỗi luật phát hiện: 11.

Rule F1: 1.0.

Tổng ứng viên semantic: 396.

Số ảnh có ứng viên: 125.

Phân loại:

instance_merge: 338.

missing_box: 44.

bbox_drift: 4.

class_swap_or_category_swap: 10.

Ngưỡng và phương pháp lựa chọn

Validator sử dụng đối chiếu pixel giữa detection box và panoptic segment. Ngưỡng coverage 0.15 hiện được sử dụng để sàng lọc ứng viên instance_merge.

Đã thử phân tích thêm các ngưỡng coverage từ 0.15 đến 0.60 với segment có diện tích tối thiểu 1024 pixel.

Kết quả cho thấy vẫn tồn tại nhiều ứng viên tự nhiên ngay cả khi tăng ngưỡng. Vì vậy, không tự động coi ứng viên là lỗi. Tất cả ứng viên semantic cần được kiểm tra hình ảnh và xác nhận trước khi đưa vào errors.json.

Lô sạch được dùng để đo nhiễu tự nhiên, không dùng để xác định trực tiếp nhãn đúng của lô luyện tập vì hai lô sử dụng các ảnh khác nhau.

#2. Vì sao báo hết ứng viên làm F1 giảm?

Ứng viên do validator tạo ra chỉ là dấu hiệu nghi vấn, không phải lỗi đã được xác nhận.

Kết quả lô sạch có 110 ứng viên trên 30 ảnh dù không có lỗi được chủ động gài. Điều này cho thấy hai nguồn annotation COCO có thể bất đồng tự nhiên do vật thể bị che khuất, nhiều đối tượng chồng lấn hoặc khác biệt trong cách biểu diễn instance.

Nếu đưa toàn bộ ứng viên vào errors.json, các ứng viên không phải lỗi thật sẽ trở thành False Positive. Precision giảm và kéo F1 xuống.

Vì vậy, chỉ những lỗi semantic được mở ảnh kiểm tra và xác nhận mới được đưa vào danh sách lỗi cuối cùng.

#3. Quyết định và lineage

Kiểm soát chất lượng v1

Số lỗi luật đã phát hiện: 11.

Tổng số ảnh: 250.

Tỷ lệ lỗi tối thiểu: 11/250 = 4,4%.

Ngưỡng cho phép theo quy định: 2%.

Vì tỷ lệ lỗi vượt quá 2%, quyết định đối với release v1 là HOLD.

Release ID: lab250_e815148e1805.

Ảnh hưởng đến training run

Training run sử dụng dữ liệu v1 phải được xem xét hoặc huấn luyện lại nếu lineage xác nhận run đó phụ thuộc vào release đang HOLD.

Việc sửa dataset và tạo release v2 không tự động sửa các trọng số của mô hình đã được huấn luyện từ v1.

Cần sử dụng lineage.py impact để xác nhận training run bị ảnh hưởng.

## 4. Hash chứng minh gì, không chứng minh gì?
<<>>

## 5. Truy vết
<<Tiêu chí tầng a/b, vì sao lấy guideline theo job.>>

## 6. Bug hoặc điểm chưa rõ trong lab (nếu có)
<<>>
