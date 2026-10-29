# Danh mục ứng dụng và đường tìm kiếm

DeskMorph dùng GIO AppInfo/ DesktopAppInfo cho cả discovery và launch theo desktop ID. Không tự tách Exec thành shell command. XDG_DATA_HOME/applications có ưu tiên cao nhất, gồm Hidden=true tombstone. GIO xử lý ID từ đường con, desktop environment, locale và symlink deployment.

Ngay đầu run_app, trước GTK/GIO hay worker, catalogue_paths::prepare giữ thứ tự thư mục tuyệt đối trong XDG_DATA_DIRS, loại trùng và nối các export hiện có:

1. $FLATPAK_USER_DIR/exports/share nếu biến là đường tuyệt đối; nếu không, $XDG_DATA_HOME/flatpak/exports/share. XDG_DATA_HOME thiếu hoặc tương đối thì dùng $HOME/.local/share.
2. /var/lib/flatpak/exports/share.
3. /var/lib/snapd/desktop.

Nối cả root chưa có thư mục applications: GIO theo dõi ancestor để phát hiện lần cài đầu tiên trong cùng process. XDG_DATA_DIRS thiếu/rỗng/không có đường tuyệt đối dùng /usr/local/share:/usr/share. Các đường được cấu hình rõ đứng trước fallback. Thay đổi chỉ nằm trong process DeskMorph và môi trường child; không ghi cấu hình phiên desktop. Không thay biến toàn cục trong command hay sau khi GLib cache đường. System Flatpak installation tùy chỉnh được hỗ trợ khi có trong XDG_DATA_DIRS, chưa tự đọc installation config.

Kiểm thử Rust chạy GIO trong subprocess với XDG riêng; fake export layout bao phủ ba root, symlink, priority/Hidden/ID trùng và launch marker từ desktop ID. Ca native:

```sh
/usr/bin/python3 tests/desktop_smoke.py --exports-smoke --launcher-smoke
```

Chỉ dùng isolated test profile. Harness bỏ export khỏi startup XDG_DATA_DIRS, tìm tên duy nhất bằng native input rồi launch qua UI, kiểm marker, xóa fixture và khôi phục config/process bình thường. Cần desktop GNOME X11 mở khóa. [Bản ghi](benchmarks/catalogue-exports-2026-10-29.json) và [tiến độ](PROGRESS.md) ghi phạm vi: đây là export-layout fixture, chưa phải chạy gói Flatpak/Snap đã cài.


## Refresh trong cùng process

Catalogue backend cache 30 giây; AppInfoMonitor và GTK theme change đánh dấu dirty, phát deskmorph:apps-changed cho consumer. Refresh chủ động bỏ qua cache thời gian. Monitor giữ reference trên GTK main context và disconnect khi thay watch/thoát; hook có một request đang chạy cùng một pending reload cho mỗi effect, bỏ completion sau dispose và dọn listener đăng ký muộn.

```sh
/usr/bin/python3 tests/desktop_smoke.py --catalogue-refresh-smoke --exports-smoke
```

Ca refresh tạo FLATPAK_USER_DIR riêng còn chưa tồn tại khi app khởi động. Giữ launcher mở với query cố định, rồi tạo export/entry, atomic rename, Hidden=true, khôi phục và gỡ. Kiểm kết quả UI thay đổi mà không refresh/restart; thêm refresh chủ động và thay entry khi consumer đã đóng rồi mở lại. Sau cùng dọn đúng thư mục mkdtemp sở hữu và khôi phục config/process thường. [Bản ghi](benchmarks/catalogue-refresh-2026-10-29.json) lưu thời gian vòng đợi quan sát; đây không phải benchmark độ trễ đầy đủ từ filesystem đến UI. Kiểm chứng native hiện trên GNOME X11 tham chiếu.
