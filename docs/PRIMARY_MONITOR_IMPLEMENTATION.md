# Chuyển giao và thực thi: màn hình chính

Ngày: 01/11/2026. Tham chiếu: [kế hoạch](PRIMARY_MONITOR_PLAN.md), [phân tích](PRIMARY_MONITOR_SYSTEM_ANALYSIS.md), [thiết kế](PRIMARY_MONITOR_SYSTEM_DESIGN.md).

## Phạm vi đã triển khai

Đợt này hoàn thiện adapter GNOME để đổi primary trực tiếp. Phạm vi công bố là GNOME/Mutter có `ApplyMonitorsConfigAllowed`; desktop khác vẫn chỉ đọc hoặc mở cài đặt hệ thống.

- Tab Studio → Màn hình / Displays, riêng với màn hình đặt Dock.
- Native GIO/DisplayConfig đọc logical/physical monitor, primary, vị trí, scale, mode, Hz và output đang tắt; mirror hiển thị một nhóm logical.
- Giữ serial, session bus GUID và service owner nội bộ; snapshot công khai có epoch/revision/sequence, không gửi serial thiết bị.
- Subscription MonitorsChanged/NameOwnerChanged, polling fallback 5 giây, gộp sự kiện ở vòng worker 150 ms; lỗi đọc xóa trạng thái cũ trên UI và phục hồi khi đọc lại thành công. Worker riêng tránh chặn GTK; dừng và unsubscribe khi thoát.
- Frontend subscribe trước read, bỏ response cũ và cleanup callback khi chuyển tab; lỗi dịch tại lúc hiển thị vi/en.
- Platform summary có cờ primary. Watcher Dock theo dõi primary tường minh bên cạnh geometry; display snapshot thay đổi topology/primary sau baseline mới invalidates popup và yêu cầu layout đọc lại màn hình từ GTK; snapshot đầu hoặc chỉ đổi serial/permission không đóng popup.
- Nút mở GNOME Display Settings qua GIO desktop entry, kiểm caller là Studio; không ghép shell command.
- Khi GNOME cho phép, capability mở thao tác đổi primary; command chỉ nhận từ cửa sổ Studio, kiểm revision, đọc lại snapshot, VERIFY rồi gửi persistent apply. Sau apply, kiểm lại service owner trước refresh.
- Native giữ lease 30 giây sau apply để chặn request DeskMorph trùng trong lúc GNOME xác nhận; lease này không thay thế deadline hay phục hồi compositor.
- Candidate giữ vị trí, scale, transform, mode ID, nhóm mirror, underscan và `layout-mode` khi compositor công bố nó có thể đổi. Không ghi `monitors.xml`, không lưu primary trong config DeskMorph.
- GNOME Shell sở hữu Keep/Revert và timeout. Studio chỉ báo đang chờ GNOME, không suy active preview là persistence đã xác nhận.

Không thêm primary vào JSON config, import/export hoặc preset; không sửa monitors.xml và không tự đổi màn hình lúc startup.

## Kết quả spike và quyết định policy

Lab GNOME headless riêng (log tạo ngoài repository) dùng bus, runtime, HOME và hai màn hình ảo riêng:

1. VERIFY cấu hình chỉ đổi primary đạt.
2. TEMPORARY đổi primary đạt, giữ topology/mode/Hz/scale/transform trong snapshot test.
3. Request PERSISTENT đi vào preview active đúng target.
4. GNOME Shell explicit Revert khôi phục baseline; explicit Keep giữ target.
5. `monitors.xml` xuất hiện sau Keep; primary đã Giữ vẫn tồn tại sau khi GNOME Shell cô lập khởi động lại với cùng HOME/config; mọi process lab đã thoát.

Đối chiếu resource `windowManager.js` của GNOME Shell đang cài cho thấy hộp xác nhận gọi `complete_display_change(true/false)` nội bộ Shell. Public DisplayConfig đã khảo sát không có method/signal kết quả xác nhận tương đương. Vì vậy không dùng điều kiện “primary vẫn active sau vài giây” để suy ra đã lưu bền.

Chưa kiểm persistence qua logout/login, SIGKILL applying client, hotplug/mixed DPI hoặc end-to-end native product trong lab. `canPersist` nghĩa là có thể yêu cầu persistent mode; lab mới chỉ chứng minh qua Shell restart cùng phiên/config, không phải persistence qua đăng nhập mới.

Không có agent, journal hay khóa mutation runtime riêng: an toàn xác nhận/phục hồi trong phạm vi này do GNOME compositor sở hữu. Các hạng mục hardening còn lại không được đánh dấu hoàn thành.

## Kiểm thử và bằng chứng

- `npm run build` đạt; `npm test`: 59/59.
- `cargo test --offline --manifest-path src-tauri/Cargo.toml --target-dir src-tauri/target/agent --lib`: 96 đạt, 5 native opt-in bỏ qua.
- Sáu test Rust mới: primary/mode/privacy, primary thay đổi không đổi geometry, mirror/inactive, response lỗi, service owner/permission và snapshot ban đầu/metadata không được đóng popup.
- Test frontend kiểm request `set_primary_monitor` chỉ với target secondary/capability hợp lệ và revision hiện hành.
- GUI host smoke đã được đổi để không click nút mutation và chỉ kiểm action có sẵn. Hai lượt ở đây dừng trước khi accessibility tree công bố tab Màn hình; không tính là bằng chứng UI native mới.
- Ca end-to-end GNOME/X11 thật ngày 01/11/2026: Studio DeskMorph gửi `eDP-1-1` → `HDMI-0`; GNOME xác nhận Keep. Đọc DisplayConfig và `xrandr` sau Keep cùng xác nhận HDMI primary, với vị trí `(1920,0)/(0,0)`, scale/transform `1/0`, HDMI `1920x1080@60` và laptop `1920x1080@144` không đổi. Lượt kế tiếp yêu cầu HDMI → laptop rồi chọn Revert; API xác nhận trả đúng baseline lượt hai là HDMI primary. Đây là kiểm app → GNOME dialog → API thật, không dùng để suy hotplug, logout/login, mixed DPI hay accessibility đã đạt.
- Các lượt GUI đầu dừng do harness tìm paragraph bằng accessible name; sau đó gọi nhầm method Python Text. Đã sửa sang Atspi.Text.get_text. Các lượt lỗi không tính là đạt.
- Lượt spike đầu kiểm cleanup quá sớm nên ghi ownedProcessesExited=false; runner đã bổ sung chờ/kiểm cleanup, lượt sau đạt. Không dùng lượt đầu để chứng nhận cleanup.

GUI test không gửi chuột/phím host, không thay topology và không mở Settings thật. Chưa kiểm bàn phím/Orca hay mutation trên phần cứng thật. Fixture chỉ xác minh luồng GIO/open command, không thay kiểm Settings GNOME thực tế.
- Hồi quy hai Dock trên bản release: [32 popup vi/en, chuyển mode màn hình, tắt/bật và restart](benchmarks/primary-monitor-dock-regression-2026-10-31.json) đạt; không thay topology host.

Một lượt hồi quy cuối dừng vì popup không còn hiển thị. Review phát hiện reader có thể đóng popup khi snapshot đầu đến trễ hoặc serial/metadata đổi; đã giới hạn reconcile theo thay đổi logical/physical sau baseline và thêm regression test. Kết quả chạy lại được ghi ở benchmark cuối, không dùng lượt lỗi làm bằng chứng đạt.

## Cách dùng đợt này

1. Thoát DeskMorph hoàn toàn bằng nút Thoát trong Studio → Hệ thống, rồi chạy `src-tauri/target/release/deskmorph`. Chỉ đóng cửa sổ Studio có thể giữ Dock và process cũ nên chưa nạp bản mới; không chạy kèm instance test cũ.
2. Studio → Màn hình: xem primary/secondary và thông số.
3. Chọn “Đặt làm màn hình chính” ở màn logical phụ.
4. Chọn Giữ thay đổi hoặc Hoàn tác trong hộp thoại GNOME. Nếu adapter không hỗ trợ, dùng nút mở cài đặt màn hình hệ thống.
5. Studio tự cập nhật theo desktop. Cấu hình Dock “Màn hình chính” theo primary desktop; màn cụ thể và tất cả giữ ý nghĩa riêng.

Lượt kiểm thực tế đã giữ HDMI là primary theo lựa chọn Keep của người dùng. Không tự restart/kill instance thật hoặc tự thay primary ngoài thao tác Studio do người dùng xác nhận.

## Công việc còn lại theo thứ tự

- [ ] Trong lab riêng: kiểm Giữ/Hoàn tác thủ công, SIGKILL applying client, kết quả xác nhận và persistence qua phiên desktop; xây observer có bằng chứng, không suy từ active state.
- [ ] Chốt AdapterPolicy đúng phiên GNOME/backend; nếu cần API ngoài public DisplayConfig, đánh giá rõ phụ thuộc mới và cập nhật thiết kế trước.
- [ ] Native transaction state machine, recovery agent, runtime journal, session lock xuyên profile, caller/ownership và request idempotency.
- [ ] IPC preview/confirm/revert, dialog theo confirmation owner và deadline native, xử lý unknown/conflict/persist lỗi.
- [ ] Dock reconcile theo logical snapshot đồng bộ Tauri: mapping mirror, retry giới hạn, generation resize; kiểm không có Dock/input region dư khi primary đổi.
- [ ] Test crash/hotplug/external Settings/mixed DPI, bàn phím/Orca, persistence qua login và ma trận hỗ trợ; chỉ mở rộng capability khi môi trường tương ứng đạt.
- [ ] Handover bản mutation với bằng chứng và hướng dẫn recovery; cập nhật checklist kế hoạch theo từng ca thật.

Đã đánh dấu P3.1 (panel màn hình) hoàn thành theo bằng chứng GUI. Đợt này không đánh dấu toàn bộ P1–P6 hoặc G2.10 cũ là hoàn thành. Không có thay đổi topology trên desktop người dùng.
