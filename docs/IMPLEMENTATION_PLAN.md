# Kế hoạch phát triển DeskMorph

Ngày lập: 28/10/2026. Trạng thái: đang triển khai. Bằng chứng và phần chưa xác minh được ghi trong [PROGRESS.md](PROGRESS.md).

## 1. Mục tiêu và phạm vi

Xây dựng Dock tùy biến dùng hằng ngày: tìm ứng dụng → mở → ghim → sắp xếp → quản lý cửa sổ; bổ sung Studio, hình nền và tiện ích hệ thống theo từng mốc có thể phát hành.

Kế hoạch bao phủ toàn bộ danh sách công việc đã trao đổi. Không cam kết hỗ trợ mọi desktop Linux ngay trong bản đầu. Mốc đầu chọn một phiên X11 để kiểm thử; xác định chính xác distro, desktop, phiên bản và tỷ lệ hiển thị trong G0. Hỗ trợ Wayland được quyết định bằng thử nghiệm khả năng của compositor mục tiêu.

Hiện trạng từ source: React 19, TypeScript, Tauri 2, Rust; quản lý cửa sổ qua X11/xprop; đổi hình nền qua GNOME gsettings; cấu hình localStorage và events. Đã có code gom nhóm/popup và kiểm tra build, nhưng cần kiểm thử desktop thực tế. Không coi tính năng đã qua kiểm thử chỉ vì tài liệu cũ đánh dấu hoàn thành.

## 2. Quy ước thực hiện

- Mỗi ID dưới đây là một đầu việc có thể theo dõi độc lập. Ban đầu tất cả để trống.
- Trình tự: G0 → G1 → G2 → G3 → G4 → G5 → G6 → G7 → G8 → G9. Có thể phát hành sau G4 và G6 khi vượt cổng chất lượng tương ứng.
- Chỉ mở rộng kiểm thử khi thay đổi hoặc rủi ro yêu cầu; test tập trung vào hành vi và dữ liệu, không sao chép implementation.
- Giữ nguyên thay đổi có sẵn của người dùng; chia commit theo phạm vi khi được yêu cầu commit.
- Không thêm phụ thuộc trước khi xác định nhu cầu; thử nghiệm nhỏ với API hệ thống trước khi xây UI đầy đủ.
- Đầu việc hoàn thành khi có code, kiểm tra phù hợp, trạng thái lỗi rõ ràng và tài liệu cần thiết; các giới hạn phải ghi cụ thể.

## 3. G0 — Xác lập môi trường và đường cơ sở

Đầu vào: source hiện tại. Đầu ra: môi trường tham chiếu và danh sách lỗi tái hiện được.

- [x] G0.1 Ghi nhận distro, desktop/version, X11/Wayland, kiến trúc CPU, màn hình và scale của máy kiểm thử; phân biệt môi trường thực tế với môi trường dự kiến hỗ trợ.
- [x] G0.2 Chạy build frontend và cargo check; ghi cách khởi động Tauri, các công cụ như xprop/gsettings và phụ thuộc native cần có.
- [x] G0.3 Kiểm thử gom nhóm: 0/1/nhiều cửa sổ, pinned/unpinned, active, đổi tiêu đề, đóng từ bên ngoài, hộp thoại xác nhận đóng.
- [x] G0.4 Kiểm thử popup: Escape, bấm ngoài, chuyển focus, dock trên/dưới, bật/tắt tự ẩn, mở liên tiếp menu/lịch/danh sách.
- [x] G0.5 Lập bảng khả năng ban đầu theo desktop; hiển thị thiếu hỗ trợ rõ ràng, không suy diễn XWayland là hỗ trợ cửa sổ Wayland native.
- [x] G0.6 Ghi số liệu nền: thời gian mở app, số lượt polling, CPU/RAM lúc rảnh; dùng để so sánh tối ưu sau này.

Tiêu chí qua G0: có hướng dẫn tái hiện và kết quả thật; lỗi ảnh hưởng mất cấu hình, đóng sai cửa sổ hoặc không mở được Dock được ưu tiên trước tính năng mới.

## 4. G1 — Cấu hình, đồng bộ và vòng đời ứng dụng

Phụ thuộc G0. Module dự kiến: config/schema, config/store, hooks đồng bộ; backend persistence và lifecycle.

- [x] G1.1 Gom toàn bộ mặc định về một nguồn; loại các bản sao và các override làm mất lựa chọn enabled/autoHide đã lưu.
- [x] G1.2 Định nghĩa schema cấu hình có version, giá trị hợp lệ, giới hạn số và fallback cho trường thiếu/sai.
- [x] G1.3 Migration từ localStorage hiện tại sang cấu hình versioned; cân nhắc file JSON tại app config directory làm nguồn bền vững, localStorage chỉ dùng di trú/cache.
- [x] G1.4 Một luồng cập nhật authoritative: nhận patch → validate → persist → phát snapshot/revision; serialize cập nhật để tránh ghi đè thay đổi đồng thời.
- [x] G1.5 Đồng bộ Studio/Dock/popup khi ghim, bỏ ghim, đổi giao diện; cửa sổ mở sau nhận snapshot hiện tại và cập nhật không gây vòng lặp events.
- [x] G1.6 Lưu an toàn bằng file tạm và thay thế; cấu hình lỗi được bảo toàn để khôi phục, không âm thầm xóa tùy chỉnh.
- [x] G1.7 Dọn timer/listener và async callbacks; xử lý React StrictMode, tránh listener đăng ký xong sau unmount.
- [x] G1.8 Chặn polling chồng nhau; chia sẻ snapshot phù hợp; dừng polling UI khi ẩn nhưng vẫn giữ cơ chế cần thiết cho auto-hide và popup.
- [x] G1.9 Chuẩn hóa lỗi command: mã, thông điệp, ngữ cảnh; hiện lỗi mở app/đổi hình nền/lưu cấu hình, cho phép thử lại và không báo thành công giả.
- [x] G1.10 Sửa trạng thái enabled khi startup, thao tác toggle và restart; backend không tự hiện Dock ngược cấu hình.
- [x] G1.11 Xác định đóng Studio: giữ Dock theo lựa chọn, có đường mở lại Studio và nút thoát hẳn dễ tìm; không để tiến trình không thể điều khiển.
- [x] G1.12 Ngăn nhiều instance; lần mở tiếp theo chuyển tới instance hiện có và mở Studio theo hành vi đã chọn.
- [x] G1.13 Sửa autostart/desktop entry cho đường dẫn có khoảng trắng; dùng vị trí executable thực tế, báo lỗi ghi file, không dựa vào đường dẫn máy phát triển.

Tiêu chí: thay đổi từ bất kỳ cửa sổ nào phản ánh ở các cửa sổ khác; restart giữ đúng cấu hình; JSON lỗi không làm app crash; không xuất hiện polling/listener trùng sau mở/đóng nhiều lần. Test migration, validation và cập nhật cạnh tranh; kiểm tra startup/autostart thực tế trên môi trường tham chiếu.

## 5. G2 — Window backend, popup và nhiều màn hình

Phụ thuộc G1. Module dự kiến: platform/capabilities, window-manager/x11, popup coordinator, geometry.

- [x] G2.1 Phát hiện session và desktop; thay nhãn X11 hardcode bằng kết quả thực; capability mô tả enumerate/activate/close/workspaces/wallpaper.
- [x] G2.2 Tách X11 khỏi logic chung bằng interface list/activate/close; định nghĩa ID và lỗi nhất quán để bổ sung adapter sau.
- [x] G2.3 Kiểm tra xprop/X11 display và trạng thái exit; thông báo thiếu công cụ, không trả danh sách rỗng như thành công khi lệnh thất bại.
- [x] G2.4 Popup coordinator quản lý duy nhất một popup mở; đóng popup cũ trước khi mở mới; xử lý mở nhanh, focus loss và thread theo dõi click cũ.
- [x] G2.5 Hoàn thiện auto-hide: giữ hiện khi popup mở, timer ẩn được hủy đúng lúc, trigger cạnh màn hình đáng tin cậy, tắt Dock đóng popup liên quan.
- [x] G2.6 Danh sách cửa sổ cập nhật tiêu đề/active/thêm/bớt; giữ cửa sổ đang chờ xác nhận đóng; close không dùng force kill thay thế tự động.
- [x] G2.7 Điều hướng danh sách bằng mũi tên, Home/End, Enter, Escape; focus ban đầu và focus khi hàng biến mất hợp lý.
- [x] G2.8 Đóng bằng Escape/bấm ngoài có hành vi nhất quán; trả focus về nguồn mở khi phù hợp, không giành focus sau khi người dùng đã chọn app khác.
- [x] G2.9 Chuẩn hóa tọa độ logical/physical, monitor origin và work area; tính vị trí từ kích thước Dock thực, clamp popup vào màn hình.
- [ ] G2.10 Kiểm tra Dock trên/dưới, monitor bên trái có tọa độ âm, scale 100/125/150/200%, màn hình hỗn hợp DPI và đổi độ phân giải.
- [ ] G2.11 Chọn màn hình đặt Dock; xử lý rút/cắm màn hình và fallback về màn hình còn lại. Dock trên tất cả màn hình là phần mở rộng sau khi chế độ chọn một màn hình ổn định.
- [x] G2.12 Tránh hiển thị cửa sổ nội bộ DeskMorph trong danh sách app; active indicator phải chính xác với ID cửa sổ.

Tiêu chí: không bị cắt popup, không đóng nhầm, không popup mồ côi; danh sách và Dock cùng phản ánh trạng thái. Test thuần cho geometry/grouping, kiểm thử desktop cho focus/outside-click/DPI và hotplug nếu có thiết bị.

G0.5/G2.1/G2.3: [CAPABILITIES.md](CAPABILITIES.md) ghi ma trận ban đầu và bằng chứng. Capability cửa sổ đọc EWMH hiện tại, tách enumerate/activate/close, không suy từ DISPLAY/tool existence; action kiểm tra lại hỗ trợ. Fixture lỗi xprop và native startup PATH rỗng đã qua; hồi quy native focus/close/force-close đã qua trên desktop tham chiếu; danh sách động và bàn phím có thêm bằng chứng G0.3/G2.6/G2.7/G4.5 trong PROGRESS.md. Các desktop/DPI/hotplug còn thiếu vẫn ở mục chưa đánh dấu.

## 6. G3 — Danh mục ứng dụng, tìm kiếm và icon

Phụ thuộc G1–G2. Thử parser và launch desktop entry trước khi xây launcher UI.

- [x] G3.1 Quét XDG_DATA_HOME/applications, XDG_DATA_DIRS/applications và các đường export Flatpak/Snap khi cần; dùng desktop ID và thứ tự ưu tiên đúng, tránh trùng.
- [x] G3.2 Đọc Type, Name theo locale, GenericName, Keywords, Icon, Exec, TryExec, Terminal, Hidden, NoDisplay, OnlyShowIn, NotShowIn, StartupWMClass và Actions.
- [x] G3.3 Lọc mục ẩn/không phù hợp môi trường; xử lý override Hidden=true và file lỗi; một file lỗi không làm hỏng toàn bộ danh mục.
- [ ] G3.4 Launch theo desktop entry bằng cơ chế hệ thống phù hợp; xử lý field codes/Terminal/DBusActivatable, không ghép Exec từ file desktop thành chuỗi shell tùy tiện.
- [ ] G3.5 Thống nhất model InstalledApp: desktop ID, tên, icon, cách mở, match hints; giữ tương thích app ghim cũ qua migration/fallback.
- [ ] G3.6 Cache danh mục và refresh có kiểm soát; phát hiện app cài/gỡ/đổi entry bằng watcher hoặc refresh theo nhu cầu.
- [ ] G3.7 Bấm logo Dock mở launcher; có ô tìm kiếm, empty/loading/error state, đóng ngoài/Escape qua popup coordinator.
- [x] G3.8 Xếp hạng exact/prefix/substring trên tên, từ khóa và tên không dấu; kết quả ổn định, giới hạn số render.
- [ ] G3.9 Điều hướng bàn phím, Enter mở, trạng thái đang khởi chạy và báo lỗi; tránh mở lặp do nhiều lần Enter.
- [ ] G3.10 Ghim/bỏ ghim trực tiếp từ kết quả; cùng desktop ID không tạo nhiều pin; mở từ Dock dùng cơ chế launch thống nhất.
- [ ] G3.11 Resolve icon: đường dẫn tuyệt đối, icon theme hiện tại, inheritance/hicolor và fallback; kiểm soát kích thước/cache và định dạng SVG/PNG.
- [ ] G3.12 Dùng icon thật cho Dock, launcher, danh sách cửa sổ khi nhận diện được; icon dự phòng cho app không xác định.
- [ ] G3.13 App bị gỡ có trạng thái không khả dụng và thao tác bỏ ghim; không tự xóa pin khi lỗi quét tạm thời.

Tiêu chí: tìm được và mở đúng app thực tế gồm terminal, app có đường dẫn khoảng trắng, Flatpak/Snap nếu máy có; ghim giữ sau restart; file sai và icon thiếu không làm app crash. Test parser bằng fixtures, XDG precedence, lọc locale/environment, normalization tìm kiếm và migration pin; kiểm thử launch thực tế trên một tập app đại diện.

Bằng chứng G3.2–G3.3: `application_fixtures.rs` chạy mỗi scenario trong tiến trình mới với XDG/locale/desktop riêng; kiểm tra metadata và model InstalledApp, override user/system/fallback, desktop ID thư mục con, Hidden tombstone, NoDisplay, OnlyShowIn/NotShowIn, TryExec có/thiếu, sai Type/file hỏng và icon không resolve được. Fixture launch đã qua field codes/Terminal/Desktop Action và DBusActivatable trên bus riêng; G3.4 vẫn chờ hoàn tất tập ứng dụng thực tế, G3.6 chờ kiểm tra refresh xuyên IPC/UI sau sửa giữ monitor.

## 7. G4 — Hoàn thiện trải nghiệm Dock

Phụ thuộc G2–G3. Đây là cổng bản xem trước dùng hằng ngày đầu tiên.

- [x] G4.1 Kéo thả icon pinned để sắp xếp; lưu một lần khi kết thúc; hủy thao tác không đổi thứ tự và không vô tình mở app.
- [x] G4.2 Cung cấp thao tác bàn phím/menu để đổi thứ tự, thay thế cho kéo thả.
- [x] G4.3 Tooltip thống nhất, có delay, không đè popup và không bị cắt ngoài cửa sổ native.
- [x] G4.4 Middle-click mở phiên mới khi app hỗ trợ; ứng dụng single-instance giữ hành vi riêng, không hứa luôn tạo cửa sổ mới.
- [x] G4.5 Menu chuột phải hiển thị cửa sổ cùng app, chọn active và đóng từng cửa sổ.
- [x] G4.6 Đọc và chạy Desktop Actions được khai báo thay vì tự đoán cờ new-window/incognito; ẩn hành động không có.
- [x] G4.7 Tách kích thước icon, chiều cao Dock và khoảng cách; giới hạn giá trị để không cắt animation hay indicator.
- [x] G4.8 Chiều rộng Dock theo nội dung nhưng không vượt work area; chọn overflow cuộn hoặc nút mở thêm và kiểm thử với nhiều app.
- [x] G4.9 Giảm/tắt animation, tôn trọng prefers-reduced-motion; magnification và bounce không làm thay đổi hit target thất thường.
- [x] G4.10 Kiểm tra running/active/count khi pin đổi, app mở nhiều instance hoặc WM_CLASS không có desktop ID; lưu mapping có kiểm soát khi cần.

Tiêu chí phát hành preview: hoàn thành luồng tìm → mở → ghim → đổi thứ tự → chọn/đóng cửa sổ; restart giữ đúng thứ tự; tự ẩn và overflow không chặn thao tác; ghi rõ môi trường hỗ trợ.

## 8. G5 — Studio, preset và khả năng tiếp cận

Phụ thuộc G1/G4.

- [x] G5.1 Chia cài đặt thành Dock, Ứng dụng, Giao diện, Hình nền, Hệ thống; mô tả ngắn tác dụng của từng tùy chọn.
- [ ] G5.2 Preview dùng cùng model/tokens với Dock thật; thay đổi hiển thị đúng và có cách khôi phục trước đó.
- [x] G5.3 Preset đầy đủ: màu, opacity, radius, icon size, height, spacing, animation; xác định trường nào preset sở hữu để không ghi đè pin/autostart.
- [x] G5.4 Lưu/đổi tên/xóa preset cá nhân; tên trùng và preset thiếu trường được xử lý rõ.
- [x] G5.5 Export/import JSON có version, validation và màn hình tóm tắt thay đổi; nhập lỗi không thay cấu hình hiện có.
- [x] G5.6 Reset cấu hình có xác nhận cụ thể và phương án khôi phục; xác định rõ có xóa preset cá nhân hay không.
- [ ] G5.7 Định dạng giờ 12/24, hiện giây, ngày tháng theo locale.
- [ ] G5.8 Gom chuỗi giao diện vào tài nguyên vi/en; lưu ngôn ngữ, hỗ trợ chuỗi dài, plural và thông báo lỗi.
- [ ] G5.9 Focus-visible, nhãn accessible, tab order, contrast và trạng thái disabled; mọi thao tác chính dùng được bằng bàn phím.
- [ ] G5.10 Capability được phản ánh trong UI: tính năng chưa hỗ trợ có lý do cụ thể, không nút hoạt động giả; tách mục đang phát triển khỏi chức năng dùng được.

Tiêu chí: preview đúng Dock; import/reset không mất dữ liệu ngoài phạm vi đã thông báo; toàn bộ luồng chính hoạt động bằng bàn phím ở vi/en và reduced-motion.

## 9. G6 — Thư viện hình nền

Phụ thuộc G1/G2; capability backend cho từng desktop được xác minh trước.

- [x] G6.1 Lưu danh sách thư mục đã chọn và tùy chọn quét đệ quy.
- [ ] G6.2 Quét có giới hạn tài nguyên, hủy lượt quét cũ; xử lý quyền đọc, symlink và file hỏng; chống vòng lặp khi quét thư mục con.
- [x] G6.3 Loại trùng bằng định danh đường dẫn chuẩn; nếu phát hiện ảnh trùng nội dung, thực hiện hash riêng có kiểm soát.
- [x] G6.4 Thumbnail nền và cache có invalidation theo mtime/kích thước; lazy render/pagination cho thư viện lớn.
- [x] G6.5 Tìm theo tên, lọc thư mục/định dạng và ảnh yêu thích; favorite không mất khi thư mục tạm không truy cập được.
- [x] G6.6 Shuffle không chọn lại ảnh hiện tại khi có lựa chọn khác; xử lý thư viện 0/1 ảnh.
- [ ] G6.7 Lịch đổi ảnh theo chu kỳ, bật/tắt rõ ràng, một scheduler duy nhất; xử lý resume sau sleep và ảnh bị xóa.
- [ ] G6.8 Kiểm tra exit status/kết quả backend trước báo thành công; phản ánh hình nền đổi từ bên ngoài nếu adapter hỗ trợ.
- [ ] G6.9 Adapter GNOME/COSMIC/KDE được bổ sung riêng sau thử nghiệm API thực tế; chỉ bật adapter đã xác minh, có unsupported state.

Tiêu chí: thư viện lớn không chặn UI; ảnh hỏng/quyền thiếu có thể xử lý; chu kỳ không chạy trùng; mỗi desktop được tuyên bố hỗ trợ có kiểm thử áp dụng thực tế.

## 10. G7 — Âm thanh và media

Phụ thuộc G2/G4. Chốt backend bằng spike PulseAudio/PipeWire và D-Bus trước.

- [x] G7.1 Đọc âm lượng, mute và sink hiện tại; xác định pactl/wpctl hoặc thư viện phù hợp, báo thiếu service/công cụ.
- [x] G7.2 Popup volume với slider, mute và trạng thái đồng bộ khi thay đổi từ bên ngoài; debounce cập nhật slider, giữ mức âm lượng an toàn theo lựa chọn sản phẩm.
- [x] G7.3 Danh sách thiết bị đầu ra, chọn default, phản ánh hotplug; xác định rõ có chuyển stream đang phát hay chỉ đổi mặc định.
- [x] G7.4 Discover MPRIS players qua session bus; chọn player ưu tiên và cho người dùng đổi khi có nhiều player.
- [x] G7.5 Hiển thị title/artist/artwork/status; xử lý metadata thiếu, player thoát và artwork lỗi, cache ảnh có giới hạn.
- [x] G7.6 Play/pause/previous/next theo capability player; nút không được hỗ trợ có trạng thái rõ.
- [ ] G7.7 Ưu tiên signals thay polling nhanh; reconnect khi audio/session service khởi động lại; dọn subscriptions khi không cần.

Giới hạn hiện tại: ảnh bìa chỉ nhận file cục bộ; URL remote có fallback rõ ràng. Hotplug được kiểm thử bằng null sink, chưa bằng headset thật. Reconnect đã kiểm thử khi child subscription dừng; restart service/session bus thực tế còn nằm ở G7.7. Bằng chứng: audio-result.json, media-result.json và các ca thiếu công cụ/service, exit trong PROGRESS.md.

Tiêu chí: volume đồng bộ với hệ thống, hotplug không crash; hai player không bị điều khiển nhầm; service thiếu vẫn dùng Dock được. Test mapping/capability và kiểm thử native với player, headset thực tế nếu có.

## 11. G8 — Tiện ích hệ thống và phím tắt

Phụ thuộc G2/G4; mỗi tiện ích là module có thể bật/tắt.

- [x] G8.1 Pin qua UPower hoặc nguồn phù hợp; charging/remaining/percentage, nhiều battery nếu có; máy bàn tự ẩn.
- [x] G8.2 Trạng thái mạng cơ bản qua NetworkManager hoặc backend tương ứng: disconnected/wired/wifi; tránh suy diễn có kết nối nội bộ là có Internet.
- [x] G8.3 Popup CPU/RAM: số liệu, đơn vị, chu kỳ cập nhật; bật khi cần, không tạo thêm nguồn refresh cạnh tranh.
- [ ] G8.4 Mở system monitor bằng desktop entry/app được phát hiện, có fallback và báo thiếu ứng dụng.
- [ ] G8.5 Mở Downloads theo XDG user directories, xử lý thư mục chưa có; mở Thùng rác bằng cơ chế desktop hỗ trợ, không tự xóa dữ liệu.
- [x] G8.6 Phím tắt launcher có thể tùy chỉnh; phát hiện đăng ký thất bại/xung đột, cho đổi/tắt; không chiếm Super/Alt+Space mặc định khi chưa kiểm tra môi trường.
- [ ] G8.7 Trên Wayland, thử global shortcuts portal theo compositor; nếu thiếu thì cung cấp hướng dẫn gán phím trong desktop.

G8 hiện đã kiểm thử UPower/NetworkManager và CPU/RAM trên máy tham chiếu, gồm service không khả dụng. Downloads mở đúng qua COSMIC Files; Trash đang tắt vì thiếu URI handler đã xác minh. Chưa đánh dấu G8.4–G8.7 hoàn tất.

Tiêu chí: widget không có phần cứng/service tự ẩn hoặc báo thiếu rõ; phím tắt không làm mất thao tác desktop đã có; trạng thái tiếp tục đúng sau suspend/resume.

## 12. G9 — Wayland, chất lượng và phát hành

Phần tài liệu/kiểm thử bắt đầu từ G0; cổng phát hành tổng hợp sau các giai đoạn chọn đưa vào release.

- [x] G9.1 Chọn compositor Wayland mục tiêu dựa trên môi trường sử dụng; khảo sát layer-shell, window enumeration/control, icon identity, shortcuts và wallpaper.
- [ ] G9.2 Tạo prototype nhỏ chứng minh dock placement/auto-hide và liệt kê/chuyển/đóng cửa sổ native; đánh giá quyền và protocol thực tế.
- [ ] G9.3 Quyết định adapter Wayland theo kết quả: triển khai API được hỗ trợ, tích hợp extension/plugin nếu cần, hoặc công bố giới hạn; không cam kết API chung mà compositor không cung cấp.
- [ ] G9.4 Chạy lại luồng cốt lõi trên mỗi tổ hợp được tuyên bố hỗ trợ; tách verified/experimental/unsupported với phiên bản cụ thể.
- [x] G9.5 Tích hợp lệnh test vào package scripts/CI: config/migration, desktop parser, grouping, geometry, tìm kiếm; build TS/Vite và cargo check/test phù hợp.
- [x] G9.6 Kiểm tra policy IPC/capabilities và asset scope theo tính năng thật; hạn chế quyền dư sau khi thay shell launch bằng desktop launcher.
- [ ] G9.7 So sánh CPU/RAM, polling/process spawn với đường cơ sở; đặt ngân sách dựa trên số đo môi trường tham chiếu và điều tra regression.
- [ ] G9.8 Kiểm tra vòng đời dài: mở/đóng popup lặp, sleep/resume, service restart, rút/cắm màn hình; tìm leak và thread/timer không kết thúc.
- [x] G9.9 README: mục tiêu, ảnh minh họa, môi trường hỗ trợ, dev/build/install/uninstall, dependencies, cấu hình và troubleshooting.
- [x] G9.10 Cập nhật tài liệu kiến trúc cũ theo code thực; changelog, giới hạn và danh sách tính năng chưa hỗ trợ.
- [ ] G9.11 Chọn định dạng gói cho distro mục tiêu, cài trên tài khoản/máy sạch; kiểm tra icon/menu/autostart, nâng cấp giữ dữ liệu và gỡ cài đặt.
- [ ] G9.12 Checklist release có kết quả, version và artifact; quyết định phát hành sau kiểm thử, không tự công bố chỉ vì build thành công.

Tiêu chí: mỗi artifact cài/chạy được trên môi trường công bố; không lỗi nghiêm trọng trong luồng chính; giới hạn Wayland và backend được ghi rõ; nâng cấp không mất cấu hình.

Bằng chứng G9.6/G9.9: quyền plugin opener đã bỏ, core chỉ cho listen/unlisten; CSP không tải script/font remote và asset scope ban đầu rỗng, cấp từng file. Native startup/IPC, icon trong ảnh Studio thật, thumbnail kiểm tra pixel và force-close với PID giả đều đã qua; chi tiết trong PROGRESS.md. README có ảnh `docs/images/studio.png`, hướng dẫn dependency (gồm libXi), build/cài/gỡ và giới hạn. Cài sạch/nâng cấp vẫn thuộc G9.11, chưa được suy từ hướng dẫn này.

## 13. Thứ tự triển khai cụ thể cho đợt đầu

1. G0: kiểm thử bản hiện tại và ghi môi trường.
2. G1.1–G1.6, G1.10: cấu hình authoritative, validation, migration, persistence và startup.
3. G1.7–G1.9: vòng đời polling/listener và thông báo lỗi.
4. G2.4–G2.10, G2.12: popup/auto-hide, danh sách cửa sổ, focus và geometry.
5. G3.1–G3.5: danh mục ứng dụng và cơ chế launch; kiểm thử app thực trước UI.
6. G3.7–G3.13: launcher, tìm kiếm, ghim và icon thật; bổ sung refresh G3.6.
7. G4.1–G4.10: sắp xếp, actions, tooltip, layout/overflow và giảm hoạt ảnh.
8. Hoàn thành G1.11–G1.13, G2.1–G2.3/G2.11 và tài liệu/checklist release liên quan trước phát hành preview.

Cập nhật triển khai: nền tảng cấu hình/window backend đã có code và kiểm thử trọng tâm; Studio, wallpaper scheduler và audio/media đã được tích hợp tiếp trên cùng nhánh. Các cổng G0–G4 vẫn chưa hoàn tất toàn bộ ma trận desktop; tính năng mới không thay thế các kiểm tra đó và chưa đủ điều kiện phát hành preview. Wayland adapter vẫn chờ spike riêng.

## 14. Mốc phát hành và quy mô ước lượng

Các khoảng dưới là ngày công kỹ thuật tập trung, gồm implementation và kiểm tra cơ bản cho một người; không phải cam kết thời gian lịch. Không cộng cơ học vì còn phụ thuộc môi trường kiểm thử và protocol hệ thống.

| Giai đoạn | Khoảng dự kiến | Rủi ro chính |
| --- | --- | --- |
| G0 | 1–2 ngày | Thiếu màn hình/phần cứng để kiểm thử |
| G1 | 4–7 ngày | Migration và cập nhật nhiều cửa sổ |
| G2 | 5–9 ngày | Focus, DPI, native popup và X11 |
| G3 | 6–10 ngày | Desktop entry, launch và icon theme |
| G4 | 4–7 ngày | Kéo thả, overflow, nhận diện app |
| G5 | 5–8 ngày | Import/preset, i18n, accessibility |
| G6 | 5–9 ngày | Cache ảnh lớn và API desktop |
| G7 | 5–9 ngày | Audio hotplug, nhiều media player |
| G8 | 4–7 ngày | Service hệ thống và shortcut |
| G9 | 5–10 ngày, cộng adapter Wayland sau spike | Protocol compositor và đóng gói |

- Preview 1 sau G0–G4: Dock cốt lõi dùng được trên môi trường tham chiếu, gồm app launcher/icon/ghim/sắp xếp/grouping và cấu hình ổn định.
- Preview 2 sau G5–G6: cá nhân hóa và thư viện hình nền hoàn chỉnh hơn.
- Beta sau G7–G8 và các kiểm tra G9 liên quan: tiện ích hệ thống tùy chọn, đóng gói và ma trận hỗ trợ rõ ràng.
- Wayland: mốc riêng, quyết định phạm vi sau G9.1–G9.2; không chặn phát hành X11 nếu bản X11 đã đạt tiêu chí.

## 15. Ma trận kiểm thử và bằng chứng hoàn thành

| Nhóm | Tự động | Kiểm thử thực tế |
| --- | --- | --- |
| Config | validation, migration, revision, persistence failure | restart, nhiều cửa sổ, import/reset |
| Windows | grouping, ID, geometry, capability mapping | focus, close confirmation, outside click |
| Apps | desktop fixtures, XDG overrides, search, pin migration | launch native/terminal/Flatpak/Snap có trên máy |
| Dock | reorder/config transformations | drag/drop, keyboard, animation, overflow |
| Display | tọa độ âm, scale và clamp | multi-monitor, hotplug, mixed DPI |
| Wallpaper | dedup, scheduler, adapter error | file hỏng, thư viện lớn, đổi ảnh ngoài app |
| Audio/system | state mapping, thiếu capability | player/service restart, thiết bị cắm/rút, sleep |
| Release | frontend build, Rust checks/tests | cài sạch, autostart, upgrade/uninstall |

Mỗi đầu việc cập nhật: trạng thái, file/commit liên quan nếu có, lệnh hoặc kịch bản kiểm tra, kết quả, giới hạn còn lại. Những kịch bản chưa có thiết bị/môi trường được ghi là chưa kiểm thử, không đánh dấu pass.

## 16. Phạm vi mở rộng ngoài danh sách lần này

Live thumbnails, notification center, system tray host, quản lý workspace toàn diện và marketplace trực tuyến không nằm trong đợt thực hiện này. Chúng cần kế hoạch riêng sau khi có nền tảng ổn định; mục marketplace hiện có trong UI cần thể hiện đúng trạng thái sẵn sàng.
