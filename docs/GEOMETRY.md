# Tọa độ Dock, popup và tooltip

G2.9 dùng một module geometry cho Dock, popup và tooltip. Quy ước không trộn đơn vị:

| Giá trị | Đơn vị / nguồn |
| --- | --- |
| Rect, work area, monitor origin | Physical screen pixels; có thể có origin âm |
| Native outer_position / outer_size | Physical screen pixels của cửa sổ thực |
| Tâm nút từ getBoundingClientRect | Logical WebView pixels, tương đối với Dock |
| anchor_x | Physical screen X = Dock origin + offset logical × scale của WebView Dock |
| Kích thước nội dung popup / margin / gap | Logical pixels, đổi theo scale màn hình đích |
| set_position / set_size | PhysicalPosition / PhysicalSize; không nhân scale lần hai |

Anchor được đổi trước khi đặt popup; không dùng scale đích để đổi một offset của nguồn. Launcher click/Enter gửi tâm nút thật. Launcher qua phím tắt không có nút nguồn thì lấy tâm chiều rộng Dock thật thay cho mốc 150 cố định. Tooltip dùng cùng quy ước source anchor và cùng hàm đặt popup.

Dock lấy content width hiện hành, căn giữa work area màn hình đã chọn và dùng height cấu hình. Popup lấy outer rect Dock hiện hành, đặt trên/dưới với gap 14 logical px và clamp vào work area, không dùng kích thước Dock giả định 1100 px. Hai inset được giới hạn riêng theo chiều rộng/cao để work area rất nhỏ vẫn còn ít nhất một pixel. Margin dọc Dock không vượt khoảng trống sau khi tính height. Phép tính vị trí dùng i64 để offset rất lớn hoặc origin âm không làm tràn i32 trước khi clamp. Chỉ khi chiều rộng thay đổi, sau khi GTK xác nhận size của lần apply mới nhất, layout được phép căn lại position đúng một lần nếu WM đã dùng allocation cũ để constrain một lượt chuyển màn hình. Target mới thay target cũ; size event không khớp không tiêu thụ target, không sửa khi popup đang mở, không đặt lại focus hoặc tạo vòng timer/configure vô hạn. Thay height để auto-hide không tạo target căn lại position. Ca wide HDMI → small eDP từng dừng ở y=32 thay vì y=16 đã được tái hiện trước sửa và qua sau sửa.

Đầu vào placement là work area không rỗng do monitor API cung cấp; geometry không thay thế giới hạn kích thước nội dung của GTK/WebKit.

Kiểm thử đơn vị bao gồm origin âm cả X/Y, scale 1/1.25/1.5/2, top/bottom, hidden Dock, anchor i32 min/max, nội dung vượt work area và vùng rộng/cao chỉ 1–20 physical px. Một ca số cụ thể dùng source scale 1.25 và destination scale 2 để xác minh source offset chỉ đổi một lần; đây là kiểm thử toán, không phải bằng chứng mixed DPI native.

```sh
cargo test --offline --manifest-path src-tauri/Cargo.toml --target-dir src-tauri/target/agent --lib geometry::tests
/usr/bin/python3 tests/desktop_smoke.py --geometry-smoke
/usr/bin/python3 tests/desktop_smoke.py --tooltip-smoke --focus-smoke
```

Geometry smoke đọc topology bằng xrandr, work area bằng GDK, native rectangles bằng xwininfo với PID/XID đã kiểm tra thuộc app riêng. Chỉ gửi input sau guard GNOME unlocked/focus/PID. Cấu hình được nhập qua UI và khôi phục trong finally. Top dùng Dock theo nội dung gốc; bottom thêm pin placeholder /bin/true để Dock rộng gần hết màn hình, bắt buộc đi qua clamp trái của launcher và clamp phải của lịch. Harness chỉ mở popup, không launch các pin placeholder. Nhánh geometry mặc định không thay mode/scale/origin màn hình; các ca đổi resolution/output có lệnh và phạm vi riêng trong bản ghi bằng chứng.

Môi trường GUI tham chiếu là GNOME 46/X11, hai màn hình scale 1: HDMI-0 work area (1920,32,1920,1048), eDP-1-1 (0,0,1920,1080). [Lượt GTK scale 2](benchmarks/geometry-scale2-2026-10-30/result.json) đã qua 16 ca, cùng hồi quy scale 1. Đây là application scale qua `GDK_SCALE=2 GDK_DPI_SCALE=0.5`, không phải scale compositor hoặc bằng chứng mixed DPI. G2.10 còn mở vì origin âm native, fractional 125/150% và mixed DPI chưa có đủ bằng chứng.

G2.11 đã qua [một vòng rút/cắm HDMI vật lý](benchmarks/physical-hotplug-2026-10-30/result.json): Dock fallback, mở lịch trên màn hình còn lại, giữ cấu hình monitor ưu tiên rồi quay về sau reconnect. XRandR báo connector connected nhưng output chưa active khi cắm lại; harness áp lại layout đã lưu để bật output và kiểm bước quay về. [Sáu vòng software output off/on](benchmarks/output-fallback-2026-10-30/result.json) bổ sung stress top/bottom, được ghi riêng với rút/cắm thật. Các ca opt-in khôi phục mode/refresh/position/primary và cấu hình test trong finally; không suy thành hỗ trợ mọi topology hoặc DPI.
