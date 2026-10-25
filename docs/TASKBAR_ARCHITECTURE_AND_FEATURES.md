# TÀI LIỆU PHÂN TÍCH VÀ ĐẶC TẢ TÍNH NĂNG TASKBAR & DOCK HỆ THỐNG
*(So sánh chi tiết Windows, macOS, Linux và Lộ trình phát triển DeskMorph)*

---

## 1. TỔNG QUAN VÀ MỤC ĐÍCH

Tài liệu này tổng hợp toàn bộ các tính năng, hành vi tương tác và cơ chế kỹ thuật của thanh tác vụ (**Taskbar / Dock**) trên 3 hệ điều hành lớn nhất thế giới hiện nay (**Microsoft Windows, Apple macOS, và Linux Desktop**).

Mục đích:
* Cung cấp bức tranh toàn cảnh về tiêu chuẩn thiết kế trải nghiệm người dùng (UX/UI) của thanh tác vụ máy tính để bàn.
* Đánh giá hiện trạng của **DeskMorph Taskbar** (thanh Dock tùy biến được xây dựng bằng Rust, Tauri 2, React, TypeScript).
* Định hình danh mục tính năng cần bổ sung để DeskMorph hội tụ những ưu điểm vượt trội nhất từ cả 3 nền tảng.

---

## 2. SO SÁNH KIẾN TRÚC TRÊN 3 HỆ ĐIỀU HÀNH

```
+---------------------------------------------------------------------------------------------------+
| 1. WINDOWS (All-in-One Taskbar)                                                                  |
| [Start] [Search] [Pinned & Running Apps Taskbar]                    [SysTray] [Clock] [ActionCtr] |
+---------------------------------------------------------------------------------------------------+

+---------------------------------------------------------------------------------------------------+
| 2. macOS (Kiến trúc kép: Menu Bar + Floating Dock)                                                |
| Menu Bar (Top):  [Apple] [App Menus]                                 [Menu Extras / Tray] [Clock] |
| Dock (Bottom):        [ [Finder] [Pinned Apps] | [Running Apps] | [Recent] [Folder] [Trash] ]     |
+---------------------------------------------------------------------------------------------------+

+---------------------------------------------------------------------------------------------------+
| 3. LINUX (GNOME / Pop!_OS COSMIC / KDE Plasma)                                                   |
| Top Bar / Panel: [App Grid / Activities] [Workspaces] [Clock]        [Status / Quick Settings]    |
| Dock / Panel:    [ [App Launcher] [Pinned Apps] [Active Windows] ]                                |
+---------------------------------------------------------------------------------------------------+
```

### 2.1. Windows (Triết lý Tất-Cả-Trong-Một)
* **Cấu trúc**: Toàn bộ các công cụ nằm liền mạch trên duy nhất 1 thanh ngang cố định ở cạnh dưới (hoặc tùy biến các cạnh trên Windows cũ).
* **Đặc trưng**: Tích hợp sâu Jump Lists (danh sách tệp xem gần đây), cửa sổ xem trước (Live Thumbnail Preview) khi rê chuột, thanh đo tiến trình tải file (% progress bar) trực tiếp trên icon ứng dụng.

### 2.2. macOS (Triết lý Phân Tách: Menu Bar & Floating Dock)
* **Cấu trúc**:
  * **Top Menu Bar**: Cố định ở mép trên màn hình. Chứa menu ngữ cảnh của ứng dụng đang mở (*File, Edit, View...*), trạng thái kết nối, pin, Control Center, Spotlight và Đồng hồ.
  * **Floating Dock**: Nổi ở mép dưới (hoặc trái/phải), tự co giãn kích thước theo số lượng ứng dụng.
* **Đặc trưng**: Hiệu ứng phóng to mượt mà dạng làn sóng khi rê chuột (*Magnification*), hiệu ứng nhún nhảy (*Bouncing animation*) khi mở app hoặc có thông báo, ngăn chứa thư mục mở nhanh (*Stacks/Folders*) và Thùng rác (*Trash*).

### 2.3. Linux Desktop (Triết lý Tự Do & Mô-Đun Hóa)
* **GNOME & Pop!_OS COSMIC**: Tách làm Top Bar (thanh thông tin hệ thống) + Dock nổi (Dash to Dock).
* **KDE Plasma**: Hệ thống widget linh hoạt nhất thế giới. Cho phép thêm/xóa panel, kéo thả widget hiệu năng máy (CPU/RAM/GPU), thêm khoảng cách (*spacers*), hỗ trợ chuẩn thông báo khay hệ thống *StatusNotifierItem*.

---

## 3. DANH MỤC TOÀN DIỆN CÁC TÍNH NĂNG TASKBAR & DOCK

### Nhóm 1: Quản lý Ứng dụng & Cửa sổ (Window & App Management)

1. **Ứng dụng được ghim (Pinned Apps / Keep in Dock)**:
   * Giữ icon các ứng dụng thường dùng luôn hiện diện trên thanh Dock.
   * Khi ứng dụng chưa mở: Bấm để khởi chạy (*Launch*).
   * Khi ứng dụng đã mở: Bấm để đưa cửa sổ lên trên cùng (*Focus/Activate*).
2. **Nhận diện trạng thái chạy (Running Indicators)**:
   * Dấu chấm sáng (*Dot*), vạch sáng (*Underline*) hoặc hiệu ứng phát sáng dải màu báo hiệu ứng dụng đang hoạt động trong bộ nhớ RAM.
   * Trạng thái phân biệt giữa: *Ứng dụng đang là tiêu điểm chính (Active Window)* và *Ứng dụng đang chạy nền (Background Window)*.
3. **Gom nhóm cửa sổ (Window Grouping / Stacking)**:
   * Khi mở nhiều cửa sổ của cùng một ứng dụng (ví dụ 4 cửa sổ Chrome, 3 cửa sổ terminal), hệ thống tự động gộp vào 1 icon duy nhất trên taskbar.
   * Nhấp chuột vào icon gom nhóm sẽ mở ra danh sách/thumbnail của từng cửa sổ con để chọn lựa.
4. **Xem trước hình thu nhỏ thời gian thực (Live Thumbnail Preview)**:
   * Khi rê chuột (*hover*) lên icon ứng dụng đang chạy, hiện một popup nhỏ hiển thị chính xác nội dung đang diễn ra trong cửa sổ đó (kể cả video đang chạy).
   * Cung cấp nút tắt nhanh cửa sổ (*Close Button*) ngay trên thumbnail xem trước.
5. **Menu ngữ cảnh thao tác nhanh (Jump Lists & Dock Options)**:
   * Bấm chuột phải vào icon để:
     * Xem danh sách tài liệu mở gần đây (*Recent Files*).
     * Mở tab mới / Tab ẩn danh (*New Window / Incognito*).
     * Bật/Tắt chế độ *Mở cùng hệ thống (Open at Login)*.
     * Buộc dừng ứng dụng (*Force Quit*).
     * Bỏ ghim khỏi thanh (*Unpin*).
6. **Thanh tiến độ tác vụ trực tiếp trên Icon (Progress Bar on Icon)**:
   * Hiển thị vạch màu xanh hoặc gradient chạy ngang thân icon khi tải tệp, sao chép dữ liệu hoặc xuất video (0% đến 100%).
7. **Huy hiệu số lượng thông báo (Badge Counters)**:
   * Vòng tròn màu đỏ ở góc trên icon hiển thị số lượng tin nhắn, email hoặc thông báo chưa đọc.
8. **Hiệu ứng hoạt họa (Animations)**:
   * **Bouncing Icon**: Icon nảy lên nhẹ nhàng khi ứng dụng bắt đầu khởi động hoặc khi ứng dụng có tác vụ cần người dùng can thiệp.
   * **Magnification**: Tự động phóng to icon khi con trỏ chuột lướt qua.
   * **Genie Effect / Scale Effect**: Cửa sổ uốn lượn hút vào icon khi thu nhỏ (*Minimize*).
9. **Ngăn ứng dụng vừa dùng (Recent / Suggested Apps)**:
   * Phân vùng tự động hiển thị 2–4 ứng dụng gần nhất vừa mở nhưng chưa được ghim.
10. **Kéo thả để mở tệp (Drag and Drop to Launch)**:
    * Kéo 1 file từ trình quản lý tệp thả thẳng lên icon ứng dụng trên Taskbar để mở tệp đó bằng phần mềm tương ứng.

---

### Nhóm 2: Khởi chạy, Tìm kiếm & Menu Hệ thống

1. **Trình đơn kho ứng dụng (Start Menu / Launchpad / App Grid)**:
   * Nút góc mở danh mục toàn bộ ứng dụng cài đặt trong máy tính, chia theo nhóm hoặc thư mục.
2. **Tìm kiếm toàn cục (Global System Search / Spotlight)**:
   * Thanh tìm kiếm nhanh ứng dụng, tài liệu, web, thực hiện phép tính toán học nhanh, chuyển đổi đơn vị ngoại tệ.
3. **Menu quản trị khẩn cấp (Quick Admin Menu - Win+X / Apple Menu)**:
   * Nhấp chuột phải vào nút Launcher mở nhanh: *Task Manager, Terminal, Device Manager, System Settings, Shutdown, Restart, Sleep*.

---

### Nhóm 3: Khay Hệ thống & Trung tâm Điều khiển (System Tray & Control Center)

1. **Khay biểu tượng ứng dụng chạy ngầm (System Tray / Menu Extras)**:
   * Hiển thị và quản lý các công cụ nền: bộ gõ tiếng Việt (Unikey/IBus), phần mềm chat (Telegram, Zalo, Discord), Steam, trình đồng bộ đám mây (Google Drive, Dropbox).
2. **Quản lý Mạng & Kết nối (Network & Internet)**:
   * Icon trạng thái Wi-Fi / Cáp mạng LAN / VPN. Bấm vào để quét mạng và kết nối tức thì.
3. **Điều khiển Âm lượng & Thiết bị xuất (Volume & Sound Device Switcher)**:
   * Thanh trượt chỉnh âm lượng nhanh, chọn nhanh đầu ra giữa Loa máy tính, Tai nghe Bluetooth, Cổng HDMI.
4. **Nguồn điện & Chế độ tiết kiệm pin (Battery & Power Profiles)**:
   * Báo % pin, thời gian sử dụng ước tính còn lại, thanh gạt chuyển giữa *Tiết kiệm pin (Power Saver)*, *Cân bằng (Balanced)* và *Hiệu năng tối đa (High Performance)*.
5. **Trung tâm cài đặt nhanh (Quick Settings / Control Center)**:
   * Bật/tắt 1-click: *Bluetooth, Đèn đêm chống mỏi mắt (Night Light / True Tone), Chế độ máy bay, Điểm phát sóng di động (Hotspot)*.
6. **Bộ gõ & Ngôn ngữ bàn phím (Input Method Switcher)**:
   * Hiển thị trạng thái ngôn ngữ gõ (EN, VI, JA...) và phím tắt chuyển nhanh.
7. **Chỉ báo bảo mật & riêng tư (Privacy Indicators)**:
   * Hiện chấm màu xanh lá cây hoặc cam khi Camera hoặc Microphone đang bị ứng dụng truy cập.

---

### Nhóm 4: Thời gian, Lịch, Thông báo & Giải trí

1. **Đồng hồ số thời gian thực & Lịch tương tác**:
   * Hiển thị giờ:phút:giây và ngày/tháng.
   * Nhấp chuột mở popup lịch tương tác, hiển thị lịch âm/dương và sự kiện.
2. **Trung tâm thông báo (Notification Center)**:
   * Lưu trữ lịch sử thông báo từ phần mềm và hệ thống, hỗ trợ trả lời nhanh tin nhắn hoặc nút *Clear All*.
3. **Chế độ tập trung (Do Not Disturb / Focus Mode)**:
   * Tắt toàn bộ âm thanh và biểu ngữ thông báo khi đang làm việc hoặc chơi game.
4. **Widget trình phát đa phương tiện (Now Playing Media Widget)**:
   * Tự động nhận diện bài nhạc/video đang phát (Spotify, YouTube, VLC...).
   * Cung cấp nút *Play, Pause, Next, Previous*, ảnh bìa album và thanh tua bài hát.

---

### Nhóm 5: Không gian làm việc, Đa màn hình & Thao tác nhanh

1. **Quản lý màn hình ảo (Virtual Desktops / Workspaces)**:
   * Phím tắt hoặc nút bấm chuyển nhanh giữa Desktop 1, Desktop 2, Desktop 3.
2. **Toàn cảnh cửa sổ (Task View / Mission Control)**:
   * Bung toàn bộ các cửa sổ đang chạy ra màn hình dạng lưới để người dùng tìm và chọn nhanh.
3. **Nút "Thu nhỏ toàn bộ về Desktop" (Show Desktop / Peek)**:
   * Nhấp chuột vào góc ngoài cùng để ẩn sạch sẽ mọi cửa sổ đang mở.
4. **Hỗ trợ đa màn hình (Multi-Monitor Support)**:
   * Tùy chọn hiển thị Taskbar/Dock trên tất cả các màn hình phụ hay chỉ giữ trên màn hình chính.
5. **Tự động ẩn thông minh (Auto-Hide / Intellihide)**:
   * Tự thu giấu thanh khi không rê chuột hoặc khi cửa sổ ứng dụng chạm vào vùng taskbar.
6. **Thùng rác & Thư mục nhanh trên Dock (Trash & Folders)**:
   * macOS cho phép ghim thư mục Downloads hoặc Thùng rác trực tiếp ở mép phải Dock.

---

## 4. BẢNG MA TRẬN SO SÁNH: WINDOWS vs macOS vs LINUX

| Tính năng cốt lõi | Windows 11 | macOS Sonoma/Sequoia | Linux (Pop!_OS / KDE) |
| :--- | :---: | :---: | :---: |
| **Ghim ứng dụng (Pinned Apps)** | ✅ | ✅ | ✅ |
| **Chấm trạng thái đang chạy (Running Dot)** | ✅ (Gạch chân) | ✅ (Chấm tròn) | ✅ (Chấm tròn / Vạch) |
| **Gom nhóm cửa sổ (Grouping)** | ✅ | ✅ | ✅ |
| **Live Thumbnail Preview khi hover** | ✅ **Rất mạnh** | ❌ (Dùng Exposé) | ✅ (KDE Plasma) |
| **Hiệu ứng Magnification (Phóng to hover)** | ❌ | ✅ **Đặc sản** | ✅ (Latte/Plank) |
| **Hiệu ứng Bouncing Icon (Nhún nhảy mở app)** | ❌ | ✅ **Đặc sản** | ✅ (KDE / GNOME) |
| **Thanh tiến độ % download trên icon** | ✅ | ✅ (Icon Downloads) | ✅ (Hỗ trợ qua D-Bus) |
| **Huy hiệu số thông báo (Badges)** | ✅ | ✅ | ✅ |
| **Ngăn chứa thư mục nhanh (Stacks)** | ❌ | ✅ **Cực mạnh** | ✅ (KDE Plasma) |
| **Thùng rác tích hợp trên Dock** | ❌ (Desktop) | ✅ | ✅ (Ubuntu Dock) |
| **Jump Lists (Chuột phải file gần đây)** | ✅ **Cực mạnh** | ✅ | ✅ (.desktop actions) |
| **Khay ứng dụng chạy ngầm (System Tray)** | ✅ | ✅ (Menu Bar) | ✅ (Panel / Tray) |
| **Widget Giám sát CPU/RAM trực tiếp** | ❌ (Cần tool ngoài) | ❌ (Cần app ngoài) | ✅ (KDE Widgets) |
| **Đổi hình nền 1-Click (Wallpaper Shuffle)** | ❌ | ❌ | ❌ (DeskMorph độc quyền) |
| **Tự động ẩn (Auto-Hide / Intellihide)** | ✅ | ✅ | ✅ |
| **Độ thẩm mỹ (Glassmorphism / Blur)** | Acrylic / Mica | Apple Vibrancy Blur | KWin Blur / Mutter Blur |

---

## 5. ĐÁNH GIÁ HIỆN TRẠNG DESKMORPH VÀ LỘ TRÌNH NÂNG CẤP

### 5.1. Các tính năng DeskMorph đã hoàn thiện xuất sắc (Live)
* [x] **Floating Glassmorphism Dock**: Giao diện kính mờ xuyên thấu, bo cong mềm mại, nổi trên màn hình.
* [x] **Hệ thống Pinned Apps**: Ghim các ứng dụng chính (Chrome, Code, Terminal, Files, Settings), tự động phân biệt giữa app chưa mở và app đang chạy.
* [x] **Khởi chạy ứng dụng 1-click**: Bấm vào icon ghim để khởi chạy app trực tiếp qua Linux subprocess.
* [x] **Nhận diện cửa sổ thời gian thực (X11 Client Message)**: Tự động bắt danh sách cửa sổ đang mở, hiển thị đèn báo trạng thái đang chạy (*running dot*) và đèn dạ quang tiêu điểm (*active glow*). Bấm vào icon để đưa ngay cửa sổ đó lên màn hình chính.
* [x] **Phân tách Pinned Apps & Unpinned Running Apps**: Hiển thị đường ngăn cách mượt mà giữa ứng dụng được ghim và các cửa sổ mở thêm khác.
* [x] **Giám sát hiệu năng hệ thống thời gian thực**: Đo và vẽ thanh % CPU, RAM sống động ngay trên Dock (tính năng vượt trội hơn cả Windows và macOS gốc).
* [x] **Đổi hình nền tức thì (Instant Wallpaper Shuffle)**: Tích hợp nút đổi ngẫu nhiên hình nền chất lượng cao từ thư viện máy.
* [x] **Đồng hồ số thời gian thực**: Hiển thị giờ:phút:giây và thứ/ngày/tháng.
* [x] **Cơ chế Auto-Hide thông minh & Tùy biến kích thước**: Cho phép chỉnh chiều cao từ 42px đến 74px, chỉnh bo góc, màu sắc, chế độ tự ẩn không để lại vạch mờ hay che khuất ứng dụng khác.

### 5.2. Lộ trình phát triển tiếp theo (Next Milestones)
* [ ] **Milestone 1 - Tương tác nâng cao**: Bổ sung hiệu ứng phóng to icon khi rê chuột (*Magnification*) và hiệu ứng nhảy nảy (*Bounce animation*) khi bấm mở ứng dụng.
* [ ] **Milestone 2 - Popup Lịch tương tác**: Bấm chuột vào widget Đồng hồ sẽ mở ra bảng lịch tháng nhỏ nhắn với các ghi chú nhanh.
* [ ] **Milestone 3 - Menu ngữ cảnh chuột phải (Context Menu)**: Chuột phải vào icon để hiện menu: *Mở cửa sổ mới, Đóng ứng dụng, Bỏ ghim*.
* [ ] **Milestone 4 - Gom nhóm nhiều cửa sổ cùng app**: Khi mở 3-4 cửa sổ trình duyệt, gom chung và hiển thị thumbnail xem trước khi rê chuột.
* [ ] **Milestone 5 - Tích hợp điều khiển Âm lượng / Media**: Nút chỉnh volume nhanh và điều khiển bài hát đang phát.

---

## 6. KIẾN TRÚC KỸ THUẬT CỦA DESKMORPH DOCK

* **Frontend**: React 18, TypeScript, Vanilla CSS (Design Tokens, Glassmorphism Backdrop Filter, GPU-accelerated CSS Transforms).
* **Backend Native Window**: Tauri 2 (Rust), WebKitGTK-4.1, Xlib (`libX11.so.6` FFI bindings).
* **Quản trị cửa sổ**:
  * Đọc cửa sổ: `xprop -root _NET_CLIENT_LIST` & `WM_CLASS`.
  * Nâng cửa sổ: X11 ClientMessage `_NET_ACTIVE_WINDOW` gửi đến root window với mask `SubstructureNotifyMask | SubstructureRedirectMask`.
* **Giám sát tài nguyên**: `sysinfo` crate (đọc trực tiếp `/proc/stat` và `/proc/meminfo` của Linux Kernel).
* **Đồng bộ sự kiện**: Tauri Event System (`emit` & `listen`) giúp truyền cấu hình từ Dashboard sang thanh Dock với độ trễ < 1ms.

---

## 7. KẾ HOẠCH KỸ THUẬT & DANH SÁCH MODULE CẦN BỔ SUNG ĐỂ HỢP NHẤT TOÀN DIỆN CẢ 3 HỆ ĐIỀU HÀNH

Để DeskMorph trở thành một thanh **"Super Dock / Unified Taskbar"** kết hợp trọn vẹn những điểm tinh hoa nhất của **Windows 11, macOS Sequoia và Linux (Pop!_OS/KDE)**, chúng ta cần bổ sung các module kỹ thuật sau:

```
+-------------------------------------------------------------------------------------------------------------+
|                                    DESKMORPH UNIFIED SUPER DOCK ARCHITECTURE                                |
+-------------------------------------------------------------------------------------------------------------+
| [MODULE 6]     | [MODULE 1 & 2]                              | [MODULE 3]     | [MODULE 4]  | [MODULE 5]    |
| App Launcher & | Pinned & Running Apps                       | Media & Audio  | System Tray | System Status |
| Spotlight      | • macOS Magnification & Bouncing            | • MPRIS Player | • D-Bus SNI | • CPU/RAM/Net |
| Search         | • Windows Grouping & Live Thumbnails        | • Volume/Sink  | • Unikey    | • Clock & Cal |
| (Toàn bộ Apps) | • Jump Lists & Context Menu (Chuột phải)    | • Pulse/Pipe   | • Telegram  | • Wallpaper 🔀|
+-------------------------------------------------------------------------------------------------------------+
```

---

### 7.1. Bảng phân tích khoảng cách công nghệ (Technical Gap Analysis)

| Module cần bổ sung | Mục tiêu tính năng | Học từ OS nào | Thư viện / Công nghệ cần tích hợp | Độ phức tạp |
| :--- | :--- | :---: | :--- | :---: |
| **1. Magnification Engine** | Icon phình to mượt mà dạng sóng khi rê chuột lướt qua Dock | **macOS** | React Hooks (`useSpring` / Gaussian Math) + CSS Transform | Trung bình |
| **2. Bouncing & Feedback** | Icon nảy tưng tưng khi click mở hoặc khi có cảnh báo | **macOS** | CSS Keyframes Animation + State Machine | Dễ |
| **3. Window Grouping & Jump List** | Gom nhóm nhiều cửa sổ cùng app + Menu chuột phải thao tác nhanh | **Windows** | X11 Client properties, `.desktop` actions parser | Trung bình |
| **4. Live Thumbnail Preview** | Rê chuột lên icon hiện hình thu nhỏ trực tiếp của cửa sổ | **Windows** | X11 Composite Extension (`libXcomposite`, `XShm`) | Nâng cao |
| **5. Audio & Media MPRIS Controller**| Mini widget chỉnh âm lượng + Điều khiển nhạc Spotify/YouTube | **Windows / macOS** | Linux D-Bus (`zbus` crate) + PulseAudio/PipeWire CLI | Trung bình |
| **6. System Tray Host** | Khay hiển thị icon các ứng dụng chạy ngầm (Zalo, IBus, Steam) | **Windows / Linux** | Giao thức D-Bus `org.kde.StatusNotifierWatcher` | Nâng cao |
| **7. Interactive Calendar Flyout** | Bấm vào đồng hồ bung popup lịch tháng âm dương, ghi chú | **Windows / macOS** | React Calendar Component + State Flyout Window | Dễ |
| **8. Spotlight App Launcher** | Bấm logo mở tìm kiếm ứng dụng, tệp tin và tính toán nhanh | **macOS (Spotlight) / Pop!_OS** | Quét thư mục `/usr/share/applications` + Fuzzy Search | Trung bình |

---

### 7.2. Đặc tả chi tiết 6 Module cốt lõi cần xây dựng

#### Module 1: Hiệu ứng Tương tác Cao cấp chuẩn macOS (Magnification & Animation Engine)
* **Nguyên lý toán học**: Khi con trỏ chuột ở vị trí $X_{mouse}$, bán kính ảnh hưởng $R \approx 120px$.
  Kích thước của icon thứ $i$ ở vị trí $X_i$ sẽ được tính theo hàm phân phối chuẩn (Gaussian) hoặc Cosine:
  $$\text{Scale}_i = 1 + (\text{MaxScale} - 1) \cdot \cos\left(\frac{|X_i - X_{mouse}|}{R} \cdot \frac{\pi}{2}\right)$$
  *(với $|X_i - X_{mouse}| \le R$)*.
* **Bouncing Launch Effect & Dynamic Floor Shadow**:
  * **Nảy icon (Squash & Stretch)**: Khi bấm vào icon chưa chạy, icon nảy lên với gia tốc vật lý tự nhiên (`translateY(-9px)`), kèm biến dạng nhẹ (co nén khi tiếp đất và kéo dài nhẹ khi bay lên).
  * **Bóng đổ & Vệt sáng tiếp xúc động (Dynamic Floor Glow/Shadow)**: Nằm ngay dưới chân icon trên mặt sàn kính Dock Glassmorphism:
    * *Khi icon nảy lên cao*: Vệt sáng/bóng đổ mờ đi (`opacity: 0.15`), thu nhỏ kích thước (`scale: 0.35`) và tán xạ mềm (`blur: 4.5px`), mô phỏng chân thực nguồn sáng và khoảng cách xa mặt đất.
    * *Khi icon chạm đất*: Vệt sáng đậm đặc (`opacity: 0.95`), loang rộng sang hai bên (`scaleX: 1.35`) kèm vệt sáng neon thương hiệu của ứng dụng phản chiếu lên mặt kính.
    * Đảm bảo tính đàn hồi cao mà không làm xô lệch bất kỳ phần tử lân cận hay mở rộng bounding box của Dock.

#### Module 2: Quản lý Cửa sổ Chuyên sâu chuẩn Windows (Window Grouping & Context Menu)
* **Gom nhóm thông minh**: Nếu người dùng mở 5 cửa sổ Google Chrome hoặc 3 file mã nguồn trong VS Code, thanh Dock chỉ hiển thị **1 icon duy nhất**. Icon này có 2 vạch sáng hoặc huy hiệu số `[3]` bên cạnh.
* **Menu ngữ cảnh (Context Menu / Jump Lists)**: Khi bấm chuột phải vào icon:
  * Mở cửa sổ mới (*New Window*).
  * Danh sách tài liệu mở gần đây (*Recent Files* được trích xuất từ `~/.local/share/recently-used.xbel`).
  * Tùy chọn: *Ghim vào Dock / Bỏ ghim*.
  * Đóng cửa sổ (*Close Window*) hoặc Buộc dừng (*Kill process*).
* **Live Thumbnail Preview**: Sử dụng kỹ thuật X11 Composite Snapshot để chụp ảnh thu nhỏ của cửa sổ và render trong một flyout popup nổi khi rê chuột vào icon.

#### Module 3: Bộ Điều khiển Âm thanh & Media (Audio Controller & MPRIS D-Bus)
* **Lắng nghe nhạc đang phát qua giao thức MPRIS**:
  * Các trình duyệt (Chrome, Firefox) và phần mềm nghe nhạc (Spotify, VLC) trên Linux đều gửi tín hiệu D-Bus lên `org.mpris.MediaPlayer2.*`.
  * DeskMorph backend (Rust) lắng nghe tín hiệu này để lấy: Tên bài hát, Tên ca sĩ, Ảnh bìa Album, Thời lượng bài hát.
  * Cung cấp các nút bấm: *Play / Pause, Next, Previous* ngay trên một widget thu nhỏ của Taskbar.
* **Điều chỉnh Âm thanh Hệ thống**:
  * Kết nối tới máy chủ âm thanh PulseAudio hoặc PipeWire (thông qua lệnh `pactl` hoặc crate `pulsectl-rs`).
  * Bấm vào icon loa sẽ bung slider kéo âm lượng mượt mà và nút đổi nhanh thiết bị đầu ra (Loa trong / Tai nghe Bluetooth).

#### Module 4: Khay Hệ thống D-Bus (System Tray / StatusNotifierItem)
* **Vấn đề trên Linux**: Các ứng dụng chạy ngầm như bộ gõ Tiếng Việt (IBus / Fcitx), Telegram, Discord, Steam giao tiếp với thanh taskbar qua giao thức **StatusNotifierItem (SNI)** của D-Bus.
* **Giải pháp cho DeskMorph**:
  * Đăng ký DeskMorph là một `StatusNotifierWatcher` trên Session Bus.
  * Khi các ứng dụng đăng ký tray icon, backend Rust sẽ nhận icon pixmap/tệp ảnh và menu hành động.
  * Frontend React hiển thị một cụm icon nhỏ gọn ở bên cạnh đồng hồ, bấm chuột trái để mở cửa sổ app, bấm chuột phải để hiện menu khay hệ thống.

#### Module 5: Popup Lịch Tháng & Thông báo (Interactive Calendar Flyout)
* **Popup khi bấm vào Đồng hồ**:
  * Thay vì chỉ hiển thị giờ tĩnh, khi người dùng nhấp chuột vào khu vực ngày giờ, một Flyout kính mờ tuyệt đẹp sẽ mở ra.
  * Hiển thị cuốn lịch tháng trực quan, có đánh dấu ngày hiện tại, tích hợp xem ngày Âm lịch (Việt Nam) và các ngày lễ.
  * Tích hợp đồng hồ đếm ngược (*Pomodoro Timer*) hỗ trợ tăng năng suất làm việc.

#### Module 6: Trình tìm kiếm & Mở ứng dụng toàn năng (Spotlight / App Launcher)
* **Quét ứng dụng máy tính**:
  * Backend Rust duyệt qua `/usr/share/applications` và `~/.local/share/applications`, đọc các file `.desktop` để trích xuất: Tên ứng dụng, Icon, Lệnh thực thi (`Exec`), Danh mục (`Categories`).
* **Giao diện tìm kiếm Spotlight**:
  * Nhấp vào icon DeskMorph (hoặc bấm tổ hợp phím tắt `Alt + Space` / `Super + Space`) sẽ bung thanh tìm kiếm nổi giữa màn hình.
  * Hỗ trợ tìm kiếm thông minh (*Fuzzy Search*): Gõ "chr" ra Google Chrome, gõ "term" ra Terminal, gõ "calc" hoặc phép tính "15 * 85" tính toán ra kết quả tức thì.

---

### 7.3. Lộ trình triển khai kỹ thuật khuyến nghị (Phased Roadmap)

```
GIAI ĐOẠN 1: TƯƠNG TÁC THỊ GIÁC & MENU CHUỘT PHẢI (Frontend-Driven)
├── Bổ sung hiệu ứng phóng to icon khi rê chuột (macOS Magnification)
├── Bổ sung hiệu ứng nảy icon khi mở (Bouncing Launch Animation)
└── Menu ngữ cảnh chuột phải trên icon (Mở cửa sổ mới, Ghim/Bỏ ghim, Đóng app)

GIAI ĐOẠN 2: CÁC FLYOUT WIDGET TIỆN ÍCH (Productivity Flyouts)
├── Popup Lịch tương tác khi click vào Đồng hồ (Calendar Flyout)
├── Slider điều chỉnh âm lượng nhanh (PulseAudio / PipeWire)
└── Widget điều khiển nhạc đang phát (MPRIS Media Controller)

GIAI ĐOẠN 3: QUẢN LÝ CỬA SỔ NÂNG CAO (Advanced Window Management)
├── Gom nhóm nhiều cửa sổ cùng 1 app (Window Grouping Stacking)
├── Cửa sổ xem trước thu nhỏ khi rê chuột (Live Thumbnail Previews)
└── Hiển thị thanh tiến trình download / tác vụ trên icon (% Progress)

GIAI ĐOẠN 4: TÍCH HỢP HỆ THỐNG SÂU (Deep OS Integration)
├── Khay hệ thống cho ứng dụng chạy nền (D-Bus StatusNotifierItem Tray)
├── Trình tìm kiếm ứng dụng và phím tắt toàn năng (DeskMorph Spotlight)
└── Hỗ trợ giao thức hiển thị Wayland Layer-Shell (Chuẩn bị cho tương lai Pop!_OS COSMIC)
```

