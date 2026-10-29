# Khả năng desktop và phạm vi đã kiểm thử

Ma trận ban đầu cho G0.5/G2.1. Đây là bản development; cổng phát hành vẫn nằm trong [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md). Bằng chứng chi tiết và những ca còn thiếu nằm trong [PROGRESS.md](PROGRESS.md).

| Môi trường | Liệt kê / chuyển / yêu cầu đóng cửa sổ native | Dock / popup | Hình nền | Workspace | Global shortcut |
| --- | --- | --- | --- | --- | --- |
| Pop!_OS 24.04, GNOME 46.0, X11, x86_64 | Backend X11; GNOME công bố `_NET_CLIENT_LIST`, `_NET_ACTIVE_WINDOW`, `_NET_CLOSE_WINDOW`; đã qua native nhóm 0/1/nhiều pinned/unpinned, danh sách/menu cập nhật động, bàn phím/XID, close-confirmation và force-close fixture có PID giả, sentinel còn sống | Đã qua focus/Escape/outside-click, auto-hide top/bottom và stress ba vòng; overflow/mixed DPI/hotplug chưa hoàn tất | Adapter GNOME GSettings; áp dụng/shuffle/lịch một phút đã kiểm thử | Chưa triển khai | XCB tùy chọn; xung đột/retry/đổi/tắt/focus/exit-restart đã qua |
| X11 trên KDE, COSMIC hoặc desktop khác | Adapter dùng EWMH, chỉ bật capability API được phát hiện; chưa kiểm thử môi trường này | Chưa kiểm thử | Không bật adapter chưa xác minh | Chưa triển khai | Có code XCB, chưa kiểm thử desktop này |
| GNOME Shell 46 / Mutter 46.2 Wayland headless, output ảo scale 1 | Unsupported trong sản phẩm; prototype extension GNOME 46 qua enumerate/activate/close native fixture; API client thường bị chặn | Không có layer-shell; prototype actor Shell qua top/bottom và auto-hide, chưa tích hợp Dock Tauri | Adapter sản phẩm GNOME qua UI Apply/Retry; keyfile riêng light/dark và pixel stage hồng/xanh đã kiểm ở vi/en, scale1 ([bằng chứng](benchmarks/wallpaper-visible-2026-10-29/results.json)); chưa kiểm mọi mode/monitor | Chưa triển khai | Portal lab thiếu GlobalShortcuts; fallback custom shortcut GNOME46 qua gsd-media-keys có cold/warm/focus/search/Escape/gỡ phím; chưa triển khai portal |
| COSMIC cosmic-bg1.11.0 (9520e16), cosmic-comp8cb1802, backend winit lồng, output WINIT-0 scale1 | Chưa có adapter cửa sổ được xác minh | Chưa kiểm thử Dock production | Adapter RON v1 được nối sản phẩm; UI vi/en Apply/error/Retry/Shuffle và pixel, tạo all/per-output thiếu đã kiểm ([bằng chứng](benchmarks/cosmic-studio-2026-10-29/results.json)); chưa chứng nhận toàn desktop/multi-monitor/scheduler | Chưa triển khai | Chưa thử |
| KDE Plasma 5.27.12 / KWin 5.27.11 nested virtual | Chưa có adapter cửa sổ được xác minh | Chưa kiểm thử Dock production | API Plasma `evaluateScript` đã xác nhận trong runtime riêng; visible-pixel bị thiếu `wl_shm`, nên vẫn unsupported ([nghiên cứu](KDE_WALLPAPER.md)) | Chưa triển khai | Portal chưa thử trên compositor mục tiêu |

Có `DISPLAY`, XWayland hoặc file XML protocol trên đĩa không chứng minh ứng dụng có quyền quản lý cửa sổ Wayland native. Window backend và outside-click watcher X11 chỉ chạy khi `XDG_SESSION_TYPE=x11`. COSMIC Files cài trên máy tham chiếu là ứng dụng quản lý tệp; phiên desktop vẫn là GNOME.

## Phát hiện khi chạy

`get_platform_info` trả session/desktop thực tế, `windows.enumerate`, `windows.activate`, `windows.close`, `forceQuit`, `workspaces`, `wallpaper`, `dockPlacement`, `autoHide`, `unavailableReasons` theo từng tính năng, monitor topology và lý do thiếu hỗ trợ. `windowManagement` giữ ý nghĩa khả năng liệt kê để Dock tiếp tục hiển thị app đã ghim khi tính năng cửa sổ không khả dụng.

- Liệt kê cần gọi được `xprop` thành công và đọc `_NET_CLIENT_LIST` có kiểu WINDOW, kể cả danh sách rỗng hợp lệ. Thiếu property, sai kiểu/định dạng hoặc lỗi lệnh không được trả thành danh sách rỗng thành công.
- Chuyển/đóng cần window manager công bố chính xác atom EWMH tương ứng. UI tắt thao tác thiếu hỗ trợ; command kiểm tra lại trước gửi request. Command thành công nghĩa là đã gửi yêu cầu; window manager/ứng dụng vẫn quyết định chuyển focus hoặc hỏi xác nhận đóng.
- Force-close còn cần `xkill`; luôn yêu cầu xác nhận và không thay thế đóng bình thường. Hồi quy native của thay đổi force-close mới chưa hoàn tất.
- Workspace hiện luôn false và UI ghi “Đang phát triển”. Đặt cạnh/màn hình và tự ẩn chỉ bật trong phiên X11 có DISPLAY; đây là gate cho adapter hiện tại, không chứng nhận mọi WM X11. Nếu config đã lưu tự ẩn nhưng phiên chưa hỗ trợ, giữ giá trị cấu hình và cho Dock hiện đầy đủ. Hình nền GNOME bật khi desktop có token GNOME chính xác (phân tách bằng dấu hai chấm), schema/key tồn tại và các key light/dark ghi được. COSMIC dùng token COSMIC chính xác và cosmic-bg có sẵn, cấu hình RON v1 hợp schema, owner/path/file hợp lệ và target ghi được; probe không tạo file. Config sai/read-only có lý do vi/en; KDE và desktop chưa có adapter báo unsupported. CPU/RAM, UPower, NetworkManager, audio và MPRIS có trạng thái thiếu công cụ/service riêng.

Nút “Kiểm tra lại khả năng desktop” phát event tới các WebView để đọc lại capability. Lỗi probe xóa snapshot hỗ trợ cũ; loading/lỗi không được suy thành khả dụng. Ghim/mở app và chỉnh WM_CLASS thủ công vẫn dùng được khi không đọc được cửa sổ. Trạng thái Dock lúc này ghi chưa đọc được cửa sổ thay vì khẳng định 0. UI hiện lý do vi/en cho từng tính năng thiếu; thao tác activate/close/force-close và apply/shuffle kiểm tra gate trước dispatch.

## Bằng chứng hiện có

- Hình nền GNOME: backend kiểm tra transaction light/dark và đọc lại trước success; lỗi ảnh bị xóa không báo thành công. Studio đã phản ánh hai thay đổi từ bên ngoài qua polling. Scheduler đã qua xóa/khôi phục ảnh ở deadline thật và SIGSTOP/CONT riêng app qua hai chu kỳ; chưa kiểm thử system sleep. Xem [WALLPAPER.md](WALLPAPER.md) và [bản ghi](benchmarks/wallpaper-recovery-2026-10-29.json).

- `xprop -root _NET_SUPPORTED _NET_CLIENT_LIST` trên máy tham chiếu: ba API cửa sổ nêu trên hiện diện; danh sách root có XID thật. Đây là kiểm tra chỉ đọc.
- Rust fixtures chạy `xprop` giả trong subprocess có PATH riêng: thiếu executable, exit khác 0, thiếu/sai property, danh sách rỗng hợp lệ và từ chối action chưa được công bố. Không dùng X server thật cho các ca lỗi này.
- Native `desktop_smoke.py --platform-tool-missing --inspect`: khởi động profile test với PATH rỗng, đọc được lỗi `xprop_unavailable` trong Studio và nút launcher vẫn tồn tại; không gửi input. Báo cáo `platform-tool-missing-result.json` trong thư mục test. Sau ca này khởi động lại profile với PATH thông thường.

Đã có lab GNOME Wayland headless độc lập để khảo sát G9.1, ghi tại [WAYLAND_RESEARCH.md](WAYLAND_RESEARCH.md). Không đổi session desktop thật hoặc bật GNOME unsafe mode. G9.2 đã có [prototype](benchmarks/wayland-prototype-2026-10-29.json); G9.3 chốt [giới hạn adapter](WAYLAND_ADAPTER_DECISION.md). Sản phẩm trên GNOME Wayland vẫn unsupported cho placement/auto-hide/window management; prototype là experimental và G9.4 chưa đạt.


Icon catalogue trên GNOME/X11 tham chiếu đã qua GTK theme inheritance/hicolor/absolute SVG/PNG và theme switch trên IconTheme riêng; native pixels đã xác minh launcher, Dock ghim/chưa ghim, window rows. Nguồn được rasterize tối đa 64 px vào cache 512 PNG/32 KiB mỗi file; nguồn lỗi/vượt giới hạn hoặc class mơ hồ dùng fallback. Scope asset chỉ thêm cache icon riêng không đệ quy, không thêm source file. Xem APPLICATION_CATALOGUE.md và benchmarks/application-icons-2026-10-29.json; không suy phép đo scale 1 thành mixed-DPI hoặc native Wayland.


COSMIC wallpaper có [nghiên cứu API và pixel](benchmarks/cosmic-background-2026-10-29/results.json) trên compositor lồng commit8cb1802 + cosmic-bg1.11.0: private RON source Path, startup và atomic config update hiển thị đúng. Chưa có adapter sản phẩm hoặc chứng nhận toàn phiên COSMIC; capability vẫn unsupported. KDE chưa có runtime kiểm trên máy.


Nghiên cứu COSMIC bổ sung [per-output và state isolation](benchmarks/cosmic-per-output-2026-10-29/results.json): WINIT-0 override/fallback và live update đã kiểm pixel, chưa nối adapter. Đính chính lượt API cũ: thiếu XDG_STATE_HOME nên đã ghi state WINIT-0 host; lượt mới tách state và kiểm hash file host trước/sau. Không còn coi private config/runtime/bus là bằng chứng mọi state host bất biến.


Adapter COSMIC đã được tích hợp sau các bước research phía trên; các ghi chú “chưa nối/unsupported” ở báo cáo lịch sử mô tả trạng thái lúc chạy. Bản hiện tại có [kiểm Studio/IPC/pixel](benchmarks/cosmic-studio-2026-10-29/results.json), gồm fallback hệ thống/builtin, tạo entry còn thiếu và refresh list để cosmic-bg nạp per-output mới. Chỉ chứng nhận các luồng đã ghi trên đúng version/output lab; G9.4 và G6.9 toàn phạm vi vẫn mở vì chưa có KDE và các môi trường/ca còn lại.
