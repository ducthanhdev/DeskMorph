# Đường cơ sở hiệu năng DeskMorph

Ngày 29/10/2026, source production `47fa999`. [Dữ liệu gốc và từng mẫu](benchmarks/x11-debug-baseline-2026-10-29.json) giữ cấu hình, môi trường và SHA-256 binary. Đây là đường cơ sở debug để so sánh cùng điều kiện; G9.7 chưa hoàn tất.

Pop!_OS 24.04, GNOME 46/X11, GTK 3.24.41, WebKitGTK 2.52.6; i5-12450HX, 12 CPU logic; hai màn hình 1920×1080 scale 1. Studio và Dock hiện, apps/stats/audio/clock bật, auto-hide tắt, popup đóng. Desktop còn ứng dụng khác hoạt động; không đo cold-cache hay thời gian đăng nhập.

| Lượt không trace | Startup tới button AX (s) | CPU (% một lõi) | PSS median (MiB) | PSS peak (MiB) |
| --- | ---: | ---: | ---: | ---: |
| 1 | 1,250 | 10,246 | 368,32 | 376,99 |
| 2 | 1,246 | 9,379 | 370,13 | 377,99 |
| 3 | 1,345 | 9,520 | 367,10 | 373,62 |

Startup tính từ Popen đến lần AT-SPI thấy button đầu tiên, kiểm tra mỗi khoảng 200 ms; không coi đó là thời gian mọi dữ liệu tải xong. Sau khi chờ 3 giây, lấy 16 mẫu cách nhau khoảng 1 giây. CPU là trung bình trên khoảng đo 15 giây của cây tiến trình native/WebKit, tính cả CPU child đã reap. 100% tương ứng một lõi, không phải toàn bộ CPU máy. Các tiến trình ngắn bị reparent ra ngoài cây giữa hai mẫu có thể không được quy thuộc đầy đủ.

PSS chia phần trang dùng chung giữa các tiến trình, phù hợp hơn cộng RSS khi có nhiều WebKit process. Cộng RSS median trong ba lượt là 1.213,56–1.218,79 MiB và có đếm lặp trang chia sẻ; không diễn giải thành lượng RAM riêng app sử dụng. Bảy tiến trình được quan sát trong mỗi mẫu; PSS không bao gồm GPU memory.

Hai lần trace riêng đều ghi nhận 10 vòng `get_open_windows` biểu hiện bằng root `_NET_ACTIVE_WINDOW` query trong 15,03 giây, khoảng 0,664 vòng/giây. Với sáu managed clients, mỗi vòng gọi hai root query và sáu per-window query: tổng 80 exec `xprop`/15 giây. Không có execve unfinished/resumed trong các trace này. Đây là đếm truy vấn cửa sổ, chưa phải tổng mọi IPC/timer, CPU/RAM hook hay local clock timer. Không dùng CPU/startup khi trace để so với các lượt không trace.

Tái lập trên desktop X11 với profile test hiện có; không chạy đồng thời với các ca GUI khác:

```sh
npm run build
cargo build --offline --manifest-path src-tauri/Cargo.toml --target-dir src-tauri/target/agent --features custom-protocol
/usr/bin/python3 tests/desktop_smoke.py --performance-smoke
/usr/bin/python3 tests/desktop_smoke.py --performance-trace
```

Cần AT-SPI/GI, X11, `/proc` cùng quyền đọc `smaps_rollup`; trace cần `strace` có thể theo dõi child do chính nó tạo. Harness chỉ restart app nhận diện bằng profile `/tmp/deskmorph-desktop-test/config`, không tương tác instance dev. Config cần Dock/apps/stats bật và auto-hide tắt; script từ chối điều kiện khác thay vì âm thầm đổi cài đặt. Báo cáo mới nằm ở `/tmp/deskmorph-desktop-test/performance-{idle,trace}-result.json` và bản có PID để giữ từng lượt. Trace kết thúc bằng dọn app/tracer và mở lại app test không trace.

G9.7 sẽ so cùng build mode, cấu hình, số cửa sổ và cách lấy mẫu trước khi đặt ngân sách. Cần đo riêng release, Studio ẩn, auto-hide, popup đang mở và nhiều cửa sổ; điều tra CPU khoảng 9–10% một lõi và chi phí sinh xprop trước khi tuyên bố đã tối ưu.
