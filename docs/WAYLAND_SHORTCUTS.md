# Gán phím từ desktop khi thiếu GlobalShortcuts portal

DeskMorph hiện đăng ký phím tắt launcher trực tiếp trên X11. Trên Wayland, ô đăng ký trong Studio bị vô hiệu hóa. Kết quả lab GNOME Shell 46 / Mutter 46.2 với xdg-desktop-portal 1.18.4 và GTK backend 1.15.1: interface `org.freedesktop.portal.GlobalShortcuts` không được xuất. Máy lab không cài backend portal GNOME. Đây là giới hạn của bộ backend được đo, không phải kết luận cho mọi phiên GNOME. [Bằng chứng portal và protocol](WAYLAND_RESEARCH.md).

Có thể gán phím của desktop để **mở hoặc hiện lại Studio** bằng executable đã cài. Lệnh này chưa mở thẳng popup launcher; ứng dụng chưa có tùy chọn CLI cho thao tác đó. Hướng dẫn này không bật đăng ký phím Wayland trong DeskMorph, không bảo đảm focus trên mọi compositor và không thay thế kiểm thử launcher Wayland của G8.7.

## GNOME: tạo phím mở Studio

1. Cài executable ở vị trí cố định theo [README](../README.md#build-và-cài-thủ-công). Xác định đường dẫn tuyệt đối, ví dụ `/home/ban/.local/bin/deskmorph`. Không dùng executable trong thư mục build tạm, `~` hoặc `$HOME` trong ô lệnh: trình gán phím không nhất thiết chạy qua shell.
2. Mở **Settings → Keyboard → View and Customize Shortcuts → Custom Shortcuts → Add**. Tên mục có thể được dịch theo ngôn ngữ desktop. Tài liệu GNOME cài trên máy mô tả đường **Keyboard → View and Customize Shortcuts → Custom Shortcuts → +**; dùng tìm kiếm Settings nếu bố cục phiên bản khác.
3. Đặt tên **DeskMorph Studio**. Nhập lệnh dưới đây, thay đường dẫn ví dụ bằng executable thực. Dấu ngoặc kép cần thiết khi đường dẫn chứa khoảng trắng:

   ```text
   env WEBKIT_DISABLE_DMABUF_RENDERER=1 "/home/ban/.local/bin/deskmorph"
   ```

4. Chọn một tổ hợp chưa dùng. Nếu Settings báo xung đột, chọn tổ hợp khác; không thay phím desktop đang cần. Không dùng Ctrl+Alt+F1–F12 vì có thể chuyển console. DeskMorph không tự ghi đè phím đã gán của desktop.
5. Lưu rồi thử từ một cửa sổ khác. Khi chưa chạy, DeskMorph mở Studio. Khi instance cùng profile đang chạy, lần gọi sau chuyển yêu cầu tới instance đó để hiện Studio, không tạo Dock thứ hai. Đóng Studio có thể giữ app chạy nếu bật **Giữ Dock khi đóng Studio**. Trên Wayland, compositor quyết định quyền activation/focus; nếu chỉ thấy thông báo app đã sẵn sàng, dùng thông báo hoặc trình chuyển cửa sổ để vào Studio. Không coi exit code 0 của lệnh là bằng chứng cửa sổ đã nhận phím.
6. Để gỡ, quay lại Custom Shortcuts và xóa riêng mục DeskMorph Studio. Tắt phím tắt trong DeskMorph không xóa phím do GNOME quản lý; gỡ executable cũng không tự xóa mục này.

Nếu dùng profile riêng, thêm `DESKMORPH_CONFIG_HOME` với đường dẫn tuyệt đối sau `env`, trước executable. Để mở instance thông thường, bỏ biến này. Đừng thay `XDG_CONFIG_HOME` chỉ để chạy DeskMorph: biến đó còn ảnh hưởng cấu hình các dịch vụ desktop.

## Kiểm tra khi không hoạt động

- Chạy chính lệnh đã nhập trong terminal để kiểm tra executable, thư viện và lỗi startup. Lệnh ở trên cần đường dẫn thật; không chép nguyên ví dụ `/home/ban` nếu đó không phải tài khoản của bạn.
- Nếu binary đã đổi vị trí, sửa đường dẫn của phím tắt. Chỉ đăng ký menu ứng dụng không tự tạo hoặc sửa custom shortcut.
- Nếu mở ra instance khác, kiểm tra profile và các biến môi trường trong lệnh. Không xóa lock/socket của instance đang chạy để ép mở thêm bản khác.
- Nếu portal xuất hiện sau khi cài backend khác, điều đó chưa tự bật tính năng trong DeskMorph. Cần triển khai và kiểm session/permission/Activated/deactivation/cleanup trước khi công bố hỗ trợ.
- KDE Plasma và COSMIC có trình gán phím riêng. Chưa kiểm giao diện/lệnh/activation trên các phiên đó; không áp dụng đường Settings của GNOME rồi coi đã xác minh.

## Phạm vi đã xác minh và phần còn mở

Đường Settings và ý nghĩa Name/Command/Shortcut được đối chiếu với tài liệu GNOME cài tại `/usr/share/help/C/gnome-help/keyboard-shortcuts-set.page`. Schema `org.gnome.settings-daemon.plugins.media-keys` có `custom-keybindings`; schema relocatable `org.gnome.settings-daemon.plugins.media-keys.custom-keybinding` có `name`, `command`, `binding`. Không ghi các key này vào desktop của người dùng để kiểm tài liệu. Các bước tạo/gỡ qua giao diện chưa được chạy trên phiên Wayland.

Single-instance forwarding của executable đã có Rust socket/ACK tests và native X11 lifecycle tests. Những bằng chứng đó không chứng minh activation trên Wayland hoặc một custom shortcut thực sự nhận tổ hợp phím. Còn cần kiểm lệnh launcher chuyên dụng (hiện chưa có), activation token theo compositor, cold/warm start, tổ hợp xung đột, desktop gán/gỡ phím và cleanup trên phiên Wayland mục tiêu. G8.7 **chưa chốt**.
