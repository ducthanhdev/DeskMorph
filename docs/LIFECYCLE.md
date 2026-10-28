# Polling và vòng đời giao diện

`startPolling` sở hữu một timer, một AbortController và listener visibilitychange. Mỗi hook giữ một Promise đang chạy qua các lần thay effect, kể cả React StrictMode: effect mới đợi IPC cũ kết thúc rồi mới gọi task mới. Cleanup hủy consumer/timer/listener; không tuyên bố hủy được lệnh native đã gửi. Hook nhận task mới nhất qua ref. Document ẩn dừng timer và khi hiện lại lấy mẫu ngay.

Dock còn phân biệt trạng thái tự ẩn 4 px với document ẩn. Khi tự ẩn, dừng danh sách cửa sổ, CPU/RAM, đồng hồ và battery/network widget; vòng kiểm tra con trỏ X11 250 ms tiếp tục để hiện Dock. Mỗi lần pointer được xác minh trong native Dock sẽ hủy timer DOM mouseleave còn sót. Khi hiện, các hook lấy lại dữ liệu ngay. Khi config.enabled tắt, cả vòng con trỏ cũng dừng. Preview trong Studio tuân theo document visibility và unmount khi rời tab.

Audio/media/system và danh sách cửa sổ dùng generation hiện hành qua `usePopupActive`. `watchPopupVisibility` đăng ký listener trước rồi query trạng thái, đếm phiên bản event để query cũ không ghi đè hide mới. Listener resolve sau cleanup tự unlisten; query/exception muộn không cập nhật consumer cũ. Audio/media đợi đăng ký stream xong mới lấy snapshot đầu tiên để không có khoảng trống giữa query và subscribe. Khi ẩn, bỏ kết quả/cập nhật UI, hủy debounce volume và hàng đợi chưa gửi; native command đã gửi vẫn có thể hoàn tất.

CPU/RAM dùng `SystemSampler` duy nhất ở backend dưới mutex, cache mẫu 2 giây. Nhiều view có thể gọi IPC cùng thời điểm nhưng không refresh sysinfo nhiều hơn mức này. Không dùng cache đó để suy rằng mọi loại IPC hay backend khác đều có một nguồn duy nhất.

Đo native bằng:

```sh
/usr/bin/python3 tests/desktop_smoke.py --polling-smoke
```

Harness chỉ khởi động profile test với `DESKMORPH_TRACE_COMMANDS=1`. Trong debug build, diagnostics ghi cặp start/end, PID, tên command cố định, ID, thời gian và độ trễ vào stderr. Không ghi arguments, tên/tiêu đề cửa sổ hay nội dung người dùng. Release build không bật logging này. Harness khôi phục config rồi restart app test bình thường để tắt logging, không tác động instance dev.

Bộ đếm bao phủ get_open_windows, get_system_stats, lần refresh sysinfo thật, get_system_status, dò con trỏ, get_current_wallpaper và trạng thái scheduler. Đây là các nguồn polling UI cần kiểm tra, không phải tổng mọi IPC, event subscription hoặc thread trong ứng dụng. Kết quả nằm ở `/tmp/deskmorph-desktop-test/polling-result.json`.

Frontend tests kiểm tra request pending khi visibility đổi, StrictMode replacement, cleanup/ẩn, retry sau lỗi, listener đăng ký muộn, query visibility cũ và query/exception sau cleanup. Kiểm thử native bổ sung việc tắt widget, tự ẩn/hiện lại bằng cạnh, chia sẻ mẫu CPU/RAM, bốn lần mount/hide popup và Studio ẩn/hiện. Các bài audio/media/popup/auto-hide kiểm tra đường tương tác vẫn hoạt động. G1.7 còn được rà soát riêng cho callback thao tác, launcher và rAF; G7.7/G9.8 vẫn cần kiểm thử service restart và vòng đời dài.
