# 📋 Kế Hoạch Cải Thiện Giao Diện DeskMorph (UI Action Plan)

> **Tài liệu kiểm định & chuẩn hóa giao diện DeskMorph**  
> Dựa trên tiêu chuẩn Art Direction & Anti-Slop của **Taste-Skill** (`lint.mjs` & `inspect.mjs`).  
> *Mục tiêu:* Loại bỏ toàn bộ các đặc điểm "AI-slop / template", chuẩn hóa typography, bảng màu phẳng (flat dark devtools), tối ưu trải nghiệm desktop cao cấp.

---

## 📌 Tổng Quan Tiến Độ

- [x] **Giai đoạn 1: Chuẩn Hóa Design Tokens & Typography** (Nền tảng) — *Đã hoàn thành*
- [x] **Giai đoạn 2: Sửa 25 Lỗi Nghiêm Trọng (FAIL)** (Khử Purple, Gradients, Emoji) — *Đã hoàn thành*
- [x] **Giai đoạn 3: Tái Cấu Trúc Bố Cục Studio** (Xóa khoảng trống chết `unused-canvas`) — *Đã hoàn thành*
- [x] **Giai đoạn 4: Tinh Chỉnh Cảnh Báo (WARN)** (Shadows, Glassmorphism, Monospace) — *Đã hoàn thành*
- [x] **Giai đoạn 5: Tích Hợp Mock Trình Duyệt & Nghiệm Thu (Gate Check)** — *Đã hoàn thành*

---

## 🛠️ Danh Sách Công Việc Chi Tiết

### 🔤 GIAI ĐOẠN 1: Chuẩn Hóa Design Tokens & Typography
*Mục tiêu: Đưa bộ font chuẩn vào ứng dụng, tăng cỡ chữ dễ đọc, thiết lập bảng màu dark devtools.*

- [x] **1.1. Nhúng font Inter / IBM Plex Sans vào HTML**
  - **File:** [`index.html`](file:///home/ducthanhdev/Documents/Projects/Tool-private/index.html)
  - Đã thêm `<link>` tải font `Inter` (weights 400, 500, 600, 700) từ Google Fonts.
- [x] **1.2. Nâng scale typography trong CSS**
  - **File:** [`src/App.css`](file:///home/ducthanhdev/Documents/Projects/Tool-private/src/App.css)
  - Đổi font chính sang `'Inter', system-ui, -apple-system, sans-serif`.
  - Nâng body font-size lên **14px** (line-height: 1.45).
  - Đặt font-size tiêu đề trang `h1`: **20px** (font-weight: 700).
  - Đặt font-size section label: **16px** (font-weight: 600).
  - Đặt font-size caption / sublines: **12px**.
  - Bật `font-variant-numeric: tabular-nums` cho số liệu, đồng hồ và RAM/CPU.
- [x] **1.3. Cập nhật hệ thống màu phẳng (:root Tokens)**
  - **File:** [`src/App.css`](file:///home/ducthanhdev/Documents/Projects/Tool-private/src/App.css)
  - `--ground: #0c0d10;` (nền tối dịu mắt, không ám tím).
  - `--surface: #14161b;` (nền card/panel làm việc).
  - `--raised: #1c1f26;` (nền hover, control).
  - `--border-subtle: #22252e;` (viền mảnh tinh tế, tương phản đạt chuẩn devtools).
  - `--accent: #48b9c7;` (cyan/teal công nghệ của DeskMorph).
  - Semantic status tokens: `--status-positive: #22c55e;`, `--status-warning: #f59e0b;`, `--status-negative: #ef4444;`.

---

### 🚨 GIAI ĐOẠN 2: Xử Lý 25 Lỗi Nghiêm Trọng (FAIL)
*Mục tiêu: Đạt 0 lỗi FAIL khi chạy `node .agents/skills/design-taste-frontend/scripts/lint.mjs`.*

- [x] **2.1. Loại bỏ Violet Accent (`#8b5cf6`, `#a855f7`, `#818cf8`)**
  - [x] [`src/App.css`](file:///home/ducthanhdev/Documents/Projects/Tool-private/src/App.css): Xóa biến `--accent-purple: #8b5cf6`, chuyển sang solid accent.
  - [x] [`src/Taskbar.tsx`](file:///home/ducthanhdev/Documents/Projects/Tool-private/src/Taskbar.tsx): Sửa launcher background gradient, đổi sang solid accent.
  - [x] [`src/components/studio/DockPreview.tsx`](file:///home/ducthanhdev/Documents/Projects/Tool-private/src/components/studio/DockPreview.tsx): Thay launcher gradient `#8b5cf6` bằng flat accent `#48b9c7`.
  - [x] [`src/components/DockParts.tsx`](file:///home/ducthanhdev/Documents/Projects/Tool-private/src/components/DockParts.tsx): Thay màu `#a855f7` thanh RAM bằng cyan `#38bdf8`.
  - [x] [`src/dockAppearance.ts`](file:///home/ducthanhdev/Documents/Projects/Tool-private/src/dockAppearance.ts): Đổi accent màu preset neon từ `#8b5cf6` sang `#38bdf8`.
  - [x] [`src/dockVisuals.tsx`](file:///home/ducthanhdev/Documents/Projects/Tool-private/src/dockVisuals.tsx): Thay `#818cf8` của icon Code thành màu accent xanh kỹ thuật `#38bdf8`.
- [x] **2.2. Xóa bỏ Radial & Linear Gradients**
  - [x] [`src/App.css`](file:///home/ducthanhdev/Documents/Projects/Tool-private/src/App.css): Xóa 2 `radial-gradient` phát sáng ở `.studio-app`.
  - [x] [`src/App.css`](file:///home/ducthanhdev/Documents/Projects/Tool-private/src/App.css): Xóa gradient trong `.logo-box`, dùng nền phẳng + icon sắc nét.
  - [x] [`src/App.css`](file:///home/ducthanhdev/Documents/Projects/Tool-private/src/App.css): Xóa gradient trong `.nav-badge`.
  - [x] [`src/App.css`](file:///home/ducthanhdev/Documents/Projects/Tool-private/src/App.css): Xóa gradient trong `.btn-primary`.
  - [x] [`src/App.css`](file:///home/ducthanhdev/Documents/Projects/Tool-private/src/App.css): Xóa gradient trong `.hero-wallpaper-card`.
- [x] **2.3. Sửa Gradient Text**
  - [x] [`src/App.css`](file:///home/ducthanhdev/Documents/Projects/Tool-private/src/App.css): Xóa `background-clip: text` ở `.brand-title`, dùng màu chữ phẳng `#ffffff` với trọng số 700.
- [x] **2.4. Thay ký tự Emoji bằng Vector Icon**
  - [x] [`src/components/studio/WallpaperSettings.tsx`](file:///home/ducthanhdev/Documents/Projects/Tool-private/src/components/studio/WallpaperSettings.tsx): Thay ký tự text `"★"` và `"☆"` bằng component vector SVG `StarIcon` (an toàn với Node data-url test runner).

---

### 📐 GIAI ĐOẠN 3: Tái Cấu Trúc Bố Cục Studio (Canvas & Void)
*Mục tiêu: Đạt 0 FAIL trên `inspect.mjs`, xóa bỏ khoảng trống chết 823px (`unused-canvas`) và 73% `hero-void`.*

- [x] **3.1. Dàn lại lưới Studio Content theo cấu trúc 2 cột**
  - **File:** [`src/App.css`](file:///home/ducthanhdev/Documents/Projects/Tool-private/src/App.css), [`src/Studio.tsx`](file:///home/ducthanhdev/Documents/Projects/Tool-private/src/Studio.tsx)
  - Áp dụng bố cục chuẩn của Settings Screen: Cột trái (Sidebar điều hướng Studio) 220px, Cột phải (Vùng làm việc/Preview/Settings) chiếm trọn chiều ngang còn lại.
  - Bổ sung Media Query `@media (max-width: 600px)` cho responsive màn hình nhỏ (chuyển sang bố cục cuộn 1 cột dạng wrap pills).
- [x] **3.2. Căn chỉnh lề an toàn (Edge padding)**
  - Đảm bảo toàn bộ văn bản và thông báo cách mép màn hình tối thiểu 20px–24px (tránh triệt để lỗi `edge-text`).

---

### 🧹 GIAI ĐOẠN 4: Dọn Dẹp Cảnh Báo (WARN) & Tối Ưu Hiệu Năng
*Mục tiêu: Loại bỏ các chi tiết thừa làm nặng giao diện.*

- [x] **4.1. Tắt Shadows ở trạng thái tĩnh (Resting state)**
  - **File:** [`src/App.css`](file:///home/ducthanhdev/Documents/Projects/Tool-private/src/App.css)
  - Bỏ `box-shadow` trên các nút bấm, stat chips, thẻ card, ô input khi không hover/focus.
  - Giữ đổ bóng nhẹ chỉ cho các thành phần bay (Dropdown Context Menu, Dialog, Tooltip, Flyout).
- [x] **4.2. Tiết chế Glassmorphism (Backdrop blur)**
  - Giảm thiểu `backdrop-filter: blur(...)` rải rác. Thay thế bằng màu nền bán trong suốt nhẹ hoặc màu phẳng `--surface` để tăng hiệu năng dựng hình trên Linux/WebKitGTK.
- [x] **4.3. Thay thế các mã màu Tailwind cứng**
  - Đồng bộ `#10b981`, `#f59e0b`, `#ef4444` về các biến `--status-positive`, `--status-warning`, `--status-negative`.
- [x] **4.4. Giới hạn Monospace đúng ngữ cảnh**
  - Thay `font-family: ui-monospace, monospace` trên nhãn CPU/RAM, đồng hồ bằng `font-variant-numeric: tabular-nums` trên font Inter để số liệu thẳng hàng mà không bị lệch font.
- [x] **4.5. Tối ưu thuộc tính Transition**
  - Thay toàn bộ các khai báo `transition: all` sang chỉ định rõ các thuộc tính cần animate (`transform`, `opacity`, `background-color`, `border-color`, `box-shadow`).

---

### 🧪 GIAI ĐOẠN 5: Tích Hợp Mock Dev & Kiểm Thử Nghiệm Thu
*Mục tiêu: Đảm bảo toàn bộ test suite pass và giao diện mượt mà cả trong browser lẫn native Tauri.*

- [x] **5.1. Bổ sung Mock IPC an toàn khi chạy chế độ Web Browser**
  - **File:** [`src/ipc.ts`](file:///home/ducthanhdev/Documents/Projects/Tool-private/src/ipc.ts), [`src/config/store.ts`](file:///home/ducthanhdev/Documents/Projects/Tool-private/src/config/store.ts), [`index.html`](file:///home/ducthanhdev/Documents/Projects/Tool-private/index.html)
  - Khi chạy ngoài môi trường Tauri native (`window.__TAURI_INTERNALS__` không tồn tại), hệ thống tự động kích hoạt `window.__BROWSER_INVOKE__` để trả về config snapshot và monitor info mẫu, loại bỏ hoàn toàn các banner cảnh báo đỏ.
- [x] **5.2. Chạy kiểm tra Linter & Inspector**
  ```bash
  # 1. Kiểm tra tĩnh: 0 FAIL, 32 WARN (Passed)
  node .agents/skills/design-taste-frontend/scripts/lint.mjs
  # 2. Kiểm tra render trên Chromium: 0 FAIL, 1 WARN (Passed)
  node .agents/skills/design-taste-frontend/scripts/inspect.mjs http://localhost:5173/ --app
  # 3. Kiểm tra tương phản màu sắc: 209/209 (Passed)
  python3 tests/contrast_audit.py --output /tmp/contrast.json --enforce
  # 4. Kiểm tra toàn bộ 59 unit tests hiện tại: 59/59 (Passed)
  npm test
  ```
- [x] **5.3. Nghiệm thu ảnh chụp màn hình (Visual Sign-off)**
  - Xác nhận ảnh chụp `.taste-skill/inspect/desktop-page-01.jpg`: Giao diện đạt chuẩn Anti-Slop, typography Inter chuẩn xác, bảng màu dark devtools hài hòa và chuyên nghiệp.

---
*Nghiệm thu hoàn tất ngày: 02/11/2026 bởi Antigravity Pair Programmer.*
