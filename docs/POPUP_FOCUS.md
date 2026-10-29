# Focus và đóng popup

Mốc G2.8 được kiểm trên Pop!_OS 24.04 / GNOME 46 / X11 / scale 1. Không suy hành vi của window manager này thành bảo đảm cho compositor Wayland hoặc desktop chưa thử.

Escape được xử lý một lần tại GTK toplevel bởi popup coordinator, truyền generation hiện hành vào hide. Không còn listener Escape riêng trong WebView lịch hoặc context menu gửi hide không generation. Bấm ngoài dùng watcher X11 có generation; mất focus đợi 120 ms rồi kiểm tra lại native focus và generation để bỏ notification cũ từ hide/show nhanh. Cả ba đường đều dùng cùng coordinator, phát visibility events và áp dụng layout đang chờ. Audio/system Close truyền opening generation; yêu cầu cũ không đóng popup thay thế.

Khi người dùng mở popup, native window nhận focus tại thao tác mở. Callback WebKit sau mapping chỉ được grab focus cho nội dung khi popup còn đúng generation và native window vẫn có focus. Callback này không gọi present toplevel nữa. Shortcut toàn cục dùng timestamp của key event cho present_with_time thay vì tự tạo một yêu cầu focus CurrentTime trễ.

Khi đóng, ứng dụng để window manager chọn cửa sổ tiếp theo; không lưu target rồi đặt focus lại bằng một timer. Trên môi trường tham chiếu, Escape/Close từ popup Dock trả về đúng native Dock XID, DOM nút nguồn vẫn giữ focus và Enter mở lại đúng popup. Shortcut mở launcher từ cửa sổ GTK bên ngoài rồi Escape trả đúng XID nguồn. Nếu người dùng bấm Studio hoặc chọn GTK khác, cửa sổ mới được giữ focus; đóng popup sau đó không khôi phục nguồn cũ lên trên lựa chọn mới. Chọn hàng trong window list giữ focus trên đúng XID đã activate.

Harness:

```sh
/usr/bin/python3 tests/desktop_smoke.py --focus-smoke
/usr/bin/python3 tests/desktop_smoke.py --focus-delay
/usr/bin/python3 tests/desktop_smoke.py --popup-smoke
```

Focus smoke nhập cấu hình test qua UI, giữ bản gốc và khôi phục trong finally; chord Ctrl+Alt+Shift+J chỉ được gửi sau khi backend báo đăng ký thành công. Mọi input có guard desktop unlocked/native focus/owned PID; fixture GTK do harness tạo, đọc XID/PID/WM_CLASS trước khi cho phép input. Ngoài click Studio là click XTest thật vào điểm đã xác minh nằm ngoài popup. Kiểm tra native _NET_ACTIVE_WINDOW kết hợp Enter lại không dùng helper refocus để chứng minh cả native và DOM focus. Mỗi lần chuyển focus giữ quan sát thêm 0,7 giây để bắt callback muộn.

Chế độ focus-delay chỉ hoạt động trong debug build, biến DESKMORPH_TEST_POPUP_FOCUS_DELAY_MS=500 trì hoãn callback focus nội dung native (giới hạn 0–1000 ms). Log opt-in chỉ ghi generation và active/focused, không title/arguments. Harness xác minh log đã có callback chạy khi generation còn active nhưng native popup mất focus, không chỉ callback đã hết hạn. Sau ca này harness restart app test bình thường để bỏ biến timing. Release bỏ toàn bộ điều khiển delay/log. Đây là delay callback GTK/WebKit, không phải trì hoãn GIO launch hay giả hủy IPC.

Giới hạn phím tắt trong phiên đo này: Ctrl+Alt+Super+K/J đăng ký được đủ core X11 lock masks (client thứ hai nhận BadAccess cho từng mask) nhưng không phát KeyPress tới worker khi dùng XTest. Ctrl+Alt+Shift+J nhận event và vượt cả hai luồng focus từ cửa sổ ngoài. Chưa xác định thành phần xử lý tổ hợp Super; không coi core grab thành công là bảo đảm desktop sẽ chuyển mọi tổ hợp tới app. Không thay cấu hình phím tắt của desktop để ép ca qua; backend shortcut không đổi trong G2.8.

Helper nhập text đọc modifier/XKB keysym để gõ đúng khi Caps Lock bật, không bật/tắt lock của người dùng. Helper từ chối Ctrl+Alt+F1–F12 kể cả có thêm Super vì Xorg có thể chuyển virtual terminal trước passive grab. Một probe phụ đã gửi nhầm tổ hợp chuyển console; phiên GNOME session 2 được khôi phục bằng loginctl activate, xác minh Active=yes, rồi mới chạy tiếp. Không dùng lượt probe đó làm bằng chứng kiểm thử popup.
