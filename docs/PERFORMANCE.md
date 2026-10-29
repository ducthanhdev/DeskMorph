# Đường cơ sở hiệu năng DeskMorph

Ngày 29/10/2026, source production `47fa999`. [Dữ liệu gốc và từng mẫu](benchmarks/x11-debug-baseline-2026-10-29.json) giữ cấu hình, môi trường và SHA-256 binary. Đây là đường cơ sở debug lịch sử; kết quả so khớp và ngân sách G9.7 nằm ở phần sau.

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

Phần G9.7 bên dưới bổ sung so khớp build mode, cấu hình và số cửa sổ, cùng các trạng thái release, Studio ẩn, auto-hide, popup và nhiều cửa sổ.

## G9.7 — So sánh và ngân sách tham chiếu (29/10/2026)

[Ma trận 28 lượt và mẫu gốc](benchmarks/x11-performance-matrix-2026-10-29.json) so binary trước `e6fd7b0` với thay đổi snapshot cửa sổ. Build debug/release dùng custom-protocol và cùng cấu hình. Không có build hoặc GUI test khác chạy đồng thời. Hai lượt Studio không trace cho mỗi binary; trace riêng cho từng binary. Các trạng thái khác có một lượt không trace và một lượt trace cho mỗi build sau thay đổi. Observer AT-SPI/xprop nằm ngoài cây app, kiểm tra trạng thái map mỗi mẫu; áp dụng giống nhau trước/sau. Không suy khác biệt CPU lịch sử `47fa999` thành regression: baseline đó có 6 clients, còn lượt so khớp có 9 và preview mới có thêm consumer.

| Studio, 9 clients | CPU trung bình (% một lõi) | PSS median từng lượt (MiB) | xprop / lượt trace 15s |
| --- | ---: | --- | ---: |
| Debug trước | 17,038 | 421,49 / 422,55 | 198 |
| Debug sau | 15,161 | 420,76 / 421,35 | 99 |
| Release trước | 15,167 | 410,86 / 413,17 | 198 |
| Release sau | 15,646 | 411,67 / 413,40 | 99 |

Snapshot native dùng chung trong tối đa 1 giây giảm 18 lần quét xuống 9; vẫn có 18 IPC từ hai WebView. Mỗi lượt quét có hai root query và một detail query/client. Số exec xprop giảm 50% trong cả hai build. Debug CPU giảm khoảng 11%; release tăng khoảng 3% ở trung bình hai lượt, nhưng từng lượt dao động mạnh, chưa đủ kết luận regression hoặc cải thiện CPU release. PSS gần như không đổi. Không dùng CPU/startup có strace để đặt ngân sách. Actions vẫn xác minh target trên adapter thật và xóa cache sau thao tác; lỗi refresh xóa dữ liệu cũ, không cache lỗi; capability refresh xóa cache trước broadcast.

| Trạng thái sau thay đổi | Clients | CPU debug/release (% một lõi) | PSS peak debug/release (MiB) | xprop debug/release / 15s |
| --- | ---: | --- | --- | --- |
| Dock hiện, Studio ẩn | 8 | 8,235 / 6,760 | 421,76 / 411,30 | 90 / 90 |
| Cả hai ẩn, auto-hide bật | 8 | 1,592 / 1,261 | 416,64 / 405,53 | 0 / 0 |
| Popup hệ thống + Dock, Studio tab ứng dụng | 10 | 11,315 / 8,808 | 445,78 / 433,19 | 120 / 120 |
| Studio + Dock + 12 cửa sổ GTK fixture | 21 | 18,156 / 14,982 | 428,58 / 419,92 | 207 / 184 |

Fixture GTK nằm ngoài cây CPU của app. Khi cả hai UI ẩn, debug chỉ còn 58 IPC kiểm tra con trỏ/15,1s, không spawn process hay poll cửa sổ/stats. Popup stats có 15 request nhưng 8 native samples; Studio trước/sau có 16 request và 8 native samples. Trace many release có 8 vòng so với debug 9 do pha timer ở ranh giới khoảng đo.

[Ngân sách](benchmarks/performance-budgets.json) là cổng phát hiện regression cho môi trường này, không phải cam kết mọi máy. CPU giới hạn lần lượt Studio/Dock/ẩn/popup/many là 22/12/3/16/25% một lõi: chừa khoảng 30–45% trên mức quan sát cao nhất, rộng hơn cho trạng thái ẩn có mức tuyệt đối thấp. PSS peak lần lượt 480/470/460/500/480 MiB, khoảng 10–14% dự phòng. Startup debug 3s/release 2,5s, so với mức không trace cao nhất sau thay đổi 1,606/1,530s; chỉ là first accessible button trên desktop đã nóng. Một lượt 15s chỉ cho ngân sách ban đầu; cần nhiều lượt dài hơn khi điều tra dao động hoặc thay đổi môi trường.

Cổng polling: tối đa floor(duration/1,5s)+1 vòng native; detail query = clients × vòng, tổng xprop = (clients+2) × vòng. Khi ẩn phải bằng 0, không stats/window IPC, pointer IPC tối đa duration/0,25s+2. Cổng so khớp yêu cầu giảm ít nhất 35% xprop/s so trước; số đo hiện tại khoảng 50%. Validator từ chối thiếu lượt không trace, config/client khác nhau, vượt tải clients đã hiệu chuẩn, cleanup chưa xong và query ngoài công thức. Có test âm cho missing/CPU/client/spawn/hidden/cleanup.

```sh
/usr/bin/python3 tests/desktop_smoke.py --performance-matrix
/usr/bin/python3 tests/performance_budget.py /tmp/deskmorph-desktop-test/performance-matrix-result.json docs/benchmarks/performance-budgets.json
/usr/bin/python3 -m unittest discover -s tests -p 'performance_*test.py'
```

Matrix cần bốn binary trong đường dẫn ghi ở `tests/performance_matrix.py`; hash cụ thể có trong dữ liệu. Resume bằng `DESKMORPH_PERFORMANCE_RESUME=<thư mục kết quả>`; harness kiểm tra hash trước khi tái sử dụng. Lượt đầu gặp AT-SPI null node sau 17 kết quả; đã dọn trace group và nối 11 lượt còn lại, giữ nguyên hash/config/client count. Harness mới bỏ node null, lưu config trước chạy và đảm bảo phục hồi trong finally. Lượt đầu chưa lưu byte config gốc; chỉ xác nhận khôi phục byte của profile test lúc bắt đầu resume, không tuyên bố khôi phục được byte trước lần lỗi. Không tác động profile người dùng. Native Wayland, cold start, GPU RAM, sleep/leak dài hạn và độ tin cậy thống kê vẫn ngoài phạm vi số đo này.
