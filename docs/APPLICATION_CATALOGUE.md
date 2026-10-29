# Danh mục ứng dụng và đường tìm kiếm

DeskMorph dùng GIO AppInfo/ DesktopAppInfo cho cả discovery và launch theo desktop ID. Không tự tách Exec thành shell command. XDG_DATA_HOME/applications có ưu tiên cao nhất, gồm Hidden=true tombstone. GIO xử lý ID từ đường con, desktop environment, locale và symlink deployment.

Ngay đầu run_app, trước GTK/GIO hay worker, catalogue_paths::prepare giữ thứ tự thư mục tuyệt đối trong XDG_DATA_DIRS, loại trùng và nối các đường export chuẩn:

1. $FLATPAK_USER_DIR/exports/share nếu biến là đường tuyệt đối; nếu không, $XDG_DATA_HOME/flatpak/exports/share. XDG_DATA_HOME thiếu hoặc tương đối thì dùng $HOME/.local/share.
2. /var/lib/flatpak/exports/share.
3. /var/lib/snapd/desktop.

Nối cả root chưa có thư mục applications: GIO theo dõi ancestor để phát hiện lần cài đầu tiên trong cùng process. XDG_DATA_DIRS thiếu/rỗng/không có đường tuyệt đối dùng /usr/local/share:/usr/share. Các đường được cấu hình rõ đứng trước fallback. Thay đổi chỉ nằm trong process DeskMorph và môi trường child; không ghi cấu hình phiên desktop. Không thay biến toàn cục trong command hay sau khi GLib cache đường. System Flatpak installation tùy chỉnh được hỗ trợ khi có trong XDG_DATA_DIRS, chưa tự đọc installation config.

Kiểm thử Rust chạy GIO trong subprocess với XDG riêng; fake export layout bao phủ ba root, symlink, priority/Hidden/ID trùng và launch marker từ desktop ID. Ca native:

```sh
/usr/bin/python3 tests/desktop_smoke.py --exports-smoke --launcher-smoke
```

Chỉ dùng isolated test profile. Harness bỏ export khỏi startup XDG_DATA_DIRS, tìm tên duy nhất bằng native input rồi launch qua UI, kiểm marker, xóa fixture và khôi phục config/process bình thường. Cần desktop GNOME X11 mở khóa. [Bản ghi](benchmarks/catalogue-exports-2026-10-29.json) và [tiến độ](PROGRESS.md) ghi phạm vi: đây là export-layout fixture, chưa phải chạy gói Flatpak/Snap đã cài.


## Refresh trong cùng process

Catalogue backend cache 30 giây; AppInfoMonitor và GTK theme change đánh dấu dirty, phát deskmorph:apps-changed cho consumer. Refresh chủ động bỏ qua cache thời gian. Monitor giữ reference trên GTK main context và disconnect khi thay watch/thoát; hook có một request đang chạy cùng một pending reload cho mỗi effect, bỏ completion sau dispose và dọn listener đăng ký muộn.

```sh
/usr/bin/python3 tests/desktop_smoke.py --catalogue-refresh-smoke --exports-smoke
```

Ca refresh tạo FLATPAK_USER_DIR riêng còn chưa tồn tại khi app khởi động. Giữ launcher mở với query cố định, rồi tạo export/entry, atomic rename, Hidden=true, khôi phục và gỡ. Kiểm kết quả UI thay đổi mà không refresh/restart; thêm refresh chủ động và thay entry khi consumer đã đóng rồi mở lại. Sau cùng dọn đúng thư mục mkdtemp sở hữu và khôi phục config/process thường. [Bản ghi](benchmarks/catalogue-refresh-2026-10-29.json) lưu thời gian vòng đợi quan sát; đây không phải benchmark độ trễ đầy đủ từ filesystem đến UI. Kiểm chứng native hiện trên GNOME X11 tham chiếu.


## Model và tương thích pin cũ

InstalledApp ở Rust/TypeScript có id desktop chuẩn, name/genericName/keywords, executable hint, matchClasses, iconPath nullable và danh sách action ID/name. Serde camelCase là hợp đồng IPC. Launch desktop entry luôn dùng id qua GIO; executable và matchClasses phục vụ nhận diện, không dùng để tái tạo Exec.

Pin mới từ catalogue lưu desktopId cùng command=desktop:ID. Với pin cũ, desktopId (nếu có), command desktop:ID hoặc bare ID.desktop là identity ưu tiên; nếu entry không còn thì không được tìm một ứng dụng khác bằng WM_CLASS. Lệnh cũ không có desktop identity được giữ nguyên, kể cả argv và đường dẫn có khoảng trắng. Ghép metadata chỉ khi executable hoặc WM_CLASS cho kết quả duy nhất; trường hợp mơ hồ giữ icon/fallback hiện có thay vì chọn theo thứ tự catalogue.

launchCommandForPin được dùng cho click/middle-click/menu của pin. Menu ưu tiên command đã chuẩn hóa từ pin, còn Desktop Actions dùng action ID của InstalledApp. Không tự viết lại pin legacy sang desktop ID và không làm mất profile/flags riêng. Pin cũ vẫn qua migration/load của ConfigStore.

```sh
/usr/bin/python3 tests/desktop_smoke.py --pin-identity-smoke
```

Ca native dùng hai pin với executable/script có khoảng trắng và argv nhiều từ/ký tự shell literal. Một pin legacy resolve metadata bằng StartupWMClass nhưng phải giữ lệnh riêng; pin còn lại có desktopId trái với command và phải mở đúng desktop entry. Cả click/middle-click/menu đều kiểm argv thực thi; restart kiểm nguyên danh sách pin/lệnh. [Bản ghi](benchmarks/pin-identity-2026-10-29.json).


## Ghim theo desktop identity

Một desktopId chỉ có một pin, kể cả các bản ghi có id pin khác nhau hoặc lưu identity dưới dạng desktop:ID / ID.desktop. Backend serialize thao tác và kiểm identity tại add, không chỉ dựa vào trạng thái UI. Add lặp enable pin hiện có, giữ tên/order/lệnh/id đã tùy chỉnh. Patch/import mới trùng identity bị từ chối; không ghi config một phần.

Load/migration dữ liệu từ bản cũ gộp duplicate explicit identity, giữ bản đầu và bật nếu có bản đang bật. Native giữ bytes gốc và recovery copy kèm warning; localStorage legacy vẫn được giữ. Không gộp theo WM_CLASS hay lệnh custom phỏng đoán. Không thay tên/metadata pin legacy bằng tên từ catalogue khi re-enable.

```sh
/usr/bin/python3 tests/desktop_smoke.py --pinning-smoke --pin-identity-smoke
```

Ca native bao phủ duplicate recovery/re-enable/unpin/re-pin/Dock launch/restart, khôi phục config và chỉ xóa recovery có đúng bytes fixture. [Bản ghi](benchmarks/pinning-2026-10-29.json).


## Entry mất và lỗi quét

Pin được giữ khi entry bị gỡ hoặc không hiển thị trong catalogue. Sau lần đọc thành công, desktop identity thiếu có badge/accessible label/tooltip ở Dock và trạng thái trong Studio/menu. Menu không cho launch một entry đã xác nhận thiếu nhưng vẫn cho bỏ ghim. Cửa sổ còn chạy vẫn được activate/chọn; legacy custom command không có desktop identity không bị coi là app đã gỡ chỉ vì không tìm thấy metadata.

Loading/lỗi quét không chứng minh entry mất: giữ snapshot gần nhất, không gỡ pin và không tự chọn app khác bằng WM_CLASS. Reinstall cùng desktop ID khôi phục trạng thái tự động qua monitor, kể cả menu đang mở. Chỉ thao tác unpin rõ ràng của người dùng mới xóa pin.

```sh
/usr/bin/python3 tests/desktop_smoke.py --missing-app-smoke --pinning-smoke
```

Native bao phủ gỡ/cài lại entry, menu disabled/enable, restart giữ pin thiếu, và unpin từ menu/Studio. Lỗi IPC tạm thời được kiểm ở hook test có invoke rejection thật trong adapter mô phỏng; không tuyên bố đã gây lỗi quét GIO trên desktop. [Bản ghi](benchmarks/missing-app-2026-10-29.json).


## Launcher và bàn phím

Logo Dock mở launcher qua popup coordinator. Có loading, error/retry và empty state riêng; lỗi quét không đồng thời thông báo không tìm thấy app. Query native input đi qua React; kết quả giới hạn 60, Up/Down wrap, CtrlHome/CtrlEnd chọn đầu/cuối phần đang render, Enter mở desktop ID hiện tại. aria-current thể hiện mục đang chọn; live status báo tên đang mở.

Một launch lock theo instance chặn nhiều Enter/click/retry khi IPC chưa xong. Thành công chỉ hide generation của lần mở đó; lỗi giữ popup và cho retry cùng app; callback đã dispose không đóng popup mới. Escape/outside/focus-loss do native popup coordinator quản lý.

```sh
/usr/bin/python3 tests/desktop_smoke.py --launcher-keyboard-smoke
/usr/bin/python3 tests/desktop_smoke.py --focus-smoke
```

Chạy hai ca riêng; mỗi ca khôi phục profile/process. Native chứng minh chọn/mở đúng ID, empty/Escape, lỗi executable bị xóa và retry sau restore, cùng outside/focus/shortcut. Component test điều khiển IPC pending để chứng minh chặn Enter/retry lặp và kiểm loading/error/render; không dùng executable chạy chậm làm bằng chứng IPC pending. [Bản ghi](benchmarks/launcher-2026-10-29.json).


## Icon theme, raster và giới hạn cache

GTK IconTheme chọn icon theo theme hiện tại, inheritance và hicolor; absolute FileIcon đọc trực tiếp từ đường native. application_icons.rs tạo PNG tối đa 64×64, giữ tỷ lệ, thay vì cấp WebView quyền đọc file icon gốc. Nguồn phải là file tuyệt đối có thể đọc, không quá 2 MiB và 16 triệu pixel theo metadata GdkPixbuf. SVG/PNG đã kiểm; format khác phụ thuộc loader GdkPixbuf cài trên máy. Nguồn thiếu/hỏng/quá lớn, cache không ghi được hoặc vượt capacity trả iconPath=null để app vẫn dùng được với icon dự phòng.

Cache application-icons-v1 trong app cache có tối đa 512 PNG, mỗi file không quá 32 KiB (tối đa 16 MiB PNG, cộng file ghi tạm đang hoạt động). Key gồm canonical source path/size/mtime/ctime; thay nguồn hoặc theme resolve sang file khác tạo URL mới. Một lượt catalogue giữ các file đã trả, không evict chúng giữa lượt. Tới capacity thì icon dư dùng fallback; desktop ID được sort trước khi phân cache để lựa chọn ổn định. Lượt refresh sau có thể bỏ file cũ chưa dùng. Startup dọn file tạm đúng định dạng có producer PID đã thoát và PNG thuộc cache vượt giới hạn; không dọn file ngoài namespace quản lý.

Asset scope khởi đầu rỗng. Khi đọc catalogue, native cho phép riêng thư mục cache icon không đệ quy; không thêm từng source icon hoặc từng version URL vào allow-list. Thumbnail wallpaper vẫn được cấp từng file, artwork dùng PNG data URL. GTK theme changed và AppInfoMonitor đánh dấu dirty/refresh metadata.

Dock ghim dùng desktop identity/legacy mapping; Dock chưa ghim chỉ mượn icon khi class khớp desktop identity hoặc hints duy nhất. Class mơ hồ/không rõ dùng icon dự phòng. WindowList nhận desktop ID từ Dock, lấy icon mới từ catalogue cho header/row; không luôn vẽ AppWindow khi đã nhận diện được. AppIcon xử lý lỗi load và có thể phục hồi khi cache URL đổi.

```sh
cargo test --offline --manifest-path src-tauri/Cargo.toml --target-dir src-tauri/target/agent --lib -- --include-ignored
/usr/bin/python3 tests/desktop_smoke.py --icon-render-smoke
/usr/bin/python3 tests/desktop_smoke.py --window-list-smoke
```

Ca GTK chạy subprocess với IconTheme tùy chỉnh riêng (không đổi theme desktop), chứng minh inheritance/hicolor/absolute/missing/theme switch. Native đo pixel màu riêng trên launcher, pinned/unpinned Dock và row cửa sổ từ absolute SVG và hicolor PNG; kiểm app vẫn hiện khi icon thiếu và kiểm kích thước/cache thực. Đây là pixel ở scale tham chiếu X11, chưa chứng nhận native mixed DPI. [Bản ghi](benchmarks/application-icons-2026-10-29.json).


Kiểm terminal thật (29/10/2026): `/usr/bin/python3 tests/wayland_lab.py --terminal-test --output /tmp/deskmorph-terminal-launch/results.json` chạy trên GNOME Wayland riêng, tạo desktop entry Terminal=true và kích nút Mở của launcher DeskMorph bằng AT-SPI. GIO chọn COSMIC Terminal1.11.0 thật; Python con xác nhận ancestry emulator và cửa sổ Wayland có frame dương. Không có wrapper terminal giả. [Bằng chứng](benchmarks/terminal-launch-2026-10-29.json). G3.4 còn thiếu kiểm runtime ứng dụng đóng gói; export fixture chưa đủ để tuyên bố Flatpak/Snap đã kiểm thực tế.


Kiểm Snap runtime thật: `/usr/bin/python3 tests/wayland_lab.py --snap-test --output /tmp/deskmorph-snap-launch/results.json`. [Bằng chứng Chromium156](benchmarks/snap-runtime-launch-2026-10-29.json) đi qua nút Mở launcher/GIO tới `/snap/bin/chromium`, xác minh AppArmor/profile riêng và nội dung trang qua CDP, đóng browser và xóa profile. Entry lab bổ sung headless/profile/loopback-CDP và env user bus/runtime hệ thống để snapd tạo cgroup. Chưa chứng nhận cửa sổ Snap hoặc entry nguyên bản; G3.4 còn mở. Cần python3-websocket để chạy harness; không đổi dependency sản phẩm.
