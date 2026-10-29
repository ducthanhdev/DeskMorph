# Gói Debian — development 0.1.0

Chọn `.deb` cho Ubuntu/Pop!_OS 24.04 amd64, môi trường build tham chiếu hiện tại. Đây là artifact development nội bộ, chưa có quyết định phát hành và chưa qua cài trên tài khoản/máy sạch. Không công bố hỗ trợ Ubuntu/Debian phiên bản khác từ build này. AppImage/RPM chưa được chọn hoặc kiểm chứng.

## Build và kiểm tra

```sh
npm ci
npm run package:deb
dpkg-deb --info src-tauri/target/release/bundle/deb/DeskMorph_0.1.0_amd64.deb
sha256sum src-tauri/target/release/bundle/deb/DeskMorph_0.1.0_amd64.deb
```

Build dùng frontend production và Rust release custom-protocol của Tauri, không dùng dev server. `tauri.linux.conf.json` chỉ bundle deb, thêm libX11/libXi/libxcb bên cạnh dependency GTK/WebKit/appindicator được Tauri tự phát hiện. x11-utils/pulseaudio-utils là Recommends: thiếu các công cụ này, tính năng tương ứng có trạng thái unavailable. Chưa có API tự kiểm cập nhật hoặc ký gói phát hành. [Manifest artifact](benchmarks/deb-artifact-manifest-2026-10-29.json) ghi commit nền, config/lockfile hashes, toolchain, OS và checksum; build có recipe chưa commit tại thời điểm đo nên không tuyên bố reproducible từ một commit sạch.

Tên file là `DeskMorph_0.1.0_amd64.deb`, tên package trong dpkg là **`desk-morph`**, executable `/usr/bin/deskmorph`. Desktop entry `/usr/share/applications/DeskMorph.desktop` có action Launcher và dùng `WEBKIT_DISABLE_DMABUF_RENDERER=1` giống hướng dẫn cài thủ công. Ba icon được đóng trong hicolor. Gói không tự tạo autostart hoặc xóa dữ liệu cá nhân; autostart vẫn là lựa chọn của người dùng trong Studio.

## Cài/gỡ trên máy đích

Sau khi các cổng release đạt, có thể dùng apt để giải dependency:

```sh
sudo apt install ./DeskMorph_0.1.0_amd64.deb
```

Thoát DeskMorph trước khi nâng cấp; xuất JSON dự phòng nếu đang có dữ liệu cần giữ. Nếu từng cài thủ công ở `~/.local/bin`, kiểm tra `command -v deskmorph` và desktop entry người dùng để tránh chạy nhầm binary cũ. Không tự xóa bản cài thủ công hoặc ghi đè custom shortcut của người dùng.

Trước khi gỡ, tắt autostart trong Studio rồi thoát app. Gỡ package bằng `sudo apt remove desk-morph`; các file do app tự tạo trong XDG config/data không thuộc package. Nếu từng đăng ký menu từ Studio, dùng hướng dẫn gỡ thủ công trong README cho riêng desktop entry đó. `purge` cũng giữ dữ liệu cấu hình cá nhân; không xóa wallpaper, cache hoặc pin của người dùng.

## Bằng chứng hiện có

[Kiểm thử dpkg](benchmarks/deb-package-2026-10-29.json) cài vào root/database riêng bằng bwrap user/PID/network namespace, host filesystem chỉ đọc. Kiểm dependency bằng bản sao status host, desktop-file-validate, decode ba PNG icon/payload, help native, nâng phiên bản từ gói tổng hợp `0.1.0~package-test`, cài lại cùng version, remove và purge. File package bị gỡ, bytes cấu hình mẫu giữ nguyên, host dpkg status không đổi. Gói tiền nhiệm dùng cùng payload nên không chứng minh migration từ bản phát hành cũ.

```sh
npm run verify:deb -- src-tauri/target/release/bundle/deb/DeskMorph_0.1.0_amd64.deb \
  --output /tmp/deskmorph-package-results/report.json
```

Harness từ chối package có maintainer scripts chưa được review. Nó chỉ dùng root bên trong user namespace, không yêu cầu hoặc dùng sudo để cài lên host. Cần bwrap và quyền user namespaces của hệ thống; môi trường sandbox có thể cần cho phép chạy namespace.

[Kiểm thử GUI release](benchmarks/deb-release-ui-2026-10-29.json) dùng executable trích nguyên từ gói, so SHA256 với payload dpkg. Chạy native Wayland trên GNOME46 headless riêng: cold/warm/search/Escape, Dock tắt, Close, lệnh mặc định Studio và GIO packaged desktop entry/action. Không coi đây là cài package trên máy sạch hoặc kiểm desktop menu được render trong một phiên đăng nhập mới. Lượt bổ sung dùng [HOME tài khoản sạch](benchmarks/deb-clean-account-2026-10-29/launcher.json), giữ nguyên checksum payload và đã qua cold/warm/search/Escape, menu GIO và Desktop Action trong phiên riêng; vẫn chưa chứng minh autostart sau đăng nhập hoặc nâng cấp từ bản phát hành tiền nhiệm.

G9.11 vẫn mở: cần tài khoản/máy sạch với dependency thực do apt giải, kiểm menu/icon/autostart trong phiên đó, và nâng cấp giữ dữ liệu từ artifact tiền nhiệm có ý nghĩa. G9.12 cũng mở: chưa chốt toàn bộ checklist/version ứng viên, ký/checksum phát hành, hoặc quyết định publish. Không tick cổng release chỉ vì `.deb` build và các ca lab qua.
