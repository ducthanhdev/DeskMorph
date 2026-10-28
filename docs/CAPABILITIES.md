# Khả năng desktop và phạm vi đã kiểm thử

Ma trận ban đầu cho G0.5/G2.1. Đây là bản development; cổng phát hành vẫn nằm trong [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md). Bằng chứng chi tiết và những ca còn thiếu nằm trong [PROGRESS.md](PROGRESS.md).

| Môi trường | Liệt kê / chuyển / yêu cầu đóng cửa sổ native | Dock / popup | Hình nền | Workspace | Global shortcut |
| --- | --- | --- | --- | --- | --- |
| Pop!_OS 24.04, GNOME 46.0, X11, x86_64 | Backend X11; GNOME công bố `_NET_CLIENT_LIST`, `_NET_ACTIVE_WINDOW`, `_NET_CLOSE_WINDOW`; đã qua native launcher/close-confirmation và force-close fixture có PID giả, sentinel còn sống | Đã qua focus/Escape/outside-click, auto-hide top/bottom và stress ba vòng; overflow/mixed DPI/hotplug chưa hoàn tất | Adapter GNOME GSettings; áp dụng/shuffle/lịch một phút đã kiểm thử | Chưa triển khai | XCB tùy chọn; xung đột/retry/đổi/tắt/focus/exit-restart đã qua |
| X11 trên KDE, COSMIC hoặc desktop khác | Adapter dùng EWMH, chỉ bật capability API được phát hiện; chưa kiểm thử môi trường này | Chưa kiểm thử | Không bật adapter chưa xác minh | Chưa triển khai | Có code XCB, chưa kiểm thử desktop này |
| GNOME Wayland | Chưa hỗ trợ cửa sổ Wayland native | Chưa có prototype đạt yêu cầu placement/auto-hide | Adapter GNOME có code, chưa kiểm thử trong phiên Wayland | Chưa triển khai | Portal chưa thử trên phiên Wayland |
| COSMIC/KDE Wayland và compositor khác | Chưa có adapter được xác minh | Chưa kiểm thử | Chưa có adapter được xác minh | Chưa triển khai | Portal chưa thử trên compositor mục tiêu |

Có `DISPLAY`, XWayland hoặc file XML protocol trên đĩa không chứng minh ứng dụng có quyền quản lý cửa sổ Wayland native. Window backend và outside-click watcher X11 chỉ chạy khi `XDG_SESSION_TYPE=x11`. COSMIC Files cài trên máy tham chiếu là ứng dụng quản lý tệp; phiên desktop vẫn là GNOME.

## Phát hiện khi chạy

`get_platform_info` trả session/desktop thực tế, `windows.enumerate`, `windows.activate`, `windows.close`, `forceQuit`, `workspaces`, `wallpaper`, monitor topology và lý do thiếu hỗ trợ. `windowManagement` giữ ý nghĩa khả năng liệt kê để Dock tiếp tục hiển thị app đã ghim khi tính năng cửa sổ không khả dụng.

- Liệt kê cần gọi được `xprop` thành công và đọc `_NET_CLIENT_LIST` có kiểu WINDOW, kể cả danh sách rỗng hợp lệ. Thiếu property, sai kiểu/định dạng hoặc lỗi lệnh không được trả thành danh sách rỗng thành công.
- Chuyển/đóng cần window manager công bố chính xác atom EWMH tương ứng. UI tắt thao tác thiếu hỗ trợ; command kiểm tra lại trước gửi request. Command thành công nghĩa là đã gửi yêu cầu; window manager/ứng dụng vẫn quyết định chuyển focus hoặc hỏi xác nhận đóng.
- Force-close còn cần `xkill`; luôn yêu cầu xác nhận và không thay thế đóng bình thường. Hồi quy native của thay đổi force-close mới chưa hoàn tất.
- Workspace hiện luôn false. Hình nền chỉ bật adapter GNOME đã có code; desktop khác có lý do unsupported. CPU/RAM, UPower, NetworkManager, audio và MPRIS có trạng thái thiếu công cụ/service riêng.

## Bằng chứng hiện có

- `xprop -root _NET_SUPPORTED _NET_CLIENT_LIST` trên máy tham chiếu: ba API cửa sổ nêu trên hiện diện; danh sách root có XID thật. Đây là kiểm tra chỉ đọc.
- Rust fixtures chạy `xprop` giả trong subprocess có PATH riêng: thiếu executable, exit khác 0, thiếu/sai property, danh sách rỗng hợp lệ và từ chối action chưa được công bố. Không dùng X server thật cho các ca lỗi này.
- Native `desktop_smoke.py --platform-tool-missing --inspect`: khởi động profile test với PATH rỗng, đọc được lỗi `xprop_unavailable` trong Studio và nút launcher vẫn tồn tại; không gửi input. Báo cáo `platform-tool-missing-result.json` trong thư mục test. Sau ca này khởi động lại profile với PATH thông thường.

Chưa có môi trường Wayland thử nghiệm, chưa đổi session hoặc bật GNOME unsafe mode trong phiên triển khai. Những ô chưa kiểm thử ở trên không được coi là đã đạt G9.1–G9.4.
