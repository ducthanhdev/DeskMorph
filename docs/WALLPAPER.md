# Hình nền GNOME và COSMIC

Adapter sản phẩm có GNOME GSettings và COSMIC RON v1 đã kiểm trên cosmic-bg1.11.0 (9520e16)/compositor8cb1802 lồng. KDE vẫn unsupported. COSMIC đã qua Studio Apply/error/Retry/Shuffle ở vi/en, tạo file cấu hình thiếu và pixel; chưa chứng nhận toàn phiên desktop hoặc scheduler COSMIC. GNOME46 Wayland headless đã có kiểm pixel hình nền trong compositor riêng; chưa suy thành mọi phiên Wayland. Ma trận môi trường nằm trong [CAPABILITIES.md](CAPABILITIES.md).

Lệnh apply kiểm tra đường dẫn local tuyệt đối, canonical path, giới hạn ảnh và decode trước khi ghi. Transaction GSettings kiểm tra quyền ghi, cập nhật cả `picture-uri` và `picture-uri-dark` nếu có, apply/sync rồi đọc lại giá trị. UI chỉ báo thành công sau kết quả backend; lỗi giữ thao tác để thử lại. Đây là xác nhận settings backend, không bảo đảm compositor đã vẽ từng pixel trên desktop.

Studio đọc lại hình nền mỗi ba giây khi đang hiển thị. Thay đổi bằng ứng dụng khác được phản ánh qua cùng đường đọc GSettings; ẩn Studio dừng polling UI, không dừng lịch backend.

## Quét thư viện

Scanner chạy trên worker ngoài UI, tối đa 20.000 mục duyệt, 5.000 ảnh và 100 issue trong một kết quả. Mỗi file tối đa 128 MiB và 100 triệu pixel; metadata được kiểm trước decode/thumbnail. Canonical path loại trùng root/file, không đi theo symlink thư mục con. Root symlink do người dùng chọn trực tiếp vẫn được canonicalize. Lỗi quyền đọc, file hỏng, symlink đứt hoặc thư mục mất được ghi thành issue, không làm mất các ảnh còn đọc được. Ảnh có metadata hợp lệ nhưng payload hỏng vẫn có thể xuất hiện trong thư viện; thumbnail/apply decode sẽ báo lỗi riêng.

Mỗi scan có request ID và generation. Lượt mới hoặc hủy đúng request làm generation cũ mất hiệu lực; cleanup cũ không hủy request thay thế. Worker kiểm hủy trong traversal và trước publication. Bước kiểm cuối và ghi danh sách ảnh được phép tạo thumbnail dùng cùng khóa với begin/cancel để không công bố sau khi đã bị hủy. Danh sách của lần quét thành công trước được giữ nếu lượt mới bị hủy. UI cũng bỏ completion/finally của effect đã disposed; retry lỗi tạo request mới.

Rust fixture dùng quyền Unix thật để kiểm thư mục không đọc được, sparse file >128 MiB, PNG IHDR/CRC >100 megapixel, 5.001 ảnh, trần issue và 20.001 mục. Cancellation được thử giữa traversal, request cũ đang chờ worker, cleanup cũ và hủy request mới. Test component thật với React/IPC adapter có kiểm soát chứng minh kết quả cũ không ghi đè kết quả mới, lỗi có retry và unmount không nhận completion muộn. Đây không phải đo độ trễ IPC trên desktop chậm. Native `--library-stress` kiểm thư viện 5.001 ảnh, notice giới hạn và pagination 24 ảnh mỗi trang.

Scheduler khởi động một worker trong vòng đời ứng dụng. Thay đổi bật/tắt, chu kỳ hoặc thư mục đánh thức worker và đổi epoch. Trước khi ghi, worker kiểm tra lại epoch/cấu hình trên GTK main thread. Deadline dùng Unix wall clock; khi quá hạn chỉ thử một lần, sau đó tính hạn mới từ lúc hoàn tất, không chạy bù mọi chu kỳ. Khi đồng hồ lùi, hạn chạy được đặt lại. Mỗi lượt quét lại thư mục; ảnh bị xóa không được giữ làm danh sách ứng viên cũ. Lượt lỗi giữ nguyên hình nền, hiển thị lỗi và tiếp tục thử ở hạn kế tiếp.

## Kiểm thử native có chủ đích

Chạy trong GNOME/X11 đã mở khóa với instance có `DESKMORPH_CONFIG_HOME=/tmp/deskmorph-desktop-test/config`:

```sh
/usr/bin/python3 tests/desktop_smoke.py --scheduler-recovery-smoke
```

Ca này dùng hai PNG riêng, kiểm tra cả hai khóa GNOME, phản ánh hai lần thay đổi từ bên ngoài, deadline một phút khi Studio đóng và mở lại cùng instance. Sau đó tạm dừng riêng PID ứng dụng test bằng SIGSTOP 125 giây, SIGCONT, kiểm tra thay đổi khi quá hạn và không đổi tiếp trong mười giây. Xóa hai PNG để tạo lỗi ở deadline kế tiếp, khôi phục ảnh để xác minh tự phục hồi mà không bật/tắt lại. Có watchdog SIGCONT riêng, cùng finally khôi phục ảnh, tắt lịch, thư viện/cấu hình và hai URI hình nền ban đầu.

SIGSTOP không phải system suspend; nhánh mặc định chỉ xác minh process pause. Nhánh opt-in dưới đây gọi `systemctl suspend` và cần người đánh thức sau ít nhất125s, rồi mở khóa desktop:

```sh
DESKMORPH_REAL_SUSPEND=1 python3 tests/desktop_smoke.py --restart --scheduler-recovery-smoke
```

[Ca native GNOME X11 đầy đủ](benchmarks/scheduler-suspend-2026-10-30/result.json) ngủ thật138,922s, đo bằng BOOTTIME−MONOTONIC, đã qua resume/missing-image/recovery/disable và finally khôi phục cả hai URI/config/thư viện. Harness mở Chi tiết của đúng scheduler alert để đọc diagnostic gốc sau bản địa hóa, lưu checkpoint nếu bước sau thất bại. Chốt G6.7 trong môi trường này; không suy thành scheduler COSMIC, mọi compositor hoặc soak dài hạn đạt.


## Hình nền hiển thị trên GNOME46 Wayland

[Bằng chứng và tám ảnh chụp stage](benchmarks/wallpaper-visible-2026-10-29/results.json) từ `/usr/bin/python3 tests/wayland_lab.py --wallpaper-test --output /tmp/deskmorph-wallpaper-visible/results.json`: UI DeskMorph thật Apply image01 (hồng), lỗi file mất rồi Retry image02 (xanh), đọc cả khóa URI sáng/tối và đối chiếu3 pixel nền thực với RGB nguồn, tolerance2/channel. Thu nhỏ riêng cửa sổ thuộc PID lab trước chụp và khôi phục sau đó. Cả vi/en, reduced motion, GNOME Shell46.0/Mutter46.2, output ảo1280×720 scale1.

Sau Apply/Retry, ca phân biệt key đặt URI sáng về ảnh hồng trong keyfile lab, giữ URI tối xanh và đổi color-scheme prefer-dark/default. Pixel stage lần lượt xanh/hồng, chứng minh compositor chọn đúng key chứ không chỉ settings ghi thành công. Đây là thao tác test bên ngoài app trong môi trường riêng, không phải app viết hai URI khác nhau. Không chụp hoặc đổi wallpaper desktop host; mọi process/mount portal lab đã dọn. G6.9 còn các desktop khác chưa được xác minh; không bật adapter COSMIC/KDE từ kết quả GNOME.


## Khảo sát COSMIC, chưa bật adapter

[Ca chạy và ảnh nền thực](benchmarks/cosmic-background-2026-10-29/results.json): `cosmic-comp` backend winit lồng trên GNOME Wayland lab, `cosmic-bg`1.11.0 (9520e16), compositor commit8cb1802. Cả XDG config/runtime và bus đều riêng; không dùng session COSMIC của người dùng. Khóa `cosmic/com.system76.CosmicBackground/v1/all` chứa RON với `source: Path("…")`, `same-on-all=true`. Ảnh hồng được đọc lúc startup; atomic replace file all sang ảnh xanh làm nền đổi khi cùng PID cosmic-bg còn chạy, đối chiếu3 pixel stage/tolerance2 và ảnh đã xem. Không cần chạy cosmic-settings-daemon trong ca này.

Đây là API research; sản phẩm vẫn báo unsupported trên COSMIC. Trước khi bật cần adapter đọc/ghi RON giữ nguyên field chưa biết, xử lý per-output và same-on-all, nguồn không phải Path, lỗi quyền/ảnh, concurrent write/rollback, rồi kiểm xuyên UI/IPC trong COSMIC. Không dùng regex của fixture để sửa config người dùng. KDE chưa có compositor/runtime trên máy tham chiếu, chưa có bằng chứng API.


### Chuẩn bị bộ sửa RON (29/10/2026)

`src-tauri/src/cosmic_background.rs` dùng RON 0.12.3 và RawValue mượn từ văn bản gốc để chỉ thay vùng `source`. Các byte bên ngoài vùng đó, bao gồm comment và field enum chưa biết, được giữ nguyên. Hiện chỉ nhận `output: "all"` và `Path` tuyệt đối UTF-8 không chứa NUL; từ chối field bắt buộc thiếu/trùng, nguồn khác Path, per-output, cú pháp sai và văn bản vượt 64 KiB. Chưa nối module này với capability hoặc command.

I/O thử nghiệm yêu cầu file thường (không symlink tại lúc kiểm), có etag; replace dùng etag cũ, không backup, rồi đọc đối chiếu. Regression kiểm external edit bị từ chối mà không mất byte mới, ghi thường giữ mode 0600 và symlink bị từ chối. Đây chưa phải bảo đảm giao dịch chống mọi race: kiểm metadata và đọc file là hai bước, etag phụ thuộc backend/filesystem; thay đổi sau replace có thể trả lỗi dù dữ liệu đã được ghi. Chưa xử lý owner/parent symlink, fallback mặc định, same-on-all/per-output, rollback hoặc xác thực ảnh tại lớp này. Không dùng trực tiếp lên cấu hình người dùng trước khi hoàn tất adapter và ca tích hợp riêng.

Lệnh regression: `cargo test --locked --offline --manifest-path src-tauri/Cargo.toml --target-dir src-tauri/target/agent --lib cosmic_background::tests::`. Giữ ba test nguồn vì bảo vệ nội dung cấu hình, escaping và xung đột ghi; không cần thêm báo cáo JSON hay log sinh ra cho các ca này.


### Cấu hình từng màn hình và sửa cô lập state (29/10/2026)

Nguồn [config/src/lib.rs](https://github.com/pop-os/cosmic-bg/blob/9520e16758693bc2f6845d52680f236d548edda2/config/src/lib.rs) đúng commit cosmic-bg đã cài xác định `backgrounds` là danh sách tên output, file `output.<tên>` là Entry tương ứng; `all` là fallback. Khi khởi động với same-on-all=true, danh sách riêng không được nạp. Với false, Entry khớp tên output ưu tiên hơn fallback. Source thực tế còn có Color; Path có thể chỉ thư mục nên không suy mọi Path là ảnh tĩnh hợp lệ.

[Bằng chứng per-output](benchmarks/cosmic-per-output-2026-10-29/results.json) dùng tên WINIT-0 đọc từ state riêng: fallback xanh + entry riêng hồng hiển thị hồng; thay riêng sang xanh hiển thị xanh mà không restart; dừng background, đặt all hồng/same-on-all=true rồi khởi động lại hiển thị hồng dù entry riêng vẫn xanh. Chưa chứng minh live toggle same-on-all, nhiều output hoặc hotplug.

Audit phát hiện lượt COSMIC cũ chưa đặt XDG_STATE_HOME: cosmic-bg đã thêm WINIT-0 trỏ ảnh lab vào file state wallpapers host. Không có snapshot trước nên không tự sửa/xóa state hoặc tuyên bố phục hồi nguyên trạng. Chưa phát hiện thay config wallpaper host; không dùng điều đó để phủ nhận tác động state. Harness nay tạo state riêng, truyền cả vào môi trường D-Bus activation, kiểm cosmic-bg thực sự ghi dưới root lab và so hash riêng file wallpapers host trước/sau. Báo cáo cũ được bổ sung đính chính, không xóa bằng chứng pixel. Lượt mới xác nhận state host không đổi trong thời gian chạy; không đại diện cho mọi file host.


### Native RON/GIO write đã qua cosmic-bg watcher (29/10/2026)

Bộ sửa giờ nhận expected output, đối chiếu `Entry.output` trước sửa, hỗ trợ Path (ảnh hoặc thư mục), Color/Single và Color/Gradient theo schema cài thực tế. Color trả None khi hỏi đường nguồn, không giả một đường ảnh. Thay sang Path mới vẫn chỉ sửa đúng vùng source; giữ scaling/filter/rotation và byte khác. Màu non-finite/cú pháp lạ bị từ chối. Các float RGB array trong RON dùng tuple `(r, g, b)`, không phải list; fixture đầu dùng nhầm list đã bị parser từ chối và được sửa theo serialization của schema.

`target_outputs` lập danh sách cho thao tác đổi toàn bộ nền của app: same-on-all=true chỉ all; false gồm all và danh sách backgrounds, giữ nguyên mode/list người dùng. Giới hạn64 output và64KiB/document, từ chối tên trống/trùng/all/đường dẫn hoặc ký tự điều khiển. Đây là hàm lập kế hoạch thuần, chưa đọc defaults, chưa điều phối ghi nhiều file hoặc bảo đảm transaction.

[Bằng chứng mới](benchmarks/cosmic-native-edit-2026-10-29.json) chạy lại5 pha pixel trên cosmic-bg thật; hai lần đổi sống all và output.WINIT-0 nay dùng chính Document::load_output/write_source Rust/GIO, không dùng regex fixture để ghi. Harness gọi một Rust test opt-in có guard root/tmp/config/state/output; assert byte đọc lại khớp trước khi kiểm compositor. Rust71 qua/5 ignored ở suite thường; riêng native_lab_edit được gọi và qua2 lần trong lab. Không suy đây là UI/IPC DeskMorph. State host wallpapers hash giữ nguyên và process/mount riêng đã dọn.

Adapter vẫn unsupported. Còn ownership/parent symlink và race đọc/ghi, cấu hình mặc định khi user file thiếu, preflight + lỗi/khôi phục nhiều file, rồi nối command/capability và kiểm Apply/Retry/Shuffle/scheduler qua UI trước bật. Không tự restart cosmic-bg của người dùng; restart trong harness chỉ tác động tiến trình lab.


### Preflight và phục hồi cấu hình COSMIC nhiều file (29/10/2026)

`cosmic_profile::Plan::load_existing` đọc mode/output-list cùng toàn bộ entry trước khi lập thay đổi. Mỗi file đọc tối đa64KiB+1 bằng O_NOFOLLOW/O_NONBLOCK, kiểm file thường, owner=euid, một hardlink, không world-writable; parent trực tiếp cũng thuộc user/không world-writable. Từ chối ancestor symlink; snapshot giữ dev/inode/size/uid/gid/mode/link/mtime/ctime, identity ancestor, etag và byte. Group-writable vẫn được phép (umask002 của môi trường tham chiếu), không diễn giải thành chống mọi writer cùng group.

Commit kiểm lại mọi snapshot trước ghi, kiểm mode/list trước mỗi bước và cuối lượt. GIO replace dùng etag, giữ quyền; mỗi receipt kiểm byte/etag/owner/group/mode/link và ancestor trước nhận thành công. Nếu lỗi bước sau, phục hồi ngược các receipt khi chúng vẫn khớp byte/etag vừa ghi. Không ghi đè sửa đổi bên ngoài lúc phục hồi. Lỗi GIO không trả receipt được coi outcome uncertain; dù các receipt trước đã phục hồi, không tuyên bố rollback đầy đủ cho file lỗi. Native lỗi quyền thực có regression riêng; injected failures kiểm phục hồi byte0600 và partial state khi external edit.

[Bằng chứng](benchmarks/cosmic-batch-write-2026-10-29.json):79 Rust qua/5 ignored ở suite thường;8 test profile bảo vệ preflight, sửa cùng kích thước, lỗi giữa chừng, quyền thật, xung đột sau ghi, external edit lúc rollback, thay thư mục/FIFO và symlink/hardlink/size/permission. Native test opt-in chạy2 lần trong lab; lượt batch ghi all + output.WINIT-0, đọc lại cả hai rồi xác minh pixel cosmic-bg. Host state wallpapers hash giữ nguyên, process/portal dọn.

Chưa phải giao dịch nguyên tử nhiều file: compositor có thể thấy trạng thái trung gian, GIO có thể fallback ghi in-place trên một số lỗi/quyền/filesystem. Chưa có journal phục hồi khi crash hoặc bảo đảm durability/power-loss. Kiểm path/snapshot có cửa sổ TOCTOU trước GIO replace; không công bố chống race độc hại giữa từng syscall. Thiếu user config vẫn từ chối, chưa tự tạo từ system defaults. Chưa bật capability/IPC; phần này cần tích hợp defaults/kiểm schema đầy đủ và test UI trước công bố hỗ trợ COSMIC.


## Adapter COSMIC qua Studio/IPC (29/10/2026)

Các phần research/preparation phía trên là lịch sử; trạng thái hiện tại đã nối availability/current/apply/shuffle/scheduler dispatch cho token COSMIC chính xác, giữ nhánh GNOME. Có cosmic-bg và cấu hình đọc/ghi hợp lệ mới bật capability; desktop khác vẫn unsupported. COSMIC filesystem apply/shuffle/scheduler chạy trên worker, GNOME giữ GSettings trên GTK main context. Scheduler COSMIC dùng cùng logic nhưng chưa có ca deadline/sleep thực trên COSMIC; không suy từ Apply/Shuffle.

Resolver dùng XDG_CONFIG_HOME (fallback HOME/.config), chọn directory schema đầu tiên tồn tại theo XDG_DATA_HOME rồi XDG_DATA_DIRS (/usr/local/share:/usr/share khi rỗng), tương ứng libcosmic430f3d48 của cosmic-bg đã cài. User override luôn ưu tiên; sai hoặc không đọc được thì báo wallpaper_config_invalid, không tự ghi đè. File mặc định hệ thống sai schema được thay bằng Entry::fallback đã đối chiếu nguồn đúng version. File all cài thực tế chứa #true và RON0.12.3 ở app từ chối; resolver dùng fallback builtin cùng các trường/theme/rotation/scaling. Nguồn cosmic-bg dùng RON0.12.2 và Context::default_background chọn builtin khi parse lỗi; không chạy bộ parser0.12.2 độc lập trong lượt này. Không dùng regex thay #true trong cấu hình người dùng.

Đọc capability/current không tạo file. Khi Apply, entry thiếu lấy mặc định all (hoặc clone all với output identity riêng), sửa sang ảnh đã được prepare_wallpaper kiểm tồn tại/decode/giới hạn. File tạm0600 cùng directory được ghi/sync trước publish bằng hard-link không thay thế đích, gỡ temp rồi xác minh. Một writer khác tạo đích làm thao tác thất bại thay vì ghi đè. Directory mới0700; rollback file vừa tạo chỉ gỡ khi receipt còn khớp, directory rỗng có thể còn lại. Không tạo same-on-all khi chỉ cần giữ fallback true.

Nếu entry per-output được tạo mới, cosmic-bg chỉ cập nhật entry đã có trong map khi nhận output.* event. Adapter vì vậy publish lại backgrounds cuối lượt với byte không đổi để nạp danh sách. Giao dịch vẫn không nguyên tử nhiều file; compositor có thể thấy trạng thái trung gian. Phục hồi hiện bảo vệ file cấu hình, chưa bảo đảm rollback hình đang cache trong compositor sau mọi lỗi/crash; không có journal/power-loss guarantee, TOCTOU quanh pathname GIO vẫn còn. Lỗi ghi chưa xác minh dùng wallpaper_write_unverified với hướng dẫn kiểm hình nền và thiết lập từng màn hình trước Retry, không hứa đã phục hồi hoàn toàn.

[Bằng chứng cuối](benchmarks/cosmic-studio-2026-10-29/results.json): app production trên socket COSMIC con, AT-SPI action qua UI/Tauri IPC, không renderer injection/giả IPC. vi tạo all thiếu; en tạo output.WINIT-0 thiếu khi mode false/list còn nguyên, refresh list được chứng minh bằng pixel. Mỗi ca chờ status hoàn tất qua AT-SPI Text và source trước dừng riêng app để chụp nền không bị cửa sổ che. Apply hồng →xóa blue/lỗi/không đổi nguồn→khôi phục/Retry xanh→Shuffle loại xanh thành hồng. Native keyboard/focus chưa được tuyên bố từ các action này. Config invalid/read-only có ca UI disabled và thông báo vi/en, không sửa nội dung đang lỗi.

Rerun: `npm run build`, native custom-protocol build, rồi `/usr/bin/python3 tests/wayland_lab.py --cosmic-test --output /tmp/deskmorph-cosmic-ui/verified.json`. Cần GNOME46 headless, cosmic-comp/cosmic-bg cài đúng schema, GTK/WebKit/AT-SPI và target Rust đã có. Không cài/chuyển phiên desktop host. Profile, config/state/bus/runtime riêng, hash riêng file wallpapers host trước/sau bằng nhau, mọi process/portal lab đã dọn. Báo cáo có version/binary/source hash và giới hạn; không phải release artifact.
