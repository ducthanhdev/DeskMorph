# Changelog

## Unreleased — development 0.1.0

- Thêm native config store có schema/revision, migration, recovery, cập nhật serialized, import/export/reset review và undo.
- Tách X11 window backend, popup coordinator, monitor geometry, single-instance và đăng ký autostart/menu entry.
- Thêm catalogue GIO, launcher/search tiếng Việt, icon theme, desktop actions, pin/reorder và nhóm cửa sổ.
- Sửa vòng đời catalogue monitor/theme invalidation và timer polling khi ẩn/hiện; bổ sung regression fixtures XDG/locale/visibility/launch, D-Bus riêng và polling cleanup.
- Phát hiện capability cửa sổ từ EWMH, xử lý xprop/property lỗi rõ ràng; thêm ACK/deadline/cleanup single-instance, exit code startup lỗi và dừng topology/clock khi không cần.
- Tách Studio thành các panel, preview dùng chung tokens, presets, vi/en và reduced motion.
- Thêm thư viện hình nền giới hạn tài nguyên, cache thumbnail, filter/favorites, GNOME shuffle/scheduler.
- Thêm popup audio/media với pactl subscription, MPRIS player selection/capabilities, artwork cục bộ và cleanup.
- Thêm pin/mạng qua UPower/NetworkManager, popup CPU/RAM, lối mở Downloads và trạng thái thiếu system monitor/Trash handler.
- Bổ sung unit/native test harness và workflow CI. Thu hẹp WebView CSP/asset/IPC, bỏ plugin opener và font remote; đã kiểm tra thumbnail render thật và force-close đúng X client với PID giả.
- Sửa bỏ sót click ngoài ngắn bằng XInput2 (thêm libxi-dev), cấp focus nội dung sau GTK map và xử lý Escape ở GTK toplevel. Thêm stress ba vòng popup, fixture force-close và ảnh Studio thật trong README; còn tiếp tục kiểm tra ma trận focus/auto-hide.
- Gắn generation cho visibility của audio/media/system; đối chiếu con trỏ native khi tự ẩn và tránh panic tooltip chưa map. Chuỗi native top/bottom, popup stress, audio/media, thumbnail, close/force-close và exit/relaunch đã qua trên GNOME/X11 tham chiếu.

- Thêm phím tắt launcher X11 tùy chỉnh, mặc định tắt; checked XCB grabs với trạng thái xung đột/thử lại, pause theo Dock, giải phóng khi thoát và focus bằng timestamp phím. Thêm libxcb1-dev và kiểm thử native đăng ký/xung đột cùng GUI xuyên ứng dụng. CI dùng Xvfb cho native grab test; chưa chạy workflow trên GitHub.

- Đồng bộ trực tiếp danh sách cửa sổ và menu chuột phải khi title/active/thêm/bớt thay đổi; dừng poll khi popup ẩn và truyền generation cho callback đóng. Giữ lựa chọn theo XID, chuyển focus sang hàng kế bên khi cửa sổ mất, bổ sung native fixture cho bàn phím và pinned/unpinned 0/1/nhiều cửa sổ.

- Sắp xếp pin bằng Pointer Events/capture, lưu một lần khi thả, hủy Escape/thả ngoài và không mở app sau kéo. Giữ focus khi đổi thứ tự bằng bàn phím, bỏ ghi ở biên; sửa tooltip chiếm focus và áp dụng chiều rộng Dock chờ sau khi popup đóng để icon mới không bị widget che. Thêm native test reorder/cancel/menu/restart và marker phát hiện mở app ngoài ý muốn.

- Thống nhất tooltip Dock cho ứng dụng và widget với delay 500 ms; sửa chiều cao native GTK 200 px thành 44 px, ellipsis tên dài và accessible name. Thêm native test top/bottom cho nội dung, geometry, focus, input region và ẩn khi popup mở.

- Thêm native GTK tests cho middle-click pinned/unpinned với multi-instance và single-instance; xác minh Desktop Actions chạy đúng argv và không lưu nút action từ ứng dụng trước.

Chưa phát hành: còn các cổng chất lượng G0–G9 trong kế hoạch, đặc biệt Wayland, mixed DPI/hotplug, sleep/resume, Wayland shortcuts portal, cài sạch và nâng cấp. Không coi mục Unreleased là tuyên bố mọi chức năng đã đạt chuẩn phát hành.
