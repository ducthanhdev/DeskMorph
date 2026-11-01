# DeskMorph

DeskMorph là Dock tùy chỉnh cho Linux, kèm Studio để quản lý ứng dụng, giao diện, hình nền và tiện ích hệ thống. Ứng dụng ưu tiên trải nghiệm GNOME/X11 và không tự thay đổi các thiết lập hệ thống khi chưa có thao tác của bạn.

![Cửa sổ DeskMorph Studio](docs/images/studio.png)

> Dự án đang phát triển. Phạm vi đã kiểm chứng chi tiết nằm trong [PROGRESS.md](docs/PROGRESS.md); đây chưa phải bản phát hành đã qua toàn bộ kiểm thử nâng cấp/cài sạch.

## Tính năng chính

- Dock có thể ghim, mở và quản lý cửa sổ ứng dụng; có launcher, menu chuột phải, kéo thả sắp xếp và điều khiển bằng bàn phím.
- Hiện Dock ở màn hình chính, một màn hình cụ thể, hoặc tất cả màn hình trên GNOME/X11.
- Studio để đổi kích thước, màu sắc, vị trí trên/dưới, tự ẩn, widget đồng hồ, âm thanh, media, pin và mạng.
- Thư viện hình nền, yêu thích, lọc, shuffle và lịch đổi hình nền.
- Đổi màn hình chính trên GNOME/Mutter: GNOME hiện hộp thoại **Giữ thay đổi / Hoàn tác**; DeskMorph không tự tạo countdown cạnh tranh.
- Nhập/xuất cấu hình JSON, preset giao diện và hoàn tác những thay đổi trong Studio.

## Hỗ trợ hiện tại

| Môi trường | Trạng thái |
| --- | --- |
| Pop!_OS 24.04 / Ubuntu 24.04, GNOME 46, X11, x86_64 | Môi trường tham chiếu đã kiểm thử |
| GNOME/Mutter DisplayConfig | Đọc trạng thái màn hình; đổi primary khi desktop cấp quyền |
| PipeWire PulseAudio / PulseAudio | Âm thanh qua `pactl`; media qua MPRIS |
| COSMIC wallpaper config | Có adapter RON v1; KDE wallpaper chưa bật |
| Wayland, KDE, COSMIC session | Chưa công bố hỗ trợ native window management |

Xem [CAPABILITIES.md](docs/CAPABILITIES.md) để biết chi tiết các capability và giới hạn theo desktop.

## Cài nhanh bằng gói Debian

Khi bạn có file `.deb` phù hợp cho Ubuntu/Pop!_OS 24.04 amd64, cài bằng:

```sh
sudo apt install ./DeskMorph_0.1.0_amd64.deb
```

Sau đó mở **DeskMorph** từ menu ứng dụng. Chạy `deskmorph` lần nữa sẽ mở Studio của instance đang chạy, không tạo Dock thứ hai.

Để gỡ:

```sh
sudo apt remove desk-morph
```

Gói không xóa cấu hình cá nhân, pin hay cache của bạn. Hướng dẫn đóng gói và giới hạn artifact development nằm trong [PACKAGING.md](docs/PACKAGING.md).

## Cài từ source

Cần Node.js 22.12+, npm, Rust stable/Cargo và các thư viện native. Trên Ubuntu/Pop!_OS 24.04:

```sh
sudo apt install build-essential pkg-config libssl-dev libgtk-3-dev \
  libwebkit2gtk-4.1-dev libayatana-appindicator3-dev librsvg2-dev \
  libx11-dev libxi-dev libxcb1-dev patchelf x11-utils pulseaudio-utils
git clone git@github.com:ducthanhdev/DeskMorph.git
cd DeskMorph
npm ci
npm run tauri -- dev
```

Lệnh trên mở bản phát triển. Để build binary production từ source:

```sh
npm run build
cargo build --release --manifest-path src-tauri/Cargo.toml --features custom-protocol
install -Dm755 src-tauri/target/release/deskmorph "$HOME/.local/bin/deskmorph"
"$HOME/.local/bin/deskmorph"
```

Sau khi cài binary vào vị trí ổn định, mở Studio → **Hệ thống** để đăng ký vào menu ứng dụng hoặc bật tự khởi động. Không đăng ký binary trong thư mục build tạm, vì desktop entry sẽ trỏ sai đường dẫn sau khi dọn dẹp build.

## Cách dùng cơ bản

1. Mở Studio bằng cách chạy `deskmorph` hoặc chọn DeskMorph trong menu.
2. Trong **Dock**, bật/tắt Dock và chọn màn hình đặt Dock: chính, cụ thể hoặc tất cả.
3. Trong **Ứng dụng**, tìm ứng dụng và ghim vào Dock. Kéo thả icon hoặc dùng `Ctrl+Shift+Trái/Phải` để sắp xếp.
4. Trong **Giao diện** và **Hình nền**, chọn giao diện, preset, ảnh nền và lịch thay đổi.
5. Trong **Màn hình**, chọn màn logical đang hoạt động rồi bấm **Đặt làm màn hình chính**. Xác nhận hoặc hoàn tác trong hộp thoại GNOME.

Đóng Studio có thể vẫn giữ Dock nếu đã bật **Giữ Dock khi đóng Studio**. Chọn **Thoát DeskMorph** trong Hệ thống để thoát hoàn toàn.

## Dữ liệu và sao lưu

- Cấu hình: `${XDG_CONFIG_HOME:-~/.config}/com.ducthanhdev.deskmorph/config.json`.
- Studio có nhập/xuất JSON và bước xem trước thay đổi. Nên export bản sao trước khi nâng cấp thủ công.
- Cấu hình màn hình chính là của desktop, không nằm trong preset hay file cấu hình DeskMorph.

Nếu cần gỡ bản cài thủ công, tắt autostart và thoát ứng dụng trước, sau đó xóa binary và desktop entry của DeskMorph:

```sh
rm -f "$HOME/.local/bin/deskmorph"
rm -f "${XDG_CONFIG_HOME:-$HOME/.config}/autostart/deskmorph.desktop"
rm -f "${XDG_DATA_HOME:-$HOME/.local/share}/applications/deskmorph.desktop"
```

Những lệnh này giữ lại cấu hình và cache để bạn có thể cài lại sau này.

## Sự cố thường gặp

- **Không thấy Dock:** mở Studio, kiểm tra Đã bật Dock và màn hình đã chọn. X11 cần `xprop` và `DISPLAY` hợp lệ.
- **Cửa sổ WebKit trống:** thử `WEBKIT_DISABLE_DMABUF_RENDERER=1 deskmorph`.
- **Không đổi được màn hình chính:** chỉ GNOME/Mutter có DisplayConfig cấp quyền mới bật nút này. Dùng **Mở cài đặt màn hình hệ thống** nếu nút bị khóa.
- **Không có âm thanh:** kiểm tra `pactl info`; DeskMorph vẫn chạy khi PulseAudio/PipeWire PulseAudio không có.
- **Mở app lần nữa chỉ hiện Studio:** đây là hành vi single-instance bình thường.

## Phát triển và kiểm thử

```sh
npm test
npm run build
cargo test --offline --manifest-path src-tauri/Cargo.toml --lib
```

Native UI test là opt-in và chỉ nên chạy trên X11 đã mở khóa. Xem [PROGRESS.md](docs/PROGRESS.md), [ARCHITECTURE.md](docs/ARCHITECTURE.md) và [RELEASE_CHECKLIST.md](docs/RELEASE_CHECKLIST.md) trước khi coi một build là sẵn sàng phát hành.
