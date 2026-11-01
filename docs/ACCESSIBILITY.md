# Bàn phím và khả năng trợ năng

DeskMorph hỗ trợ điều khiển phần lớn thao tác hằng ngày bằng bàn phím, focus hiện rõ và tên control để đọc bằng trình đọc màn hình. Tài liệu này mô tả phạm vi đã kiểm chứng trên Pop!_OS/Ubuntu 24.04, GNOME 46, X11. Đây không phải chứng nhận WCAG toàn diện hay cam kết hỗ trợ mọi desktop/trình đọc màn hình.

## Dùng DeskMorph bằng bàn phím

### Dock và launcher

| Thao tác | Phím |
| --- | --- |
| Di chuyển giữa các icon và nút Dock | `Tab` / `Shift+Tab` |
| Mở icon, popup hoặc mục đang focus | `Enter` |
| Đóng popup và trả focus về nút vừa mở | `Escape` |
| Mở menu của icon Dock đang focus | `Shift+F10` hoặc phím `Menu` |
| Di chuyển trong menu | `Tab`, `Shift+Tab`, `Mũi tên lên/xuống` |
| Đến đầu/cuối menu | `Home` / `End` |
| Sắp xếp icon đã ghim | `Ctrl+Shift+Mũi tên trái/phải` |

Trong launcher, gõ để tìm kiếm, dùng `Mũi tên lên/xuống` để chọn kết quả, `Ctrl+Home`/`Ctrl+End` để đến đầu/cuối và `Enter` để mở. `Escape` đóng launcher.

Nếu Dock đang tự ẩn, vào Studio > **Taskbar Studio** > **Điều khiển Dock bằng bàn phím**, rồi nhấn `Enter` để đưa focus vào Dock. Nút này sẽ bị khóa nếu Dock đang tắt hoặc cách đặt Dock hiện tại không hỗ trợ.

### Studio

- `Tab` và `Shift+Tab` di chuyển giữa thanh điều hướng và các control; `Enter` chọn trang hoặc kích hoạt nút.
- Checkbox dùng `Space`; select, thanh range và ô nhập dùng các phím mặc định của control.
- Các nút đang bị khóa được bỏ qua khi di chuyển bằng `Tab`.
- Trong mục Giao diện, nhập màu theo dạng `#RRGGBB`, rồi nhấn `Enter` hoặc **Lưu**. Nút Lưu chỉ bật khi màu hợp lệ và có thay đổi.
- Với preset, `Enter` tạo hoặc đổi tên; **Hủy** trả focus về ô đặt tên. Sau khi xóa một mục, focus chuyển tới mục gần nhất còn lại.
- Với nhập/xuất cấu hình, focus đi vào phần xem trước thay đổi, sau đó đến **Xác nhận** hoặc **Hủy**. Khi không có thay đổi, nút Xác nhận không kích hoạt.

### Lịch và pop-up

| Thao tác | Phím |
| --- | --- |
| Đi một ngày / một tuần | `Mũi tên` |
| Đến đầu/cuối tuần | `Home` / `End` |
| Đổi tháng | `PageUp` / `PageDown` |
| Đổi năm | `Shift+PageUp` / `Shift+PageDown` |
| Chọn ngày | `Enter` hoặc `Space` |
| Đóng lịch | `Escape` |

Trong popup âm thanh, media và hệ thống, DeskMorph giữ focus ở control vừa dùng sau khi request hoàn tất nếu bạn chưa chuyển focus sang nơi khác. Nếu thiết bị hoặc control đang focus biến mất, focus chuyển về nút **Đóng** hoặc control khả dụng phù hợp.

### Menu ứng dụng và các thao tác cần xác nhận

Menu icon Dock hỗ trợ `Tab` hai chiều, mũi tên, `Home`/`End`, `Enter` và `Escape`. Các nút đang khóa được bỏ qua. Khi mở xác nhận buộc dừng, focus bắt đầu ở **Hủy** để tránh kích hoạt nhầm; `Escape` hoặc Hủy trả focus về nút **Buộc dừng**.

Với chọn file khi nhập cấu hình, có thể dùng `Tab`/`Shift+Tab` giữa danh sách file, **Mở** và **Hủy**; `Home` chọn mục đầu danh sách và `Enter` mở file đang chọn. Hành vi này đã được kiểm chứng với file fixture trong môi trường tham chiếu, không bao quát mọi cách duyệt tệp của GTK.

## Hỗ trợ trình đọc màn hình

- Các control quan trọng có tên truy cập được, trạng thái disabled và focus hiển thị.
- DeskMorph hỗ trợ giao diện tiếng Việt và tiếng Anh; thông báo lỗi mở ứng dụng và cảnh báo xác nhận buộc dừng đã được kiểm chứng với Orca trong ca menu ứng dụng.
- Trên GNOME/X11 tham chiếu, Orca đã được kiểm chứng với Tab/Shift+Tab, bỏ qua nút disabled, mũi tên, đóng menu, lỗi mở ứng dụng và xác nhận buộc dừng trong cả tiếng Việt và tiếng Anh.
- Nếu Orca đang dùng chế độ điều hướng đọc văn bản, `Home` và `End` có thể do Orca giữ lại thay vì chuyển đến DeskMorph. Trong ca kiểm thử, chế độ bypass navigation của Orca được bật/tắt bằng `Alt+Backspace`; đây không phải cam kết tương thích mặc định cho mọi cấu hình Orca.

DeskMorph không tuyên bố đã được kiểm chứng với mọi theme, mọi trạng thái động, mọi trình đọc màn hình hay mọi phiên Wayland. Nếu bạn gặp control không đọc được hoặc focus không rõ, hãy gửi kèm phiên desktop, ngôn ngữ giao diện và các bước tái hiện.

## Phạm vi đã kiểm chứng

Đã kiểm chứng native trong môi trường tham chiếu: điều hướng Studio, Dock, launcher, lịch, menu ứng dụng, popup âm thanh/media/hệ thống, thao tác file chooser cơ bản và luồng focus sau khi control bị vô hiệu hóa hoặc biến mất. Các ca dùng Orca hiện tại tập trung vào menu ứng dụng; chúng không thay thế một đánh giá khả năng sử dụng bằng người dùng thật.

Báo cáo chi tiết và bằng chứng có thể tái hiện:

- [Tiến độ và kết quả kiểm thử](PROGRESS.md)
- [Đánh giá phạm vi còn lại và kết luận G5.9](REMAINING_ACCEPTANCE.md)
- [Hồi quy Orca trên bản hiện tại](benchmarks/orca-current-regression-2026-10-30/result.json)
- [Kiểm thử thông báo lỗi native cho Orca](benchmarks/orca-native-announcement-2026-10-30/result.json)
- [Hồi quy bàn phím của menu ứng dụng](benchmarks/orca-native-announcement-2026-10-30/keyboard.json)

## Mẹo khi gặp sự cố

- Dùng `Escape` để đóng popup/menu trước, sau đó dùng `Tab` để xác định lại vị trí focus.
- Nếu Dock tự ẩn, đưa focus vào Dock từ Studio thay vì click vào vùng trống của màn hình.
- Nếu phần mềm đọc màn hình cản trở các phím điều hướng, thử tắt chế độ đọc văn bản của nó hoặc dùng các phím `Tab` và `Shift+Tab` để di chuyển giữa control.
- Báo lỗi kèm ảnh chụp, ngôn ngữ giao diện và chuỗi phím đã bấm; thông tin này giúp tái hiện lỗi nhanh hơn.
