# Tiến độ và bằng chứng kiểm thử DeskMorph

Mục tiêu giữ nguyên toàn bộ 99 đầu việc trong IMPLEMENTATION_PLAN.md. Chưa đạt cổng hoàn thành toàn dự án. Checkbox chưa đánh dấu không đồng nghĩa chưa có code: nhiều mục đang chờ kiểm thử đủ phạm vi.

Hiện đã đánh dấu 45/99 mục, gồm G3.2–G3.3 bằng fixture môi trường cô lập và G0.5/G2.1/G2.3 qua capability EWMH, kiểm thử lỗi adapter và native startup thiếu xprop. Đã bổ sung G0.4/G2.4/G2.5 qua popup/auto-hide native và G9.6/G9.9 bằng hồi quy policy/asset/force-close và ảnh Studio thật trong README. Các cổng GUI, Wayland và phát hành vẫn chưa hoàn tất.

## Môi trường tham chiếu đã xác minh

- Pop!_OS 24.04 LTS, x86_64; GNOME Shell 46.0; X11, DISPLAY=:1.
- GTK 3.24.41, WebKitGTK 2.52.6.
- Hai màn hình: eDP-1-1 1920×1080 tại (0,0); HDMI-0 chính 1920×1080 tại (1920,0).
- GNOME scaling-factor=0 (tự động), text-scaling-factor=1.0; chưa có bằng chứng chạy thực tế ở mixed DPI.
- Có một phiên phát triển khác đang dùng target/debug và cổng dev. Build kiểm thử dùng riêng target/agent để tránh tranh chấp; script chỉ thao tác instance có DESKMORPH_CONFIG_HOME=/tmp/deskmorph-desktop-test/config (nhận diện XDG_CONFIG_HOME cũ chỉ để restart bản test cũ). Giữ XDG_CONFIG_HOME của desktop để GSettings và dconf service đọc/ghi cùng namespace.

## Đã có implementation

- G1: mặc định JSON chung, validator native, schema version/revision, di trú localStorage, lưu file tạm + rename, backup cấu hình hỏng, đồng bộ snapshot, thao tác pin theo ID, chống polling chồng nhau và chia sẻ mẫu CPU/RAM ở backend.
- G1: giữ Dock khi đóng Studio, mở lại Studio, thoát hẳn, single-instance forwarding qua Unix socket và autostart theo XDG.
- G1: single-instance đọc request phân mảnh với deadline/giới hạn kích thước, xác nhận kết quả mở Studio qua ACK, báo lỗi dispatch và dừng/join worker khi thoát. Startup lỗi trả exit code 1. Monitor topology chuyển từ worker tách rời sang GTK timeout được remove khi thoát; đồng hồ Dock dừng khi tắt widget/Dock, đồng hồ lịch dừng khi popup ẩn và lấy snapshot visibility sau đăng ký listener.
- G2: adapter X11 tách khỏi commands, kiểm tra lỗi xprop, so sánh XID chính xác, loại cửa sổ của chính tiến trình; popup coordinator có generation, bàn phím danh sách cửa sổ; tọa độ monitor origin/scale/work area.
- G0/G2: [CAPABILITIES.md](CAPABILITIES.md) mô tả ma trận ban đầu. Runtime đọc `_NET_CLIENT_LIST` kiểu WINDOW và `_NET_SUPPORTED` kiểu ATOM, tách enumerate/activate/close, từ chối action chưa công bố; UI thể hiện trạng thái riêng. Missing/malformed property và xprop thất bại không còn trả danh sách rỗng như thành công. Outside-click X11 không chạy trong phiên Wayland/XWayland.
- G2: chọn màn hình, fallback về màn hình chính khi màn hình chọn không còn, theo dõi topology; phần hotplug thực tế còn cần kiểm thử.
- G3: GIO AppInfo/desktop entry discovery, native launch không qua sh -c, cache + AppInfoMonitor, launcher tìm tiếng Việt không dấu, pin theo desktop ID, icon theo GTK theme, actions theo desktop entry.
- G1/G3: sửa polling có thể sinh nhiều timer khi visibility đổi trong lúc request chưa xong; mỗi vòng có một timer, effect mới chờ native request cũ, hủy consumer cũ và dừng khi ẩn. Giữ AppInfoMonitor trên GTK thread thay vì thả ngay sau đăng ký; disconnect khi thay watch/thoát. Thêm invalidation khi GTK icon theme thay đổi; phần theme/render native chưa được kiểm thử tương tác.
- G4: kéo thả và Ctrl+Shift+trái/phải để sắp xếp, menu đổi thứ tự, middle-click, menu cửa sổ/actions, chiều rộng Dock theo nội dung và vùng cuộn, tùy chỉnh icon/khoảng cách, reduced-motion và tooltip native riêng.

- G5: Studio đã tách thành Dock/Ứng dụng/Giao diện/Hình nền/Hệ thống; bỏ marketplace chưa hoạt động. Preview và Dock dùng chung dockMetrics/dockSurface; preview dùng số liệu hệ thống thật và tùy chọn đồng hồ.
- G5: preset dựng sẵn và cá nhân, hoàn tác giao diện; JSON export bằng hộp thoại native, import/reset có bước xem thay đổi và revision guard. Tài nguyên vi/en và plural đã nối vào các luồng chính; lỗi backend chưa được dịch đầy đủ.

- G6: thêm scanner background có hủy theo request ID, giới hạn 20.000 mục/5.000 ảnh, canonical-path dedup, không theo symlink thư mục; lỗi từng file/thư mục được giữ để hiển thị. Thumbnail cache theo path/mtime/size, một worker decode, giới hạn 512 file/64 MB.
- G6: thư mục, đệ quy và favorite lưu trong snapshot; UI tìm/lọc, phân trang 24 ảnh. GNOME dùng GSettings/GIO với URI đúng escaping, kiểm tra ảnh và writable settings; shuffle dùng thư viện đã cấu hình và loại ảnh hiện tại khi có lựa chọn khác. Scheduler duy nhất ở backend, có bật/tắt và chu kỳ 1–1.440 phút; vô hiệu hóa lượt cũ khi đổi cấu hình, dừng khi app thoát. Quét/giải mã ở worker; GSettings được giữ và đọc/ghi trên GTK main loop.

- G7: popup âm thanh/media dùng popup coordinator hiện có; widget có thể bật/tắt trong Studio và preview. pactl JSON đọc volume theo raw channel value, giữ mức trên 100% đã có; mọi lệnh điều chỉnh mới giới hạn 0–100%, không tự bỏ mute. Chọn sink theo tên cụ thể, không chuyển stream đang phát. Các command chạy worker, có timeout/output limit và serialize ghi.
- G7: một pactl subscription khi popup mở, debounce sự kiện sink/server, reconnect khi child kết thúc, dừng/reap khi popup ẩn hoặc app thoát. Slider giữ focus và gộp giá trị mới trong lúc request đang chạy. Native focus loss có generation và kiểm tra lại sau 120 ms để tránh sự kiện hide/show cũ đóng popup mới.
- G7: discover MPRIS qua session bus, ưu tiên player đang phát rồi theo tên, chọn player rõ ràng; play/pause/previous/next theo capability và nhắm unique bus owner đã kiểm tra. Tín hiệu PropertiesChanged/NameOwnerChanged cập nhật metadata/trạng thái/danh sách; dọn subscription khi ẩn. Giới hạn 16 player và ngân sách discovery. Ảnh bìa hiện chỉ đọc file cục bộ tối đa 8 MB/16 MP, thumbnail 160 px và cache 16 ảnh tối đa 256 KB/ảnh; URL remote hiển thị fallback, chưa tải qua mạng.

- G8: widget pin/mạng tùy chọn, popup tiện ích với CPU/RAM dùng sampler hiện có (2 giây), UPower display-device aggregate và NetworkManager dùng cache chung 5 giây. Không tự đổi mạng, không ghi UPower. Máy không có pin tự ẩn widget; service lỗi có trạng thái riêng. Phân biệt connected-local và connectivity probe; thời gian pin 0/không có không bị hiển thị thành 0 phút.
- G8: phát hiện app system monitor theo desktop ID và tắt nút khi thiếu. Downloads dùng XDG user directories và file manager có category FileManager, không chọn nhầm Disk Usage Analyzer đang là mặc định inode/directory trên máy thử. Adapter COSMIC Files dùng argv đường dẫn native. Trash chỉ bật khi có URI handler; máy này thiếu handler và spike COSMIC Files không chứng minh được URI trash mở đúng, nên nút được tắt kèm lý do.

- G9: thu hẹp core permissions về event listen/unlisten, bỏ plugin opener không dùng, CSP production chặn script inline/eval/kết nối remote, asset scope ban đầu rỗng và chỉ grant icon/thumbnail đã xác minh. Bỏ font remote, đồng bộ document language theo config. Native startup read-only của binary custom-protocol mới đã có React/IPC/Dock; icon/thumbnail/CSP và thao tác tương tác còn chờ native regression khi desktop mở khóa.
- G9/G1: file config/recovery mới dùng 0600; directory-sync lỗi sau rename trả cảnh báo độ bền và giữ revision/file/memory nhất quán, có fault-injection test. X11 actions từ chối XID 0, vượt 32-bit, không còn managed hoặc nội bộ/panel; kiểm tra kết quả gửi request. Force-close bỏ kill -9 theo _NET_WM_PID, chuyển sang xkill theo X resource trong child process và UI báo phạm vi nhiều cửa sổ/tiến trình nền.
- G9: thêm workflow Ubuntu 24.04, README dev/build/cài/gỡ, ARCHITECTURE.md, CHANGELOG.md và RELEASE_CHECKLIST.md. YAML workflow đã parse và kiểm tra trigger/job/quyền contents:read; chưa chạy workflow trên GitHub, chưa tạo release artifact được cài sạch.

## Kết quả đã quan sát

- `npm test`: 14/14 qua, gồm bốn regression test polling: visibility đổi khi request pending, StrictMode/effect replacement, hidden/cleanup và retry sau lỗi.
- `npm run build`: TypeScript và Vite build qua sau bản sửa capability/clock; custom-protocol native build qua.
- Rust unit tests gần nhất: 37/37 qua ngoài sandbox (`--include-ignored`), gồm Unix socket single-instance, D-Bus riêng, monitor cài/gỡ ứng dụng và adapter xprop. Có ba entry-point subprocess là no-op khi không đặt fixture env, không tính thành ba kịch bản hành vi độc lập.
- Fixture X11: kiểm tra atom chính xác/kiểu dữ liệu, client list rỗng hợp lệ so với missing/malformed, executable thiếu/exit lỗi và action chưa công bố; tất cả chạy subprocess với PATH riêng, không truy cập X server. Native root probe GNOME công bố enumerate/activate/close. Bộ single-instance kiểm tra ACK, request phân mảnh, prefix sai/quá lớn/rỗng, callback lỗi, client giữ kết nối và shutdown dưới 2 giây. Còn kiểm thử reopen/quit native của giao thức mới khi desktop mở khóa.
- Native binary với `DESKMORPH_CONFIG_HOME` tương đối bị từ chối trước khởi tạo GUI, trả exit=1 và `deskmorph_startup_failed`, không báo khởi động thành công giả.
- Fixture ứng dụng mới chạy subprocess với HOME/XDG/LANGUAGE/XDG_CURRENT_DESKTOP riêng, không sửa môi trường test runner. Đã qua user/system/fallback precedence, Hidden override, ID thư mục con, locale fr, visibility/TryExec/file lỗi; model InstalledApp giữ hints/actions và icon fallback. Launch fixture giữ nguyên argv có ký tự shell, field codes, đường dẫn khoảng trắng, desktop action, Terminal qua xterm fixture, báo app bị gỡ/action thiếu. DBusActivatable kích hoạt đúng service `org.deskmorph.Fixture` trên bus tạm và không chạy Exec fallback. Hai test entry-point con là no-op khi runner không đặt fixture env; không tính chúng là hai ca hành vi độc lập.
- Lần chạy native trước khi bổ sung test phục hồi semantic JSON: 9/9 Rust tests qua ngoài sandbox, gồm single-instance socket và khởi chạy thực executable mẫu có khoảng trắng, ngoặc kép, $, backtick, backslash và % trong tên.
- AT-SPI file JSON: xuất file và đối chiếu nội dung; nhập file thật → xem thay đổi → áp dụng → hoàn tác; file schema sai và JSON hỏng không đổi snapshot; review cũ không ghi đè chỉnh sửa đồng thời. Báo cáo `/tmp/deskmorph-desktop-test/config-result.json`.
- Rust bổ sung: import transaction/revision guard, export round-trip và lỗi không phá đích; additive defaults được persist khi load snapshot cũ hợp lệ; scanner recursion/symlink/dedup/corrupt/cancel, thumbnail invalidation/cache bound, shuffle 0/1/nhiều ảnh.
- AT-SPI Studio G5: áp dụng preset → kiểm tra phạm vi không ghi đè pin/lifecycle → hoàn tác; lưu/đổi tên/xóa preset cá nhân bằng bàn phím X11; đổi vi/en phản ánh sang Dock; mở/hủy reset review, xác nhận reset đúng phạm vi rồi hoàn tác, và hủy hộp thoại export native đều qua trên bản đã tích hợp Studio. Báo cáo: `/tmp/deskmorph-desktop-test/studio-result.json`.
- AT-SPI kiểm thử desktop: đổi cạnh trên/dưới, bật/tắt và persistence/revision, mở lịch đã qua. Bản chiều rộng động đo Dock tại (2526,48,707,52) và (2526,1012,707,52), đúng màn hình HDMI-0 đang được chọn làm màn hình chính.
- Luồng launcher đã đi tới tìm desktop entry mẫu → ghim → mở qua GIO → gom hai cửa sổ GTK → popup danh sách → yêu cầu đóng tạo hộp xác nhận và giữ cửa sổ. Bước bấm Hủy cũng đã qua trong lần chạy native mới nhất; báo cáo basic-result.json và launcher-result.json nằm trong thư mục test.

- Native audio: chọn null sink qua UI, thay đổi volume ngoài app, reconnect sau khi kết thúc riêng child pactl của instance test, slider bằng click/phím, mute/external unmute, giữ amplification có sẵn, giới hạn điều chỉnh 100%, remove sink và ba lượt popup open/close không duplicate subscription đều qua. Khôi phục default sink và gỡ null sink được xác minh sau finally. Báo cáo audio-result.json. Ca PULSE_SERVER không tồn tại và PATH rỗng riêng cho app đều hiển thị lỗi/retry, launcher vẫn dùng được; mã audio_tool_missing được đối chiếu. Thoát bình thường dọn child subscription và mở lại tiến trình mới đã qua; báo cáo audio-unavailable-result.json, audio-tool-missing-result.json, audio-exit-result.json.
- Native media: hai MPRIS fixtures, chọn player, metadata/artwork cục bộ/fallback remote, disabled capability, play/pause/previous/next gửi đúng player, playback/metadata signals và player exit/fallback đều qua. Không điều khiển Chromium thật. Báo cáo media-result.json.

- Hồi quy sau G7 trên cùng artifact: basic, Studio, JSON config và launcher đều qua. Dock có thêm nút audio, chiều rộng đo được 797 px tại (2481,48)/(2481,1012), vẫn nằm trong HDMI-0. Các báo cáo basic/studio/config/launcher đã được cập nhật cho PID 2547549.

- Native G8: widget pin đối chiếu percentage tổng hợp UPower, lưu/khôi phục tùy chọn widget, CPU/RAM và đơn vị/chu kỳ, network kind và khả năng system monitor đã qua (system-result.json). Mô phỏng system bus không truy cập được bằng biến môi trường riêng: lỗi UPower/NetworkManager rõ ràng, CPU/RAM và launcher vẫn dùng được (system-unavailable-result.json).
- Native Downloads: mở đúng cửa sổ COSMIC Files mang tiêu đề Downloads; dọn đúng XID mới và xác minh các cửa sổ file manager trước test còn nguyên. Đối chiếu nút Trash với URI handler (system-open-result.json). Spike sai URI trước đó được dọn bằng WM_DELETE_WINDOW sau khi kiểm tra PID/argv, không đóng cửa sổ file manager có sẵn.

- Native startup sau CSP/quyền mới: AT-SPI đọc được Studio đã tải config, các control và Dock groups ở PID 2656681, không gửi input; policy-startup-result.json. Đây chỉ là startup/IPC check, không chứng minh icon/thumbnail hay force-close đã qua regression.
- Native startup mới nhất sau sửa polling/catalogue monitor: custom-protocol build qua; `desktop_smoke.py --restart --inspect` khởi động đúng profile test tại PID 2690631, đọc được Studio controls/config và Dock groups. Không gửi input; không dùng kết quả này để đánh dấu interactive regression/icon/thumbnail pass. `--environment` vẫn trả GNOME ScreenSaver active=true, active XID=0x0.
- Native capability mới: `--platform-tool-missing --inspect` tại PID 2724572 đọc được `xprop_unavailable` trong Studio và nút launcher, `inputSent=false`; báo cáo `platform-tool-missing-result.json`. Đã restart profile với PATH bình thường tại PID 2726908, cây accessibility có Studio controls và Dock groups khớp cửa sổ thật. Chưa gửi chuột/phím, chưa kiểm tra calendar polling/focus/close tương tác trên build này.
- Lượt kiểm thử tương tác nối tiếp bị chặn khi GNOME ScreenSaver.GetActive=true và active XID=0x0. Harness hiện kiểm tra lock trước khi tạo fixture và trước mỗi lần focus/gửi phím; preflight refusal đã được xác minh. Không bỏ PID guard, không gửi input vào lock screen. Người dùng sau đó đã mở khóa; kết quả chạy tiếp được ghi bên dưới, không dùng trạng thái khóa cũ để chặn công việc hiện tại.

## Kiểm thử tiếp sau khi mở khóa desktop

- Đã xác minh ScreenSaver inactive và tiếp tục gửi input có lock/PID guard. Basic/Studio/JSON/launcher qua lại trên profile riêng; top/bottom Dock 837 px ở (2461,48)/(2461,1012). Cấu hình và wallpaper gốc được khôi phục trong các ca tương ứng.
- `--force-close-smoke` tạo hai GTK windows cùng X client và một sleep sentinel riêng; gán `_NET_WM_PID` của hai fixture XID sang sentinel, kiểm tra cancel/confirm. Chỉ X client fixture bị đóng, sentinel và toàn bộ cửa sổ bên ngoài còn nguyên. Báo cáo `force-close-result.json`; hồi quy đã qua trên PID app 3213515.
- `--wallpaper-smoke` kiểm tra hơn 500 pixel tím của ảnh fixture two.png trong vùng tile thuộc Studio, ngoài kiểm tra file cache; đã qua CSP/asset production, cùng apply cả light/dark, shuffle, favorite/filter và finally restore. Ảnh crop trong `thumbnail-render.png`; `wallpaper-result.json` trên PID 3213515. Icon thật hiện trong ảnh Studio `docs/images/studio.png` đã liên kết README.
- `--popup-smoke` phát hiện hai lỗi: polling 40 ms bỏ sót click press/release ngắn; Escape sau hide/show nhanh có lúc không tới DOM listener. Đã dùng XI2 raw queue (fallback pointer state), yêu cầu focus nội dung sau GTK dispatch có generation guard và thêm Escape ở GTK toplevel. Chỉ thêm native Escape chưa đủ: một lần tái mở launcher vẫn lỗi, vì vậy giữ cả hai phần sửa. Build tiếp theo PID 3225374 qua ba vòng cùng tiến trình, mỗi vòng năm chuỗi launcher/calendar/audio; Escape, focus loss, outside click và không tooltip đè popup đều qua. Chưa suy từ đây thành toàn bộ ma trận DPI/auto-hide đã hoàn tất.
- Audio/media/system/Downloads đã qua hồi quy sau mở khóa. Có một lần Home sau click slider không đổi mức; không tuyên bố đã tìm được nguyên nhân. Một lần chọn default sink trả 100% thay vì mức 37% đặt trước đó, nhưng slider khớp server: test đã đổi sang so sánh native server sau selection, vẫn kiểm tra riêng external change 62%, zero/100%, amplification và mute. Chuỗi popup ba vòng → audio → normal exit/relaunch qua trên PID 3225374; default sink được khôi phục, null sink và subscription được dọn. Reconnect ở đây chỉ là child pactl, không phải restart dịch vụ desktop.
- `npm test`: 14/14; `npm run build`: TS/Vite qua; Rust native `--include-ignored`: 37/37. Binary custom-protocol build thành công. Hồi quy auto-hide và chuỗi kết hợp trên binary mới được ghi bên dưới, không dùng riêng các kết quả unit này để suy ra GUI pass.
- `--autohide-smoke` phát hiện Dock giữ hiện sau Escape vì trigger bị gỡ mà không có mouseleave và native resize gây hover không khớp tọa độ thật. Timer cạnh chưa đủ ở bottom, nên đã thêm đối chiếu con trỏ X11 mỗi 250 ms khi auto-hide bật và popup đóng; ngoài 500 ms thì ẩn. Native top/bottom qua trên PID 3326895 và 3368221: reveal cạnh, giữ khi chuột ở bề mặt, ẩn khi rời, giữ calendar/audio, Escape và tắt Dock đóng popup, khôi phục tùy chọn. Lượt sau còn lỗi hover khi script nhắm tọa độ icon đang animation; đã chuyển sang tâm native rect sau khi reveal và đối chiếu con trỏ thật, rồi chạy lại cả chuỗi thành công (xem bên dưới). Chưa có mixed DPI/hotplug thực tế.
- Rê chuột thật còn phát hiện panic Tao `CursorIgnoreEvents` unwrap GDK window của tooltip chưa map. Đã bỏ lời gọi không kiểm tra đó và đặt input region rỗng trong GTK map với kiểm tra window tồn tại. Những lượt hover tiếp theo không crash; test không gửi input cho tiến trình khác.
- Lượt stress nối tiếp sau auto-hide từng có lỗi; G2.8 vẫn chưa đủ bằng chứng toàn phạm vi. Đã mở rộng Escape tới các GTK toplevel của chính app để xử lý trường hợp key được chuyển tới Studio, và gắn generation vào visibility cho Audio/Media/System để sự kiện ẩn của lượt cũ không vô hiệu hóa lượt mới. Stress chạy với Dock hiện đầy đủ, auto-hide được kiểm thử riêng và được khôi phục bằng finally; bản sửa generation mới đã qua chuỗi hồi quy cuối được ghi bên dưới.

## Kết quả chuỗi native cuối và commit

- `--autohide-smoke --popup-smoke --audio-smoke --media-smoke --force-close-smoke --wallpaper-smoke --audio-exit` kết thúc exit 0: PID 3535101 qua top/bottom auto-hide, ba vòng popup (15 chuỗi launcher/calendar/audio), media và audio. Normal exit dọn subscription; khởi động lại PID 3541924, wallpaper/thumbnail và launcher/close-confirmation/force-close đều qua. Sentinel vẫn sống và fixture được gỡ, default output và GNOME wallpaper được khôi phục. Báo cáo trong `/tmp/deskmorph-desktop-test` theo từng ca. G0.4/G2.4/G2.5 được đánh dấu từ phạm vi này; mixed DPI/hotplug/ngoài desktop tham chiếu chưa được suy thành pass.
- Hai lỗi harness đã được xác định: launcher top có thể che tiêu đề Studio dùng làm điểm outside-click, và AT-SPI vẫn truy cập được icon Dock khi đã auto-hide. Outside-click giờ dùng vùng header trống bên phải và kiểm tra nó nằm ngoài popup; các ca khác dùng baseline Dock hiện đầy đủ, auto-hide có ca riêng. Hover nhắm tâm native rect đã ổn định và kiểm tra con trỏ chưa bị thay đổi từ bên ngoài.
- Điểm bấm cũ từng mở Auto-cpufreq trong profile test. Đã xác minh môi trường của các PID liên quan; chỉ dọn tiến trình còn sống có đúng `DESKMORPH_CONFIG_HOME` test bằng pidfd + SIGTERM. Không đóng app của profile người dùng. Không dùng những lượt bị can thiệp đó làm bằng chứng pass hay quy toàn bộ lỗi cho sản phẩm.
- Stress catalogue dùng Hidden overrides trong XDG_DATA_HOME tạm và fixture desktop entry; giữ XDG_DATA_DIRS hệ thống. Thử nghiệm bỏ XDG_DATA_DIRS trước đó làm ca artwork fail; khi giữ tài nguyên hệ thống, media từ startup bình thường và toàn chuỗi đều qua. Harness không giả định “file thumbnail tồn tại” là render thành công, và không giả định volume trước khi đổi default sẽ luôn giữ nguyên theo policy audio.
- Đã chốt các module riêng bằng commit tiếng Việt: `a3fb110` cấu hình, `a9143e5` catalogue và fixtures, `676bda5` X11/capability/geometry, `0275506` runtime native và `690373a` tích hợp UI/runtime cùng unit tests frontend. Đây là commit module; `46157e1` hạ tầng CI/native test. Tài liệu được tách riêng, không phải tuyên bố toàn bộ 99 mục hoàn thành.

- Lặp xác minh harness sau khi thêm metadata hợp lệ cho tombstone và assertion catalogue: PID 3555639 qua thêm ba vòng stress, launcher chỉ có fixture/noop; không mở app thật.

## Ghi chú môi trường test

`DESKMORPH_CONFIG_HOME` là override riêng cho config/instance/autostart DeskMorph, phải là đường dẫn tuyệt đối. Không đổi `XDG_CONFIG_HOME` để cô lập app khi kiểm thử dịch vụ desktop: dconf service dùng namespace thật của phiên người dùng, dẫn tới đọc và ghi khác nơi nếu thay XDG của client. Test vẫn cô lập XDG_DATA_HOME/cache để đăng ký desktop fixture và cache ảnh. Profile mặc định dùng XDG như trước.

G7 spike chỉ đọc: pactl 16.1 kết nối PulseAudio trên PipeWire 1.6.8, JSON info/list sinks khả dụng; có hai output (analog và HDMI), MPRIS Chromium được phát hiện trên session bus. Đã triển khai pactl JSON + subscription và GIO D-Bus, không thêm thư viện native. Kiểm thử ghi dùng null sink tạm; đầu ra mặc định được khôi phục và fixture được gỡ trong finally.

## Tái chạy

```sh
npm test
npm run build
cargo test --offline --manifest-path src-tauri/Cargo.toml --target-dir src-tauri/target/agent --lib
cargo build --offline --manifest-path src-tauri/Cargo.toml --target-dir src-tauri/target/agent --features custom-protocol
```

Trong phiên X11 thật, ngoài sandbox:

```sh
cargo test --offline --manifest-path src-tauri/Cargo.toml --target-dir src-tauri/target/agent --lib -- --include-ignored
/usr/bin/python3 tests/desktop_smoke.py --restart --basic --studio-smoke --config-smoke --wallpaper-smoke --launcher-smoke
/usr/bin/python3 tests/desktop_smoke.py --scheduler-smoke
/usr/bin/python3 tests/desktop_smoke.py --library-stress
/usr/bin/python3 tests/desktop_smoke.py --restart --audio-unavailable
/usr/bin/python3 tests/desktop_smoke.py --restart --audio-tool-missing
/usr/bin/python3 tests/desktop_smoke.py --restart --audio-smoke --media-smoke --audio-exit
/usr/bin/python3 tests/desktop_smoke.py --restart --system-unavailable
/usr/bin/python3 tests/desktop_smoke.py --restart --system-smoke --system-open-smoke
/usr/bin/python3 tests/desktop_smoke.py --platform-tool-missing --inspect
/usr/bin/python3 tests/desktop_smoke.py --restart --inspect
```

Script cần AT-SPI, Python GI, GTK3 và libXtst. Chỉ gửi phím khi kiểm tra focus thuộc PID của phiên thử nghiệm. Dữ liệu và log test trong /tmp/deskmorph-desktop-test; script không điều khiển instance dùng cấu hình thông thường. Không dùng kết quả cũ để chứng minh một build mới chưa được chạy.

## Chưa xác minh hoặc chưa triển khai đủ

- Kiểm thử thực tế kéo thả, tooltip đầy đủ và focus race khi chuyển popup nhanh; auto-hide top/bottom đã qua; đổi màn hình, hotplug và mixed DPI.
- Fixture XDG override/locale/TryExec/app bị gỡ đã qua. Còn Flatpak/Snap export thật, quyền đọc thư mục lỗi, terminal thực tế và refresh danh mục/icon xuyên IPC/UI sau bản sửa monitor; xterm fixture chỉ kiểm tra hợp đồng argv của GIO.
- G5: vẫn cần đầy đủ bàn phím/contrast và i18n lỗi backend; lỗi filesystem/export đã có test backend, chưa mô phỏng mọi lỗi IO từ hộp thoại native.
- G6: native đã qua thêm thư mục/đệ quy, loại ảnh hỏng, tạo cache thumbnail, favorite/filter/search, áp dụng URI có dấu cách cho cả light/dark, shuffle tránh ảnh hiện tại, giữ favorite khi bỏ thư mục. Hình nền và cấu hình thư viện trước test được khôi phục trong finally. Báo cáo `/tmp/deskmorph-desktop-test/wallpaper-result.json`.
- G6: scheduler native một phút đã đổi ảnh khi Studio đóng, mở lại đúng instance và dừng khi tắt; bộ test cũng lặp shuffle ba lượt trong cùng tiến trình. Test clock mô phỏng sleep/clock jump và scan hơn 20.000 mục đã qua. Stress native 5.001 file đã qua: giới hạn 5.000 ảnh được hiển thị, chỉ 24 ảnh mỗi trang, chuyển trang trước/sau đúng; trang đầu khoảng 0,897 giây. Báo cáo library-stress-result.json. Quyền đọc/service lỗi và adapter khác vẫn cần hoàn thiện.
- G7: còn kiểm thử audio service restart thực tế, session bus restart và thiết bị headset thật; test hiện tại mô phỏng hotplug bằng null sink, reconnect bằng việc kết thúc child subscription của riêng app. Ảnh bìa remote chưa hỗ trợ. Không coi test fixture là bằng chứng của sleep/resume hay mọi player thực tế.
- G8: shortcut launcher X11 đã qua G8.6 trên desktop tham chiếu; Wayland portal, keymap remap và resume thực tế chưa kiểm thử; chưa test pin đa thiết bị/sleep/resume và system monitor launch khi có ứng dụng. Trash đang unsupported trên máy tham chiếu, chưa có adapter COSMIC nội bộ được xác minh. Downloads missing-directory và desktop khác chưa có native test.
- G9: native policy/force-close và ảnh chụp README đã có bằng chứng; còn Wayland prototype, performance và đóng gói/cài sạch/nâng cấp. Workflow mới chưa chạy trên GitHub. Khảo sát chỉ đọc cho thấy phiên hiện tại X11, không có WAYLAND_DISPLAY hay wayland-info/weston/sway/Xvfb; các XML protocol có trên đĩa không phải bằng chứng compositor hỗ trợ. Không tự đổi session hoặc bật GNOME unsafe mode.
- Chưa có artifact phát hành được kiểm thử cài sạch; chưa có bằng chứng đạt toàn bộ ma trận hỗ trợ.

## G8.6 — Phím tắt launcher X11 (29/10/2026)

- Mặc định tắt; lưu lựa chọn riêng trạng thái đăng ký, checked XCB grab trên connection riêng, xử lý lock masks, keymap lỗi, xung đột/retry và generation. UI vi/en cho đổi/tắt; tắt Dock pause grabs và mở lại khôi phục. Không chiếm phím desktop sẵn có; tổ hợp Ctrl+Alt+Fn bị từ chối.
- Native `--shortcut-smoke` qua trên PID 104840: fixture giữ cùng chord làm đăng ký báo xung đột, nhả fixture rồi retry; phím thật mở launcher và Escape đóng; mở từ cửa sổ GTK fixture riêng nhận focus đúng; đổi K sang J giải phóng phím cũ; tắt/bật Dock pause/resume; normal exit giải phóng, startup khôi phục; disable lưu null. Finally khôi phục lựa chọn ban đầu null. Báo cáo `/tmp/deskmorph-desktop-test/shortcut-result.json` có bảy assertion nhóm đều qua.
- Kiểm thử xuyên ứng dụng phát hiện launcher hiện nhưng WM không cấp focus. Đã truyền timestamp KeyPress tới GTK present_with_time với popup generation guard; lượt sau qua. Harness chỉ gửi phím cho PID test hoặc GTK fixture do chính harness tạo và kiểm tra môi trường; không nới guard cho ứng dụng ngoài.
- Lượt đầu từng dùng Ctrl+Alt+Fn và không mở launcher; truy vấn ScreenSaver sau đó timeout. Không đủ bằng chứng quy kết đã chuyển VT. Đổi test sang K/J và chặn nhóm phím này trong parser/UI help. Một lỗi harness khác dùng lệnh forwarding ACK để khởi động app mới đã được sửa bằng helper Popen/readiness riêng; không coi lượt lỗi đó là pass.
- Trên source cuối: Rust native `--include-ignored` 41/41; frontend 14/14 và TS/Vite build qua; custom-protocol native build qua; Python compile và diff whitespace qua. CI thêm libxcb1-dev, xvfb/xauth và Xvfb cho Rust grab test; chưa có kết quả GitHub. Native GUI chỉ xác minh GNOME/X11 tham chiếu, chưa chứng minh Wayland, mọi layout, remap, suspend/resume hay compositor khác.
- Báo cáo /tmp của các lượt 28/10 không còn sau khi môi trường desktop thay đổi; bằng chứng cũ trong tài liệu là lịch sử, không thay cho kết quả build hiện tại.
- Hồi quy sau sửa focus timestamp: `--popup-smoke` exit 0 trên PID 111574, ba vòng/15 chuỗi launcher-calendar-audio; Escape, thay popup, focus loss, click ngoài và tooltip đều qua. Báo cáo `/tmp/deskmorph-desktop-test/popup-result.json`.

## G1.10–G1.12 — Vòng đời Studio/Dock và single-instance (29/10/2026)

- Thêm `--lifecycle-smoke`, exit 0 trên chuỗi PID 111574 → 120103 → 120586 → 121080 → 121560 → 122438 → 122925 → 123364. Không cần sửa production: hành vi hiện có đã qua native tests mới. Báo cáo `/tmp/deskmorph-desktop-test/lifecycle-result.json`.
- Bật/tắt Dock theo chuỗi false/true/false/true, mỗi trạng thái qua normal Quit và khởi động tiến trình mới; so cấu hình lưu với managed native Dock count, chờ thêm 1,2 giây để bắt callback startup/layout trễ. Dock không tự hiện ngược lựa chọn.
- Khi enabled và keepDockOnClose bật, WM_DELETE_WINDOW đóng Studio nhưng giữ Dock/tiến trình. Ba lượt mở executable tiếp theo đều ACK, hiện lại đúng một Studio trong cùng PID. Bốn lệnh mở đồng thời đều exit 0, không tạo thêm Studio/Dock. Unit Unix socket đã qua thêm trường hợp request phân mảnh/stale socket/lock/ACK trong bộ Rust 41/41.
- Đóng Studio khi Dock tắt (dù keep bật), hoặc keepDockOnClose tắt (dù Dock bật), đều thoát tiến trình. Nút Quit thoát cả khi keep bật. Harness khôi phục enabled/keepDockOnClose/autoHide ban đầu qua UI và chỉ thao tác profile test.
- G1.10/G1.11/G1.12 được đánh dấu từ phạm vi trên; không coi đây là bằng chứng autostart đăng nhập, suspend/resume hoặc mọi lỗi startup. Python compile và diff check qua. Frontend/native production không đổi so với build đã kiểm thử G8.6.

## G1.13 — Đăng ký menu/autostart bằng executable thực tế (29/10/2026)

- `--registration-smoke` exit 0: PID 134799 chạy bản hardlink native binary ở thư mục `registration space " 100% $fixture`, tên executable giữ `deskmorph`. UI tạo cả menu entry và autostart entry trong profile tạm. GIO parse được hai file, menu entry mở lại Studio cùng PID; autostart entry mở tiến trình mới PID 135401 đúng executable này. Báo cáo `/tmp/deskmorph-desktop-test/registration-result.json`.
- Native test xác minh lại checkbox autostart sau restart, tắt xóa entry. Biến đường dẫn đích thành directory gây lỗi ghi cho từng command; UI hiện `os error 21` và autostart không tự báo enabled. Xóa lỗi bằng thao tác thành công giữa hai ca để không dùng nhầm thông báo cũ. Finally phục hồi entry có sẵn trong profile test và mở lại binary bình thường PID 136019.
- Unit GIO trong bộ Rust 41/41 cũng launch script ở path chứa khoảng trắng, dấu nháy, phần trăm, backslash và ký tự shell; không thực thi shell interpolation. Không sửa production ở bước này. Python compile và diff check qua.
- Hai lượt harness đầu chưa đạt: đổi basename executable làm AT-SPI đổi tên app nên readiness không nhận diện; đã giữ basename và đưa ký tự đặc biệt vào tên thư mục. Chỉ dọn PID 127888 sau xác minh exact test env/executable bằng pidfd. Helper startup nay terminate/wait Popen của chính nó nếu readiness timeout. Lượt tiếp dùng tên role AT-SPI `alert` quá chặt; đã kiểm tra nội dung lỗi IO thật. Không coi hai lượt đó là bằng chứng pass.
- G1.13 hoàn tất trong phạm vi tạo/launch entry, executable path và lỗi ghi. Chưa chạy đăng xuất/đăng nhập hay boot thật; autostart entry được launch thủ công bằng GIO. Cài sạch/nâng cấp và phiên desktop khác vẫn pending.
