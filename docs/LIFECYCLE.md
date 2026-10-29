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

Frontend tests kiểm tra request pending khi visibility đổi, StrictMode replacement, cleanup/ẩn, retry sau lỗi, listener đăng ký muộn, query visibility cũ và query/exception sau cleanup. Kiểm thử native bổ sung việc tắt widget, tự ẩn/hiện lại bằng cạnh, chia sẻ mẫu CPU/RAM, bốn lần mount/hide popup và Studio ẩn/hiện. Các bài audio/media/popup/auto-hide kiểm tra đường tương tác vẫn hoạt động. Callback thao tác, launcher và rAF có thêm lifetime riêng như phần audit dưới đây; G7.7/G9.8 vẫn cần kiểm thử service restart và vòng đời dài.


## Audit callback và cleanup G1.7

| Nguồn công việc | Cơ chế cleanup / bỏ kết quả cũ |
| --- | --- |
| config/store | Một connection cho các subscriber của mỗi webview; disposed guard, unlisten nếu đăng ký xong muộn, kiểm tra revision. Mutation cấu hình đã gửi vẫn hoàn tất và phát snapshot authoritative dù view nguồn đã đóng. |
| useInstalledApps / usePlatform | disposed guard cho kết quả/query/event; loading + pending gom sự kiện; unlisten muộn được dọn. Cache/monitor native được quản lý riêng. |
| polling / useClock / useSystemStatus / useLiveWindows | Một timer/request slot qua các lần thay effect, AbortSignal cho consumer, bỏ listener visibilitychange; native IPC đang chạy được đợi thay vì giả hủy. |
| usePopupActive / CalendarFlyout | Subscribe trước query; version event bảo vệ query cũ, disposed guard và unlisten; clock calendar dừng khi popup ẩn. |
| DockContextMenuStandalone / DockTooltip | Listener data được gỡ; nếu đăng ký xong sau cleanup thì unlisten ngay. Escape thuộc native coordinator với generation, không có key listener DOM trùng trong context/lịch. |
| AudioPopup / MediaControls | Listener arrays gỡ khi unmount; visible/generation guard; snapshot đầu sau subscribe; debounce/queued volume chưa gửi bị xóa khi ẩn; refresh không gửi thêm IPC từ consumer đã ẩn. |
| WallpaperSettings / SystemSettings | Scan cleanup gửi cancel bằng requestId và bỏ callback disposed; thumbnail bỏ kết quả cũ; review import dùng request counter tăng khi cleanup; query autostart có disposed guard. Lệnh apply/config do người dùng gửi được phép hoàn tất ở backend. |
| Taskbar / useDockTooltip | Hide/preview/launch/width/tooltip timers được clear; tooltip revision loại update cũ. MatchMedia, key/blur/pointer/scroll listener và ResizeObservers được remove/disconnect; magnification rAF bị cancel. |
| Launcher / WindowList / ContextActions / callback Taskbar | AsyncLifetime cấp AbortSignal theo lần setup effect; cleanup/StrictMode replay abort token cũ. Callback không đóng popup hoặc cập nhật lỗi/focus sau khi token đã bị hủy. Hide truyền opening generation, không đóng popup thay thế. |
| Native focus sau popup mapping | Kiểm tra generation và native focus, chỉ focus nội dung; không present toplevel trễ. Shortcut dùng timestamp key event. Debug timing test ghi tại [POPUP_FOCUS.md](POPUP_FOCUS.md). |
| Focus sau move pin | rAF được AsyncLifetime sở hữu và cancel khi cleanup; kết quả mutate muộn không xếp rAF mới từ token cũ. Trước focus kiểm tra document visible và Dock không auto-hidden. |

`AsyncLifetime` hủy việc quan sát kết quả và các frame chưa chạy; không hủy launch/activate/close/config đã được native chấp nhận. Launcher kiểm tra generation active trước khi nhận thao tác, truyền generation vào hide, bắt lỗi nút Studio; không mở Studio từ completion đã bị hủy hoặc hide của generation cũ. Context menu giữ mở nếu mutation trả false.

`asyncLifetime.test.mjs` dùng Promise bị giữ lại để thử completion sau StrictMode cleanup, popup thế hệ mới, giá trị false, consumer đã disposed và rAF đang đợi. Độ trễ được tạo ở unit test, không tuyên bố đã inject delay vào GIO/IPC native. Native launcher/multi-instance/reorder/restart/window-list và chuỗi popup kiểm tra tích hợp trên GNOME/X11; vòng đời nhiều giờ, suspend và restart service vẫn thuộc G9.8/G7.7.
