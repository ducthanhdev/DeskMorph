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

Môi trường GUI tham chiếu là GNOME 46/X11, hai màn hình scale 1: HDMI-0 work area (1920,32,1920,1048), eDP-1-1 (0,0,1920,1080). [Lượt GTK scale 2](benchmarks/geometry-scale2-2026-10-30/result.json) đã qua 16 ca, cùng hồi quy scale 1. Đây là application scale qua `GDK_SCALE=2 GDK_DPI_SCALE=0.5`, không phải scale compositor hoặc bằng chứng mixed DPI. Fractional125/150% và mixed DPI đã có [48/48 ca native](benchmarks/dpi-native-full-matrix-2026-10-30/result.json), restore exact. G2.10 vẫn mở vì bốn tổ hợp HDMI200% ngoài system và topology âm hợp lệ dưới WM; tọa độ âm có kiểm allocation native trong lab riêng như mô tả dưới đây.

G2.11 đã qua [một vòng rút/cắm HDMI vật lý](benchmarks/physical-hotplug-2026-10-30/result.json): Dock fallback, mở lịch trên màn hình còn lại, giữ cấu hình monitor ưu tiên rồi quay về sau reconnect. XRandR báo connector connected nhưng output chưa active khi cắm lại; harness áp lại layout đã lưu để bật output và kiểm bước quay về. [Sáu vòng software output off/on](benchmarks/output-fallback-2026-10-30/result.json) bổ sung stress top/bottom, được ghi riêng với rút/cắm thật. Các ca opt-in khôi phục mode/refresh/position/primary và cấu hình test trong finally; không suy thành hỗ trợ mọi topology hoặc DPI.


`python3 tests/negative_origin_smoke.py` chạy Xvfb đã có sẵn (đổi executable bằng `DESKMORPH_XVFB`), RandR monitors, session/accessibility bus và profile riêng. Registry AT-SPI được khởi động tường minh để không phụ thuộc activation qua systemd desktop. [Ma trận origin âm](benchmarks/negative-origin-2026-10-30/result.json) đạt16 ca: launcher/audio/system/calendar × top/bottom × GTK scale1/2. Monitor left có physical work area[-1920,0,1920,1080]; Dock sau nội dung ổn định có kích thước298×52 hoặc596×104. Đo lại Dock trước từng popup, đối chiếu containment/căn giữa/anchor/gap và clamp dọc khi popup lớn. AT-SPI extents ở GDK logical nên đổi sang physical bằng scale; native rectangles lấy từ X11 theo PID/XID. Mở bằng AT-SPI và đóng bằng Escape qua XTest chỉ trên DISPLAY riêng. Không thay topology/input host; audit sau chạy không còn helper có marker lab.

Đây là **kiểm native allocation trên topology ảo**, chưa phải kiểm pixel hiển thị: monitor âm nằm ngoài drawable root của Xvfb, không có window manager. Không suy thành layout âm trên GNOME WM, thao tác chuột thật, fractional scaling hay mixed DPI. Các lỗi harness trước đó (toggle launcher, đơn vị AT-SPI, allocation khởi tạo và accessible document bị thay lúc startup) được giữ trong báo cáo chẩn đoán; lượt cuối chờ nội dung và20 mẫu ổn định trước đo. Không dùng `GDK_DPI_SCALE` text scaling làm bằng chứng fractional125/150%.


Khảo sát [Mutter DisplayConfig hiện tại](benchmarks/dpi-capabilities-2026-10-30/result.json) chỉ đọc ghi nhận renderer=xrandr, layout-mode=2, global-scale-required=true, cả HDMI/eDP chỉ công bố scale1/2 khi experimental-features=[]; không coi topology này là mixed DPI. Khảo sát này là baseline lịch sử; feature `x11-randr-fractional-scaling` về sau đã được bật tạm và kiểm thật với48ca fractional/mixed, rồi khôi phục features/layout. Xem bản ghi cuối để tránh hiểu khảo sát ban đầu là trạng thái acceptance hiện tại. Không suy từ keyword thành hỗ trợ hoạt động hoặc từ text scaling thành fractional proof.


Nhánh opt-in `DESKMORPH_CONTEXT_DESCRIPTION_LAB=1` bổ sung pin fixture có command không tồn tại trong private root, mở menu bằng Shift+F10 trên private DISPLAY rồi kiểm accessible description/focus sau lỗi qua AT-SPI. [Lượt4 ca](benchmarks/context-description-lab-2026-10-30/result.json) dùng vi/scale1 và en/scale2, top/bottom;16 popup placement cùng lượt qua. Đây là kiểm bổ sung G5.9 trên binary thật, không tăng phạm vi chứng nhận DPI/pixel/WM.


[Preflight khôi phục Mutter](benchmarks/dpi-restore-preflight-2026-10-30/result.json) bổ sung `tests/mutter_scaling_probe.py --verify-restore --output /tmp/mutter-restore.json`. Lệnh chỉ đọc state/settings và gọi ApplyMonitorsConfig với **method0/VERIFY**, không áp cấu hình hoặc bật feature. Lượt đầu server từ chối “Can't set layout mode”; payload nay chỉ gửi layout-mode khi server công bố supports-changing-layout-mode, còn fixed layout phải khớp baseline. Lượt sửa được Mutter xác nhận hợp lệ; features, user-value state, topology và capabilities giữ nguyên.

Probe lưu backup features/user value (phân biệt unset với explicit[]) và active mode/refresh/position/scale/transform/primary cùng underscanning nếu có, trước mutation. Nhánh `--trial-fractional-feature` khôi phục user value trong finally; nếu topology còn lệch mới gọi TEMPORARY/method1 bằng serial mới, không dùng persistent/method2. Read-only survey không tự áp lại một bố trí do người dùng/ngoại cảnh thay đổi; connected connector set khác baseline thì dừng fallback. Mọi lỗi restore vẫn ghi báo cáo. Sáu fault-injection tests kiểm các ranh giới này; không thay acceptance host.

**Cập nhật acceptance:** feature trial, TEMPORARY apply và48ca125/150%/mixed đã chạy host; [system200%12/12](benchmarks/system-output200-regression-2026-10-30/result.json) cũng đạt và restore exact. Bốn tổ hợp HDMI200% ngoài system đang chờ khoảng desktop rảnh mới. SIGINT/SIGTERM thường đi qua finally; không bảo đảm khôi phục sau SIGKILL/mất điện/lỗi display service. Không đánh dấu G2.10 hoặc coi preflight là DPI test đạt.


## Giới hạn tọa độ âm được Mutter xác nhận

[VERIFY30/10/2026](benchmarks/negative-origin-mutter-verify-2026-10-30/result.json) dùng đúng saved topology/modes/refresh/primary/scale. Baseline được method0 chấp nhận; bản sao chỉ dịch cả hai logical monitors1920px sang trái để giữ adjacency nhưng tạo origin−1920 bị từ chối: `Invalid logical monitor position (-1920, 0)`. Cả hai lời gọi đều VERIFY/method0; không method1/2, không đổi feature hoặc input. Readback topology/capabilities và user value đều giữ nguyên.

Đây chứng minh candidate âm đó không hợp lệ trên Mutter/xrandr hiện tại, bổ sung bằng chứng phần mềm thay cho suy luận từ lượt XRandR bị normalize trước. Không suy mọi compositor đều cấm tọa độ âm; không suy lỗi placement của DeskMorph từ rejection của DisplayConfig. Để đáp ứng nguyên văn G2.10 vẫn cần môi trường native cho phép monitor âm nằm trong vùng drawable và có WM; synthetic RandR monitor ngoài root hoặc dịch mốc tọa độ trong báo cáo không thay thế điều kiện này. G2.10 chưa hoàn thành.
