# Khảo sát compositor Wayland — G9.1

Compositor mục tiêu đầu tiên là GNOME Shell 46 / Mutter 46.2 vì desktop đang sử dụng trên máy tham chiếu là GNOME 46, còn COSMIC Files chỉ là ứng dụng cài trong phiên đó. KDE/COSMIC không được chọn thay cho môi trường có thể kiểm chứng. Quyết định adapter và mức hỗ trợ sản phẩm vẫn thuộc G9.2–G9.4.

Ngày 29/10/2026 đã chạy GNOME Wayland headless thật trên một output ảo 1280×720, với session D-Bus, Wayland socket, XDG runtime/config/data/cache và GSettings keyfile riêng. Không kết nối DISPLAY của desktop thật, không gửi input, không thay compositor đang dùng và không bật Shell unsafe mode. Đây là khảo sát API compositor, chưa phải chứng nhận Dock/Tauri hoạt động đúng trên Wayland.

| Phạm vi | Bằng chứng và hệ quả |
| --- | --- |
| Placement / auto-hide | Registry có xdg_wm_base v6, gtk_shell1 v5, wl_output v4 và fractional-scale v1. Không có zwlr_layer_shell_v1. Một xdg_toplevel thông thường không được đặt absolute screen position như Dock X11; không thể suy set_position thành dock placement thành công. Prototype GNOME cần thử tích hợp Shell hoặc công bố giới hạn. |
| Liệt kê cửa sổ | Không có wlr/ext foreign-toplevel globals. Gọi org.gnome.Shell.Introspect.GetWindows từ client thông thường nhận AccessDenied. Sự tồn tại của object D-Bus không chứng minh client có quyền đọc cửa sổ. |
| Chuyển / đóng cửa sổ | Có xdg_activation_v1 v1 cho activation có token, không có API generic để chọn rồi điều khiển cửa sổ của client khác. Shell Eval trả (false, "") với unsafe mode mặc định; không dùng Eval làm backend hoặc tự bật unsafe mode. Cần prototype tích hợp được GNOME cho phép, rồi kiểm tra exact target/consent/lifetime. |
| Icon / identity | xdg_toplevel.set_app_id là identity của ứng dụng, nên dùng desktop ID bỏ hậu tố .desktop để resolve icon/nhóm; không dùng XID/WM_CLASS của XWayland làm identity cho cửa sổ Wayland native. XML xdg-shell cài trên máy mô tả app_id dùng để nhóm và tìm desktop entry. Việc nhận identity của cửa sổ khác còn phụ thuộc API enumeration được cho phép; chưa coi matching/icon native đã đạt. |
| Global shortcut | org.freedesktop.portal.GlobalShortcuts không được xuất trên portal của phiên lab. Máy có xdg-desktop-portal 1.18.4, GTK backend 1.15.1 và COSMIC metadata; gói xdg-desktop-portal-gnome không được cài. Các backend metadata hiện có không khai báo GlobalShortcuts. Đây là kết quả của bộ backend đang cài, không khẳng định mọi GNOME 46 hay GNOME mới hơn đều thiếu API. G8.7 còn cần đường hướng dẫn gán phím trong desktop khi portal thiếu. |
| Wallpaper | Schema org.gnome.desktop.background đọc/ghi được picture-uri trong keyfile riêng, đã set/read/restore thành công. Đây chỉ là roundtrip settings; chưa chứng minh ảnh hiển thị hoặc adapter wallpaper đã qua luồng Wayland. Không bật adapter KDE/COSMIC chỉ từ việc có gsettings. |

Phần identity đối chiếu `/usr/share/wayland-protocols/stable/xdg-shell/xdg-shell.xml`, request `set_app_id`. Registry là bằng chứng từ socket đang chạy, không phải suy hỗ trợ từ file XML trên đĩa. Các interface chưa có được ghi là vắng trong registry của phiên lab này.

## Chạy lại và ranh giới an toàn

```sh
/usr/bin/python3 tests/wayland_lab.py --output /tmp/deskmorph-wayland-lab-results/capabilities.json
```

Harness tạo TemporaryDirectory mode riêng, cập nhật activation environment chỉ trên bus riêng để portal/helper dùng đúng socket. Trước probe kiểm PID executable là gnome-shell và marker runtime riêng. Nó lấy registry qua libwayland-client, gọi DisplayConfig/GetWindows/Eval/portal version và kiểm settings roundtrip. Không inject bàn phím/chuột; Eval chỉ là probe đọc số cửa sổ, bị từ chối, không thay global state.

Supervisor chạy trong process group riêng; harness làm child subreaper, giữ các PID thuộc bus/descendant có marker đúng, stop/reap trong finally kể cả startup lỗi, và xác minh mọi tiến trình đã dừng trước khi xóa runtime. Log nằm cạnh JSON trong thư mục output; báo cáo bền vững chỉ chứa API/version/topology/PID của lab. Ca cuối GNOME PID 1468985 exit 0, ownedProcessesExited=true. Lượt đầu gặp tên enum GI sai trước khi compositor khởi động; đã sửa và chạy lại, không dùng lượt lỗi làm bằng chứng.

[Bản ghi đầy đủ](benchmarks/wayland-survey-2026-10-29.json). G9.1 hoàn thành khảo sát. G9.2 chưa có prototype đạt cả placement/auto-hide và enumerate/activate/close; G9.3 chưa quyết định triển khai adapter, G9.4 chưa qua luồng sản phẩm. Scale phân số và hotplug của Dock thực vẫn thuộc G2.10–G2.11; một output headless scale 1 không thay thế các ca đó.

Đã bổ sung [hướng dẫn GNOME gán/gỡ phím mở Studio](WAYLAND_SHORTCUTS.md), đối chiếu GNOME Help và schema cài trên máy; Studio cũng hiện hướng dẫn ngắn khi nhận diện GNOME Wayland. Chưa có CLI mở launcher hoặc bằng chứng custom shortcut/activation Wayland, nên G8.7 vẫn mở.
