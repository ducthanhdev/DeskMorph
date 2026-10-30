# Checklist phát hành DeskMorph 0.1.0

Ngày đánh giá: 30/10/2026. Quyết định: **Không phát hành** và không công bố artifact
này. Đây là quyết định có chủ ý sau kiểm thử; các cổng còn thiếu phải hoàn thành
trước khi tạo release candidate mới.

| Hạng mục | Kết quả | Bằng chứng / giới hạn |
| --- | --- | --- |
| Version và nền build | `0.1.0`, amd64, Ubuntu/Pop!_OS 24.04 | [manifest](benchmarks/deb-artifact-manifest-2026-10-29.json); artifact được build trước các thay đổi cuối, nên không gọi là reproducible release |
| Artifact | Có `.deb` development, SHA256 `f138ca13d82a29ff9ced3b4b9fe3194b60cd03ce43cfac2b4c508035250a6b15`, 2,549,260 bytes | [dpkg report](benchmarks/deb-package-2026-10-29.json); không commit binary |
| Build và package smoke | Pass | `npm run build`, cargo custom-protocol và `verify:deb`; dependency status mượn host trong bwrap |
| GUI packaged / HOME mới | Pass trong lab | [clean-account report](benchmarks/deb-clean-account-2026-10-29/launcher.json); không thay thế cài apt trên account thật |
| GNOME X11 core flow | Pass trong môi trường tham chiếu | Ma trận [PLATFORM_SUPPORT_MATRIX](PLATFORM_SUPPORT_MATRIX.md) |
| GNOME Wayland/COSMIC/KDE scope | Có giới hạn rõ | Wayland/COSMIC wallpaper-only experimental; KDE unsupported vì thiếu pixel/readback |
| Accessibility toàn ứng dụng | Chưa đạt | [G5.9 còn mở](REMAINING_ACCEPTANCE.md): system Enter và chooser route; audio native controls/keys và Orca menu vi/en đã đạt |
| Physical HDMI hotplug / fallback | Pass trên GNOME X11 tham chiếu | [Physical hotplug](benchmarks/physical-hotplug-2026-10-30/result.json), G2.11; output được bật lại bằng saved XRandR layout sau reconnect |
| Scheduler qua sleep thật | Pass trên GNOME X11 tham chiếu | [Suspend 138,922s](benchmarks/scheduler-suspend-2026-10-30/result.json), G6.7; operator đánh thức và mở khóa |
| Lifecycle dài | Pass trong phạm vi tham chiếu | [Soak122 vòng/1808,461s, Quit/survivors](benchmarks/popup-soak-2026-10-30/result.json), kết hợp restart/suspend/hotplug ghi trong PROGRESS; không chứng nhận zero leaks/uptime vô hạn |
| DPI | Chưa đạt | [48/48 fractional/mixed cases](benchmarks/dpi-native-full-matrix-2026-10-30/result.json) đã đạt top/bottom, bốn popup, hai monitor và restore exact; [Output100%16/16,200%10pass/1fail/5not-run](benchmarks/dpi-output-integer-trial-2026-10-30/result.json); G2.10 còn200% system stability và negative topology dưới WM. Baseline đã recovery exact; guard mới chỉ fault-test. Origin âm có16 ca native allocation trong Xvfb riêng, chưa kiểm pixel/WM |
| Cài account/máy sạch, autostart login, migration tiền nhiệm | Pass trong isolated lab | dpkg root + HOME mới + GUI packaged + autostart G1.13 + predecessor khác payload; không chứng nhận apt trên máy vật lý khác |
| Ký artifact / publish | Không thực hiện | Quyết định no-go; không upload hoặc công bố |

Artifact trên chỉ là bản development để tái kiểm trong lab. Không dùng checklist
này làm lời chứng nhận hỗ trợ distro/desktop ngoài phạm vi ma trận.
