# Gán phím từ desktop khi thiếu GlobalShortcuts portal

DeskMorph hiện đăng ký phím tắt launcher trực tiếp trên X11. Trên Wayland, ô đăng ký trong Studio bị vô hiệu hóa. Kết quả lab GNOME Shell 46 / Mutter 46.2 với xdg-desktop-portal 1.18.4 và GTK backend 1.15.1: interface `org.freedesktop.portal.GlobalShortcuts` không được xuất. Máy lab không cài backend portal GNOME. Đây là giới hạn của bộ backend được đo, không phải kết luận cho mọi phiên GNOME. [Bằng chứng portal và protocol](WAYLAND_RESEARCH.md).

Executable hỗ trợ `--launcher` để mở cửa sổ **DeskMorph Launcher** của cùng profile, kể cả khi Dock tắt. Trên Wayland đây là cửa sổ thông thường có titlebar, xuất hiện trong trình chuyển cửa sổ; compositor quyết định vị trí và focus. Lệnh không có đối số vẫn mở Studio. Custom shortcut GNOME 46 đã được kiểm qua backend media-keys thật trong lab Wayland riêng; phạm vi và giới hạn nằm bên dưới.

## GNOME: tạo phím mở launcher

1. Cài executable ở vị trí cố định theo [README](../README.md#build-và-cài-thủ-công). Xác định đường dẫn tuyệt đối, ví dụ `/home/ban/.local/bin/deskmorph`. Không dùng executable trong thư mục build tạm, `~` hoặc `$HOME` trong ô lệnh: trình gán phím không nhất thiết chạy qua shell.
2. Mở **Settings → Keyboard → View and Customize Shortcuts → Custom Shortcuts → Add**. Tên mục có thể được dịch theo ngôn ngữ desktop. Tài liệu GNOME cài trên máy mô tả đường **Keyboard → View and Customize Shortcuts → Custom Shortcuts → +**; dùng tìm kiếm Settings nếu bố cục phiên bản khác.
3. Đặt tên **DeskMorph Launcher**. Nhập lệnh dưới đây, thay đường dẫn ví dụ bằng executable thực. Dấu ngoặc kép cần thiết khi đường dẫn chứa khoảng trắng:

   ```text
   env WEBKIT_DISABLE_DMABUF_RENDERER=1 "/home/ban/.local/bin/deskmorph" --launcher
   ```

4. Chọn một tổ hợp chưa dùng. Nếu Settings báo xung đột, chọn tổ hợp khác; không thay phím desktop đang cần. Không dùng Ctrl+Alt+F1–F12 vì có thể chuyển console. DeskMorph không tự ghi đè phím đã gán của desktop.
5. Lưu rồi thử từ một cửa sổ khác. Khi chưa chạy, DeskMorph mở launcher và giữ Studio ẩn. Khi cùng profile đang chạy, lệnh chuyển yêu cầu sang instance đó. Launcher thường không tự ẩn khi mất focus, để bạn chọn vào từ trình chuyển cửa sổ nếu GNOME từ chối activation; Escape hoặc nút đóng titlebar ẩn launcher và giữ ứng dụng chạy. Xóa `--launcher` nếu muốn phím mở Studio. Không coi exit code 0 là bằng chứng cửa sổ nhận phím. Sau nâng cấp từ binary cũ, thoát instance cũ rồi mở lại để nhận giao thức launcher mới.
6. Để gỡ, quay lại Custom Shortcuts và xóa riêng mục DeskMorph Launcher. Tắt phím tắt trong DeskMorph không xóa phím do GNOME quản lý; gỡ executable cũng không tự xóa mục này.

Nếu dùng profile riêng, thêm `DESKMORPH_CONFIG_HOME` với đường dẫn tuyệt đối sau `env`, trước executable. Để mở instance thông thường, bỏ biến này. Đừng thay `XDG_CONFIG_HOME` chỉ để chạy DeskMorph: biến đó còn ảnh hưởng cấu hình các dịch vụ desktop.

## Kiểm tra khi không hoạt động

- Chạy chính lệnh đã nhập trong terminal để kiểm tra executable, thư viện và lỗi startup. Lệnh ở trên cần đường dẫn thật; không chép nguyên ví dụ `/home/ban` nếu đó không phải tài khoản của bạn.
- Nếu binary đã đổi vị trí, sửa đường dẫn của phím tắt. Chỉ đăng ký menu ứng dụng không tự tạo hoặc sửa custom shortcut.
- Nếu mở ra instance khác, kiểm tra profile và các biến môi trường trong lệnh. Không xóa lock/socket của instance đang chạy để ép mở thêm bản khác.
- Nếu portal xuất hiện sau khi cài backend khác, điều đó chưa tự bật tính năng trong DeskMorph. Cần triển khai và kiểm session/permission/Activated/deactivation/cleanup trước khi công bố hỗ trợ.
- KDE Plasma và COSMIC có trình gán phím riêng. Chưa kiểm giao diện/lệnh/activation trên các phiên đó; không áp dụng đường Settings của GNOME rồi coi đã xác minh.

## Phạm vi đã xác minh và phần còn mở

Đường Settings và ý nghĩa Name/Command/Shortcut được đối chiếu với tài liệu GNOME cài tại `/usr/share/help/C/gnome-help/keyboard-shortcuts-set.page`. Schema `org.gnome.settings-daemon.plugins.media-keys` có `custom-keybindings`; schema relocatable `org.gnome.settings-daemon.plugins.media-keys.custom-keybinding` có `name`, `command`, `binding`. Không ghi các key này vào desktop của người dùng để kiểm tài liệu. Các bước tạo/gỡ qua giao diện chưa được chạy; schema/backend thật đã được kiểm bằng custom binding trong lab Wayland riêng.

Single-instance forwarding của executable đã có Rust socket/ACK tests và native X11 lifecycle tests. Những bằng chứng đó không chứng minh activation trên Wayland hoặc một custom shortcut thực sự nhận tổ hợp phím. Lệnh chuyên dụng đã qua [native GNOME 46 Wayland lab](benchmarks/wayland-launcher-command-2026-10-29.json): cold/warm, tìm kiếm bằng phím thật sau activation rõ ràng của lab, Escape, Dock tắt, titlebar Close và lệnh mặc định mở Studio. Lượt cuối GNOME không tự cấp focus cho cold hoặc warm; harness chủ động activate cửa sổ đúng PID trước khi gõ. Backend nhận XDG_ACTIVATION_TOKEN/DESKTOP_STARTUP_ID và chuyển token theo request, nhưng đường token desktop thực chưa kiểm chứng. Đường token theo compositor vẫn chưa chứng nhận; xem bằng chứng phím thực bên dưới.


## Phím GNOME thực đã kiểm — G8.7

[Báo cáo](benchmarks/wayland-custom-shortcut-2026-10-29.json) dùng GNOME Shell46.0/Mutter46.2, gsd-media-keys thật và custom-keybinding schema trong settings riêng. Ctrl+Super+K từ cửa sổ GTK khác mở launcher cold/warm, tự nhận focus, gõ tìm kiếm bằng phím thật và Escape; không cần explicit activation của extension lab cho launcher. Tổ hợp trùng bị Mutter từ chối; gỡ binding giải phóng phím và không chạy command nữa. Bốn lượt hoàn chỉnh qua, không tác động shortcut desktop chính.

Wrapper của test chỉ ghi PID và boolean token trước khi exec lệnh --launcher; không tạo token hoặc activate cửa sổ. XDG_ACTIVATION_TOKEN/DESKTOP_STARTUP_ID đều vắng ở lượt cuối, nên không coi đây là test portal token. Đã kiểm đường schema/backend GNOME, chưa thao tác GNOME Settings GUI; menu hướng dẫn dựa trên Help/schema của GNOME46. Không áp kết quả sang KDE/COSMIC hoặc GNOME khác.

G8.7 chốt theo nhánh hướng dẫn gán phím desktop khi portal thiếu. Chạy lại bằng `/usr/bin/python3 tests/wayland_lab.py --shortcut-test --output /tmp/deskmorph-wayland-shortcut/results.json`. Đăng ký trực tiếp Wayland và GlobalShortcuts portal trong DeskMorph vẫn chưa được triển khai; native window management/Dock Wayland còn theo [quyết định adapter](WAYLAND_ADAPTER_DECISION.md).
