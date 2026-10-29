# Bàn phím và accessibility

G5.9 trong kế hoạch triển khai **chưa chốt**. Tài liệu này tách các hành vi đã có bằng chứng khỏi phần còn cần kiểm tra; không phải tuyên bố tuân thủ WCAG hay chứng nhận trình đọc màn hình.

## Các thao tác hiện có

- Studio: Tab/Shift+Tab giữa nút điều hướng và các control; Enter chọn trang. Checkbox dùng Space, range/select dùng phím của control native.
- Màu chủ đạo: nhập `#RRGGBB` rồi Enter hoặc Lưu. Nút lưu vô hiệu hóa khi mã sai hoặc chưa đổi. Ô màu vẫn dùng được bằng chuột; đường bàn phím dùng ô mã màu vì input color của WebKit có thể bị bỏ qua khi Tab.
- Preset: Đổi tên đưa focus và chọn nội dung ô tên; Enter tạo/đổi tên, Hủy trả về ô tên. Xóa preset, ghim hoặc thư mục chuyển focus sang nút xóa kế tiếp/trước; hết danh sách thì về ô nhập tương ứng. Async completion không lấy focus từ control khác.
- Ghép lớp cửa sổ: Enter/Space mở/đóng disclosure; Tab vào textarea. Role button và aria-expanded bổ sung vì WebKit trên môi trường kiểm thử báo summary mặc định là unknown.
- Import/reset: focus vào vùng xem trước để đọc thay đổi, Tab tới Xác nhận rồi Hủy. Không có thay đổi thì bỏ qua nút Xác nhận disabled. Hủy trả về nút mở, xác nhận chuyển sang Hoàn tác; hoàn tác thành công trở về nút mở. Khóa request lặp trong pending; chờ WebView nhận focus lại sau chooser GTK, không lấy focus từ control khác.
- Lịch: một điểm Tab cho vùng ngày; mũi tên ±1/±7 ngày; Home/End đầu/cuối tuần từ thứ Hai; PageUp/PageDown đổi tháng, Shift đổi năm. Giữ ngày hợp lệ gần nhất khi tháng đích ngắn hơn. Enter/Space chọn, Escape đóng.
- Launcher: tìm kiếm, ArrowUp/Down, Ctrl+Home/End và Enter; Escape đóng. Danh sách cửa sổ có ArrowUp/Down, Home/End, Enter và Escape. Dock hỗ trợ Ctrl+Shift+Left/Right để sắp xếp ghim.

## Bằng chứng và giới hạn

| Phạm vi | Bằng chứng | Giới hạn |
| --- | --- | --- |
| Lịch: ngày đích, một điểm Tab, Enter/Escape và focus nhìn thấy | [Native và ảnh](benchmarks/calendar-keyboard-2026-10-29.json), `calendarNavigation.test.mjs` | Native X11, đặt focus ban đầu bằng AT-SPI; chưa chứng minh mọi đường vào lịch |
| Focus sau xóa và Enter đổi tên preset | [Native vi/en](benchmarks/removal-focus-2026-10-29.json), `removalFocus.test.mjs` | Không thay thế kiểm tra toàn bộ thứ tự Tab |
| Màu: định dạng, chỉ patch accentColor, disabled khi chưa đổi, theo config/picker | `appearanceColor.test.mjs`, [native vi/en](benchmarks/accent-keyboard-2026-10-29.json) | Native save qua ô mã màu; không tuyên bố chooser native hỗ trợ bàn phím |
| Studio: Tab/Shift+Tab, tên control và disabled | [Năm tab native](benchmarks/studio-tab-2026-10-29.json), [ảnh textarea focus](benchmarks/studio-disclosure-focus-2026-10-29.png) | 279 lượt control trên trạng thái profile test tiếng Việt; có 24 cặp Apply/Favorite nhưng chưa kích hoạt chúng |
| Import/reset: focus review, Cancel, confirm/undo, no-change disabled | [Native vi/en](benchmarks/config-review-focus-2026-10-29.json), `configReviewFocus.test.mjs` | GTK Open được đặt focus bằng AT-SPI rồi Enter; chưa kiểm toàn bộ navigation trong file chooser hoặc trải nghiệm đọc |
| Chữ lịch: ngày/weekday/banner/hôm nay | `calendarContrast.test.mjs` đọc CSS và composite nền trên trắng | Chỉ các cặp màu đã nêu; chưa audit toàn bộ ứng dụng |
| Scan issues disclosure | `wallpaperScan.test.mjs` kiểm role/aria-expanded khi toggle | Kiểm renderer bằng adapter, chưa thay thế kiểm native với lỗi scan |

`tests/studio_tab_smoke.py` kiểm cây accessibility của Studio: mọi control trong trạng thái hiện tại có tên, Tab theo thứ tự DOM, Shift+Tab đảo ngược và bỏ qua disabled. Chỉ chạy trong profile test `/tmp/deskmorph-desktop-test/config`; không thực thi các nút mở app/quit/autostart/import/reset. Harness chủ động thử Enter/Space trên disclosure đầu tiên và chụp focus textarea. `--studio-tab-only 0..4` cho phép xác minh từng trang. Guard native xác minh desktop không khóa và PID trước khi gửi phím; khi focus bị ứng dụng khác lấy, harness có thể kích hoạt lại đúng Studio test rồi kiểm guard lại.

## Các phần cần hoàn tất trước khi chốt G5.9

- Kiểm thêm trạng thái động: lỗi/conflict và concurrent review thực tế, thứ tự điều hướng đầy đủ trong hộp thoại file, thao tác wallpaper favorite/filter/paging và focus sau khi control biến mất/disabled. Import/reset review/cancel/confirm/undo đã có kiểm native vi/en.
- Kiểm đường vào/ra Dock và popup chỉ bằng bàn phím, cùng audio/media/system/context/window actions, kể cả thiếu capability/lỗi và pending.
- Audit contrast và focus nhìn thấy trên toàn bộ Studio, Dock và popup; gồm nền sáng/tối, opacity người dùng chọn, màu accent tùy chỉnh và control borders. Ảnh hoặc tính toán cặp màu riêng lẻ chưa chứng minh toàn bộ.
- Kiểm trình đọc màn hình thực tế, thứ tự đọc/announcement và tác động của role/aria trên WebKit phiên bản mục tiêu. AT-SPI tree chứng minh API được expose, chưa chứng minh trải nghiệm đọc đầy đủ.
