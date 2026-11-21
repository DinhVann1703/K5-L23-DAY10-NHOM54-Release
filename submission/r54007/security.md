## Kiểm soát dữ liệu và quyền riêng tư
Toàn bộ dữ liệu bàn giao của lô lab250_e815148e1805 được xử lý cục bộ trong thư mục runs/r54007, tách biệt khỏi _private và rà soát kỹ trước khi xuất bản.

## Kiểm soát rủi ro khuôn mặt
Với các ảnh có người và khuôn mặt trong lô như 000000000139, kết luận áp dụng là Hold để kiểm soát quyền riêng tư, ẩn danh và lọc kỹ trước khi sử dụng.

## An toàn đường dẫn và đóng gói
Mọi tệp xuất bản đều được kiểm tra mã băm SHA-256 và rà soát để không chứa đường dẫn nội bộ máy cá nhân hay thông tin nhạy cảm.
