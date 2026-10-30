# Kiểm toán hai mục còn mở

Ngày 30/10/2026. Đối chiếu yêu cầu gốc trong IMPLEMENTATION_PLAN.md; tổng vẫn97/99.
Tài liệu này chỉ xác định bằng chứng còn thiếu, không thêm yêu cầu hỗ trợ desktop khác
hoặc chứng nhận WCAG/Orca toàn diện vào kế hoạch.

## G2.10 — Hình học và DPI

| Yêu cầu | Bằng chứng hiện tại | Kết luận |
| --- | --- | --- |
| Dock trên/dưới,100% | [16/16 output-scale cases](benchmarks/dpi-output-integer-trial-2026-10-30/result.json) | Đạt trong GNOME X11 tham chiếu |
|125%,150%,mixed DPI, bốn popup/hai monitor | [48/48](benchmarks/dpi-native-full-matrix-2026-10-30/result.json) | Đạt native allocation; không chứng nhận độ sắc nét hoặc click mapping |
|200% | Integer trial10 pass; [system mới12/12](benchmarks/system-output200-regression-2026-10-30/result.json) trên hai monitor/top-bottom/3repeats | Còn HDMI/top/calendar và HDMI/bottom/launcher,audio,calendar; failure system cũ chưa tái hiện, chưa xác định root cause |
| Đổi độ phân giải | [1680×1050 và restore](benchmarks/geometry-multimonitor-2026-10-30/result.json) | Đạt; không cần lặp vì chưa có thay đổi sản phẩm mới |
| Monitor bên trái có tọa độ âm | [16 allocations trong Xvfb](benchmarks/negative-origin-2026-10-30/result.json); Mutter/NVIDIA chuẩn hóa bố trí host về x=0 | Chưa chứng minh topology âm drawable dưới WM; không nâng synthetic monitor ngoài root thành màn hình thật |
| Khôi phục sau kiểm |48-ca restore exact; integer trial cần recovery bổ sung, sau đó baseline giữ nguyên | Guard cooldown/bounded retry qua14 fault/guard tests; [system200% host12/12](benchmarks/system-output200-regression-2026-10-30/result.json) restore exact, không cần reapply |

[4 ca system trên GNOME riêng](benchmarks/system-geometry-private-wm-2026-10-30/result.json)
qua scale1/2, top/bottom với màn hình drawable1920×1080. Phép đo cũ lấy anchor trước khi
Dock co chiều rộng gây một geometry mismatch trong lab. Worker mới chờ20 mẫu Dock ổn
định và kiểm Dock không đổi qua activation. Chưa dùng kết quả này để giải thích lỗi
popup không ổn định trên HDMI, vì lượt host đó không có trace dismiss.

## G5.9 — Các yêu cầu accessibility

| Yêu cầu | Bằng chứng hiện tại | Cần hoàn tất |
| --- | --- | --- |
| Nhãn, Tab hai chiều và disabled | [Studio năm trang vi/en](benchmarks/studio-focus-scroll-2026-10-30/result.json), [popup](benchmarks/popup-keyboard-2026-10-29.json), [Dock](benchmarks/dock-keyboard-2026-10-29.json) | Kiểm tuyến bàn phím của chooser đến Open; ca import hiện seed focus Open bằng AT-SPI |
| Focus-visible |406 control samples Studio, select và wallpaper focus pixel; các native keyboard suites cho Dock/popup/lịch | Giữ các giới hạn trạng thái động đã nêu trong ACCESSIBILITY.md; không suy mọi cạnh outline từ số pixel |
| Contrast |209 computed fixtures, native Studio checkbox/range/select và black/white wallpaper focus | [Audio native20 captures](benchmarks/audio-native-controls-2026-10-30/result.json) đã đạt; radio/range/checkbox checked/unchecked và focus được đo riêng, không suy từ Studio |
| Các thao tác chính bằng bàn phím | Launcher, cửa sổ/context, preset, accent, import/reset/undo, wallpaper, lịch và media có native keys; audio mute có Space sau reconnect | [Audio output selection/volume/mute vi/en](benchmarks/audio-native-controls-2026-10-30/result.json) đã đạt với keys/readback private PipeWire/Pulse/WirePlumber; [System Downloads/Trash/monitor native Enter vi/en](benchmarks/system-keyboard-private-2026-10-30/result.json) đã đạt4cases/32Enter, gồm failure/retry/missing capability. Còn tuyến chooser→Open trong dòng Tab order |
| Trình đọc màn hình bổ sung | [Orca menu vi/en đạt](benchmarks/orca-current-regression-2026-10-30/result.json), launch error/warning đều được đọc | Không mở thêm yêu cầu human listening hoặc mọi cấu hình Orca: không nằm trong G5.9. Giữ giới hạn bypass-navigation rõ ràng |

Các mục thiếu phía trên là kiểm tích hợp có thể thực hiện với fixture/private bus và
private audio. Không cần gửi lệnh đến ứng dụng hay thiết bị audio của người dùng.
Chỉ đánh dấu G5.9 khi các thao tác và control còn thiếu được kiểm, sửa nếu thất bại,
và bằng chứng được đối chiếu lại với bảng này.
