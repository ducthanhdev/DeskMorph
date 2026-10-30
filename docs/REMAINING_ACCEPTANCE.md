# Kiểm toán phạm vi còn mở

Ngày 30/10/2026. Đối chiếu yêu cầu gốc trong IMPLEMENTATION_PLAN.md; tổng98/99; G5.9 đã chốt trong môi trường tham chiếu.
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

## G5.9 — Đã chốt các yêu cầu accessibility tham chiếu

| Yêu cầu | Bằng chứng hiện tại | Cần hoàn tất |
| --- | --- | --- |
| Nhãn, Tab hai chiều và disabled | [Studio năm trang vi/en](benchmarks/studio-focus-scroll-2026-10-30/result.json), [popup](benchmarks/popup-keyboard-2026-10-29.json), [Dock](benchmarks/dock-keyboard-2026-10-29.json) | [Chooser4/4 vi/en](benchmarks/chooser-keyboard-private-2026-10-30/result.json) đã đạt Tab/Home/Tab→Open, reverse/forward và Enter; không seed focus/selection trong chooser |
| Focus-visible |406 control samples Studio, select và wallpaper focus pixel; các native keyboard suites cho Dock/popup/lịch | Giữ các giới hạn trạng thái động đã nêu trong ACCESSIBILITY.md; không suy mọi cạnh outline từ số pixel |
| Contrast |209 computed fixtures, native Studio checkbox/range/select và black/white wallpaper focus | [Audio native20 captures](benchmarks/audio-native-controls-2026-10-30/result.json) đã đạt; radio/range/checkbox checked/unchecked và focus được đo riêng, không suy từ Studio |
| Các thao tác chính bằng bàn phím | Launcher, cửa sổ/context, preset, accent, import/reset/undo, wallpaper, lịch và media có native keys; audio mute có Space sau reconnect | [Audio output selection/volume/mute vi/en](benchmarks/audio-native-controls-2026-10-30/result.json) đã đạt với keys/readback private PipeWire/Pulse/WirePlumber; [System Downloads/Trash/monitor native Enter vi/en](benchmarks/system-keyboard-private-2026-10-30/result.json) đã đạt4cases/32Enter, gồm failure/retry/missing capability. [Chooser4/4](benchmarks/chooser-keyboard-private-2026-10-30/result.json) đã chọn file bằng Home, Tab→Open/Enter, review/Cancel trả focus và không đổi config |
| Trình đọc màn hình bổ sung | [Orca menu vi/en đạt](benchmarks/orca-current-regression-2026-10-30/result.json), launch error/warning đều được đọc | Không mở thêm yêu cầu human listening hoặc mọi cấu hình Orca: không nằm trong G5.9. Giữ giới hạn bypass-navigation rõ ràng |

G5.9 đã chốt bằng tổ hợp bằng chứng trong bảng và [chooser4/4](benchmarks/chooser-keyboard-private-2026-10-30/result.json). Chooser dùng thư mục cwd fixture/private GTK startup-mode=cwd; không chứng nhận mọi đường duyệt filesystem hoặc inline filename completion. Giữ giới hạn Orca bypass-navigation và phạm vi control/state của các báo cáo; không mở rộng thành chứng nhận WCAG hay mọi reader/theme.

Chỉ G2.10 còn mở: bốn tổ hợp HDMI200% ngoài system và topology âm drawable hợp lệ dưới WM. Không dùng các diagnostic chooser thất bại để suy lỗi sản phẩm hoặc làm bằng chứng đạt.

Runner đã chuẩn bị chọn đúng bốn ca: `--run --layouts 200 --only-case HDMI-0/top/calendar HDMI-0/bottom/launcher HDMI-0/bottom/audio HDMI-0/bottom/calendar`. 11 fault/orchestration tests đạt; chưa chạy host khi chưa có khoảng desktop rảnh mới.
