# Chuyển giao và thực thi: màn hình chính

Ngày: 31/10/2026. Tham chiếu: [kế hoạch](PRIMARY_MONITOR_PLAN.md), [phân tích](PRIMARY_MONITOR_SYSTEM_ANALYSIS.md), [thiết kế](PRIMARY_MONITOR_SYSTEM_DESIGN.md).

## Phạm vi đã triển khai

Đây là đợt triển khai read path và chuyển sang cài đặt hệ thống theo nhánh fallback đã quy định trong System Design §11. Chức năng đổi primary trực tiếp trong DeskMorph **chưa hoàn thành**; không công bố giai đoạn tổng thể đã xong.

- Tab Studio → Màn hình / Displays, riêng với màn hình đặt Dock.
- Native GIO/DisplayConfig đọc logical/physical monitor, primary, vị trí, scale, mode, Hz và output đang tắt; mirror hiển thị một nhóm logical.
- Giữ serial, session bus GUID và service owner nội bộ; snapshot công khai có epoch/revision/sequence, không gửi serial thiết bị.
- Subscription MonitorsChanged/NameOwnerChanged, polling fallback 5 giây, gộp sự kiện ở vòng worker 150 ms; lỗi đọc xóa trạng thái cũ trên UI và phục hồi khi đọc lại thành công. Worker riêng tránh chặn GTK; dừng và unsubscribe khi thoát.
- Frontend subscribe trước read, bỏ response cũ và cleanup callback khi chuyển tab; lỗi dịch tại lúc hiển thị vi/en.
- Platform summary có cờ primary. Watcher Dock theo dõi primary tường minh bên cạnh geometry; display snapshot thay đổi topology/primary sau baseline mới invalidates popup và yêu cầu layout đọc lại màn hình từ GTK; snapshot đầu hoặc chỉ đổi serial/permission không đóng popup.
- Nút mở GNOME Display Settings qua GIO desktop entry, kiểm caller là Studio; không ghép shell command.
- Capability canSetPrimary/canPersist/recoveryAvailable đều false, có lý do hiển thị; không đăng ký command apply/confirm/revert giả. Nút đặt primary bị vô hiệu hóa ở cả UI và do không có native mutation API.

Không thêm primary vào JSON config, import/export hoặc preset; không sửa monitors.xml và không tự đổi màn hình lúc startup.

## Kết quả spike và quyết định policy

[Spike GNOME headless](benchmarks/primary-monitor-policy-2026-10-31.json) dùng bus, runtime, HOME và hai màn hình ảo riêng:

1. VERIFY cấu hình chỉ đổi primary đạt.
2. TEMPORARY đổi primary đạt, giữ topology/mode/Hz/scale/transform trong snapshot test.
3. Request PERSISTENT đi vào preview active đúng target.
4. Không xác nhận: compositor tự trả về baseline trong giới hạn 27 giây.
5. Dọn các process lab đã được xác minh.

Đối chiếu resource `windowManager.js` của GNOME Shell đang cài cho thấy hộp xác nhận gọi `complete_display_change(true/false)` nội bộ Shell. Public DisplayConfig đã khảo sát không có method/signal kết quả xác nhận tương đương. Vì vậy không dùng điều kiện “primary vẫn active sau vài giây” để suy ra đã lưu bền.

Spike hiện **chưa** thử bấm Giữ, chưa xác nhận persist qua logout/login, chưa thử SIGKILL applying client/recovery agent. monitors.xml không tồn tại sau ca timeout trong lab; điều này không chứng minh GNOME không hỗ trợ persistence. Chưa đủ bằng chứng chọn một policy trong thiết kế, nên mutation tiếp tục bị chặn. Auto-revert của method PERSISTENT không được suy thành auto-revert của TEMPORARY.

Không có agent, journal hay khóa mutation runtime ở đợt này vì không bật mutation. Các thành phần đó vẫn là công việc còn lại, không đánh dấu hoàn thành nhờ fallback.

## Kiểm thử và bằng chứng

- `npm run build` đạt; `npm test`: 58/58.
- `cargo test --offline --manifest-path src-tauri/Cargo.toml --target-dir src-tauri/target/agent --lib`: 93 đạt, 5 native opt-in bỏ qua.
- Sáu test Rust mới: primary/mode/privacy, primary thay đổi không đổi geometry, mirror/inactive, response lỗi, service owner/permission và snapshot ban đầu/metadata không được đóng popup.
- Hai test frontend mới: ordering/error recovery/cleanup của hook, mirror và routing mở Settings không apply primary.
- [GUI native](benchmarks/primary-monitor-ui-2026-10-31.json): vi/en qua AT-SPI trên process/profile tạm, primary khớp GNOME, nút mutation disabled, refresh, mở fixture GIO thay cho Settings thật; host snapshot không đổi và process thử đã thoát.
- Các lượt GUI đầu dừng do harness tìm paragraph bằng accessible name; sau đó gọi nhầm method Python Text. Đã sửa sang Atspi.Text.get_text. Các lượt lỗi không tính là đạt.
- Lượt spike đầu kiểm cleanup quá sớm nên ghi ownedProcessesExited=false; runner đã bổ sung chờ/kiểm cleanup, lượt sau đạt. Không dùng lượt đầu để chứng nhận cleanup.

GUI test không gửi chuột/phím host, không thay topology và không mở Settings thật. Chưa kiểm bàn phím/Orca hay mutation trên phần cứng thật. Fixture chỉ xác minh luồng GIO/open command, không thay kiểm Settings GNOME thực tế.
- Hồi quy hai Dock trên bản release: [32 popup vi/en, chuyển mode màn hình, tắt/bật và restart](benchmarks/primary-monitor-dock-regression-2026-10-31.json) đạt; không thay topology host.

Một lượt hồi quy cuối dừng vì popup không còn hiển thị. Review phát hiện reader có thể đóng popup khi snapshot đầu đến trễ hoặc serial/metadata đổi; đã giới hạn reconcile theo thay đổi logical/physical sau baseline và thêm regression test. Kết quả chạy lại được ghi ở benchmark cuối, không dùng lượt lỗi làm bằng chứng đạt.

## Cách dùng đợt này

1. Thoát DeskMorph hoàn toàn bằng nút Thoát trong Studio → Hệ thống, rồi chạy `src-tauri/target/release/deskmorph`. Chỉ đóng cửa sổ Studio có thể giữ Dock và process cũ nên chưa nạp bản mới; không chạy kèm instance test cũ.
2. Studio → Màn hình: xem primary/secondary và thông số.
3. Chọn Mở cài đặt màn hình hệ thống.
4. Trong GNOME Settings → Displays, chọn màn cần đặt chính và dùng điều khiển primary của GNOME; áp dụng và xác nhận theo hộp thoại desktop.
5. Trở lại Studio hoặc tải lại. Cấu hình Dock “Màn hình chính” theo primary desktop; màn cụ thể và tất cả giữ ý nghĩa riêng.

Giữ ứng dụng đang dùng và cấu hình người dùng khi build; đợt này không tự restart/kill instance thật hoặc tự thay primary.

## Công việc còn lại theo thứ tự

- [ ] Trong lab riêng: kiểm Giữ/Hoàn tác thủ công, SIGKILL applying client, kết quả xác nhận và persistence qua phiên desktop; xây observer có bằng chứng, không suy từ active state.
- [ ] Chốt AdapterPolicy đúng phiên GNOME/backend; nếu cần API ngoài public DisplayConfig, đánh giá rõ phụ thuộc mới và cập nhật thiết kế trước.
- [ ] Native transaction state machine, recovery agent, runtime journal, session lock xuyên profile, caller/ownership và request idempotency.
- [ ] IPC preview/confirm/revert, dialog theo confirmation owner và deadline native, xử lý unknown/conflict/persist lỗi.
- [ ] Dock reconcile theo logical snapshot đồng bộ Tauri: mapping mirror, retry giới hạn, generation resize; kiểm không có Dock/input region dư khi primary đổi.
- [ ] Test crash/hotplug/external Settings/mixed DPI, bàn phím/Orca, persistence và ma trận hỗ trợ; chỉ bật capability cho môi trường đã đạt.
- [ ] Handover bản mutation với bằng chứng và hướng dẫn recovery; cập nhật checklist kế hoạch theo từng ca thật.

Đã đánh dấu P3.1 (panel màn hình) hoàn thành theo bằng chứng GUI. Đợt này không đánh dấu toàn bộ P1–P6 hoặc G2.10 cũ là hoàn thành. Không có thay đổi topology trên desktop người dùng.
