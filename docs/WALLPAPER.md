# Hình nền trên GNOME

Adapter sản phẩm hiện chỉ bật trên GNOME khi schema GSettings phù hợp có sẵn. Chưa xác minh adapter KDE/COSMIC hoặc hình nền hiển thị trong phiên Wayland. Ma trận môi trường nằm trong [CAPABILITIES.md](CAPABILITIES.md).

Lệnh apply kiểm tra đường dẫn local tuyệt đối, canonical path, giới hạn ảnh và decode trước khi ghi. Transaction GSettings kiểm tra quyền ghi, cập nhật cả `picture-uri` và `picture-uri-dark` nếu có, apply/sync rồi đọc lại giá trị. UI chỉ báo thành công sau kết quả backend; lỗi giữ thao tác để thử lại. Đây là xác nhận settings backend, không bảo đảm compositor đã vẽ từng pixel trên desktop.

Studio đọc lại hình nền mỗi ba giây khi đang hiển thị. Thay đổi bằng ứng dụng khác được phản ánh qua cùng đường đọc GSettings; ẩn Studio dừng polling UI, không dừng lịch backend.

Scheduler khởi động một worker trong vòng đời ứng dụng. Thay đổi bật/tắt, chu kỳ hoặc thư mục đánh thức worker và đổi epoch. Trước khi ghi, worker kiểm tra lại epoch/cấu hình trên GTK main thread. Deadline dùng Unix wall clock; khi quá hạn chỉ thử một lần, sau đó tính hạn mới từ lúc hoàn tất, không chạy bù mọi chu kỳ. Khi đồng hồ lùi, hạn chạy được đặt lại. Mỗi lượt quét lại thư mục; ảnh bị xóa không được giữ làm danh sách ứng viên cũ. Lượt lỗi giữ nguyên hình nền, hiển thị lỗi và tiếp tục thử ở hạn kế tiếp.

## Kiểm thử native có chủ đích

Chạy trong GNOME/X11 đã mở khóa với instance có `DESKMORPH_CONFIG_HOME=/tmp/deskmorph-desktop-test/config`:

```sh
/usr/bin/python3 tests/desktop_smoke.py --scheduler-recovery-smoke
```

Ca này dùng hai PNG riêng, kiểm tra cả hai khóa GNOME, phản ánh hai lần thay đổi từ bên ngoài, deadline một phút khi Studio đóng và mở lại cùng instance. Sau đó tạm dừng riêng PID ứng dụng test bằng SIGSTOP 125 giây, SIGCONT, kiểm tra thay đổi khi quá hạn và không đổi tiếp trong mười giây. Xóa hai PNG để tạo lỗi ở deadline kế tiếp, khôi phục ảnh để xác minh tự phục hồi mà không bật/tắt lại. Có watchdog SIGCONT riêng, cùng finally khôi phục ảnh, tắt lịch, thư viện/cấu hình và hai URI hình nền ban đầu.

SIGSTOP không phải system suspend. Ca này xác minh worker tiếp tục xử lý hạn quá hạn sau khi tiến trình ngừng chạy; chưa xác minh login/session/compositor hoặc clock hoạt động qua sleep thật. Kiểm thử sleep thật và thay đổi phần cứng vẫn là cổng còn mở, không được suy ra từ ca này.
