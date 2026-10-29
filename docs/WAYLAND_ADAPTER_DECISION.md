# Quyết định adapter Wayland — GNOME 46

Ngày 29/10/2026, chọn **công bố giới hạn của sản phẩm hiện tại**: chưa hỗ trợ quản lý cửa sổ, đặt Dock ở cạnh màn hình hoặc tự ẩn trên GNOME Wayland. Không bật capability sản phẩm từ kết quả prototype. Backend X11 tiếp tục chỉ dùng trong phiên X11. Quyết định này hoàn tất G9.3; kiểm thử sản phẩm theo từng tổ hợp/version ở G9.4 vẫn mở.

## Căn cứ thực nghiệm

[Khảo sát](WAYLAND_RESEARCH.md) đo GNOME Shell 46.0 / Mutter 46.2: không có layer-shell hoặc foreign-toplevel; client thông thường không có quyền GetWindows; Shell Eval bị chặn. Không có cơ sở xây adapter bằng các API chung đó trên stack này. Không dùng XWayland để suy danh sách cửa sổ native, không bật Shell unsafe mode, không giả lập key để điều khiển cửa sổ người dùng.

[Prototype và kết quả](benchmarks/wayland-prototype-2026-10-29.json) chứng minh một extension GNOME được người dùng bật có thể dùng `Main.layoutManager.addChrome`/St để đặt actor tại cạnh trên/dưới và tự ẩn theo pointer; `global.get_window_actors()`/Meta.Window để lấy app ID, stable sequence, PID, focus và yêu cầu đóng đúng cửa sổ Wayland native. Đây là API nội bộ Shell, cần thích ứng từng phiên bản. Một actor Shell không chứng minh cửa sổ Tauri có thể được đặt absolute position trên Wayland.

Prototype chạy trên compositor headless riêng, output 1280×720 scale 1, hai GTK fixture native. Sáu chu kỳ tự ẩn/hiện dùng thiết bị pointer ảo của **compositor lab**; không gửi input vào desktop host. Bốn lượt chuyển focus đúng stable ID, đóng cửa sổ thứ nhất giữ cửa sổ thứ hai, rồi đóng cuối khiến fixture thoát bình thường. Token sai/PID sai bị từ chối. Tắt extension gỡ D-Bus endpoint; supervisor dọn toàn bộ tiến trình lab. Đây là chứng minh kỹ thuật cho G9.2, chưa phải adapter phát hành.

## Hệ quả cho sản phẩm

| Phần | Quyết định hiện tại |
| --- | --- |
| Dock placement / auto-hide | Giữ unsupported trên GNOME Wayland. Không gọi `set_position` rồi báo thành công như X11. |
| Enumerate / activate / close | Giữ unsupported trong backend sản phẩm. Prototype Shell là experimental, chỉ hỗ trợ fixture trong lab. |
| Launcher shortcut | G8.7 tiếp tục mở: portal của lab thiếu interface, CLI launcher đã qua cold/warm/search/Escape trên Wayland lab; desktop shortcut/activation token thực chưa chứng minh. |
| Wallpaper | Kiểm độc lập G6.9; roundtrip GSettings không chứng minh ảnh render hoặc mọi desktop adapter. |
| KDE / COSMIC / GNOME phiên bản khác | Chưa kiểm chứng; không kế thừa kết luận hoặc API GNOME 46. |

Nếu triển khai GNOME adapter sau này, hướng đã có bằng chứng là extension tự nguyện, có phiên bản và luồng bật/tắt rõ ràng. Shell phải sở hữu UI đặt ở cạnh hoặc cần một cầu nối được kiểm chứng riêng; không hứa tái sử dụng nguyên cửa sổ Dock Tauri. Backend phải xác thực peer/session, ghép window identity với generation của Shell, kiểm capability, giới hạn IPC, xử lý extension mất/kết nối lại, popup/keyboard/activation và dọn tài nguyên. Token của lab và bộ lọc app ID fixture **không phải** thiết kế bảo mật của cầu nối production.

Không cài `tests/wayland_prototype` vào desktop thường: extension cố ý từ chối chạy khi thiếu runtime/marker/token riêng của harness. Để chạy lại:

```sh
/usr/bin/python3 tests/wayland_lab.py --prototype --output /tmp/deskmorph-wayland-prototype/results.json
```

Chưa có kiểm thử Tauri integration, multi-monitor, fractional DPI, hotplug, sleep/resume, overview/workspaces, fullscreen, accessibility hoặc vòng đời dài của extension. Không gắn nhãn verified cho toàn ứng dụng trên Wayland từ prototype này.
