# Hình nền trên GNOME

Adapter sản phẩm hiện chỉ bật trên GNOME khi schema GSettings phù hợp có sẵn. Chưa xác minh adapter KDE/COSMIC. GNOME46 Wayland headless đã có kiểm pixel hình nền trong compositor riêng; chưa suy thành mọi phiên Wayland. Ma trận môi trường nằm trong [CAPABILITIES.md](CAPABILITIES.md).

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

SIGSTOP không phải system suspend. Ca này xác minh worker tiếp tục xử lý hạn quá hạn sau khi tiến trình ngừng chạy; chưa xác minh login/session/compositor hoặc clock hoạt động qua sleep thật. Kiểm thử sleep thật và thay đổi phần cứng vẫn là cổng còn mở, không được suy ra từ ca này.


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
