# Danh mục ứng dụng và đường tìm kiếm

DeskMorph dùng GIO AppInfo/ DesktopAppInfo cho cả discovery và launch theo desktop ID. Không tự tách Exec thành shell command. XDG_DATA_HOME/applications có ưu tiên cao nhất, gồm Hidden=true tombstone. GIO xử lý ID từ đường con, desktop environment, locale và symlink deployment.

Ngay đầu run_app, trước GTK/GIO hay worker, catalogue_paths::prepare giữ thứ tự thư mục tuyệt đối trong XDG_DATA_DIRS, loại trùng và nối các export hiện có:

1. $FLATPAK_USER_DIR/exports/share nếu biến là đường tuyệt đối; nếu không, $XDG_DATA_HOME/flatpak/exports/share. XDG_DATA_HOME thiếu hoặc tương đối thì dùng $HOME/.local/share.
2. /var/lib/flatpak/exports/share.
3. /var/lib/snapd/desktop.

Chỉ nối root có thư mục applications. XDG_DATA_DIRS thiếu/rỗng/không có đường tuyệt đối dùng /usr/local/share:/usr/share. Các đường được cấu hình rõ đứng trước fallback. Thay đổi chỉ nằm trong process DeskMorph và môi trường child; không ghi cấu hình phiên desktop. Không thay biến toàn cục trong command hay sau khi GLib cache đường. System Flatpak installation tùy chỉnh được hỗ trợ khi có trong XDG_DATA_DIRS, chưa tự đọc installation config.

Kiểm thử Rust chạy GIO trong subprocess với XDG riêng; fake export layout bao phủ ba root, symlink, priority/Hidden/ID trùng và launch marker từ desktop ID. Ca native:

```sh
/usr/bin/python3 tests/desktop_smoke.py --exports-smoke --launcher-smoke
```

Chỉ dùng isolated test profile. Harness bỏ export khỏi startup XDG_DATA_DIRS, tìm tên duy nhất bằng native input rồi launch qua UI, kiểm marker, xóa fixture và khôi phục config/process bình thường. Cần desktop GNOME X11 mở khóa. [Bản ghi](benchmarks/catalogue-exports-2026-10-29.json) và [tiến độ](PROGRESS.md) ghi phạm vi: đây là export-layout fixture, chưa phải chạy gói Flatpak/Snap đã cài.
