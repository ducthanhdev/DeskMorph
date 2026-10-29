# Mở ứng dụng và vị trí hệ thống

Popup chỉ cho phép ba thao tác `monitor`, `downloads`, `trash`. Giá trị khác trả `system_location_invalid`. Command chạy ngoài UI thread; UI khóa thao tác đang chờ và giữ lỗi có nội dung khi thất bại. Cấu hình MIME/user directories của desktop không bị sửa bởi chức năng này.

## System Monitor

Phát hiện desktop entry hiển thị được trong thứ tự: `org.gnome.SystemMonitor.desktop`, `gnome-system-monitor.desktop`, `org.gnome.Usage.desktop`, `org.kde.plasma-systemmonitor.desktop`, `plasma-systemmonitor.desktop`, `ksysguard.desktop`. Không ghép lệnh shell từ metadata hay đoán binary theo tên app.

Khi GIO từ chối khởi chạy, thử entry được hỗ trợ kế tiếp. Nếu không có entry, trả `system_monitor_missing`; tất cả launch bị từ chối trả `system_monitor_launch_failed` cùng các desktop ID/lỗi tương ứng. Dispatch được GIO chấp nhận không bảo đảm process sẽ sống hoặc tạo cửa sổ. Một process thoát sau dispatch không kích hoạt fallback vì không có bằng chứng launch rejection.

## Downloads

Đọc `G_USER_DIRECTORY_DOWNLOAD` qua GLib/XDG user directories; nếu chưa cấu hình thì dùng `~/Downloads`. Thư mục chưa tồn tại trả `downloads_missing`, không tự tạo hoặc đổi sang vị trí khác. Khôi phục thư mục rồi click lại có thể mở bình thường.

Chọn default `inode/directory` chỉ khi entry có category `FileManager` và hiển thị được; nếu không, dùng FileManager được phát hiện theo desktop ID ổn định. Cách này tránh chọn nhầm Disk Usage Analyzer chỉ vì nó là MIME default. Không có ứng dụng phù hợp trả `file_manager_missing`.

Truyền native `GFile` cho `GAppInfo.launch`, giữ desktop entry, wrappers, flags và quoting của executable. Không lấy riêng `GAppInfo.executable` để dựng lệnh: API đó có thể cắt sai executable có khoảng trắng và làm mất cờ/wrapper. GIO quyết định chuyển local file thành path hay URI cho entry; cả hai phải chỉ đúng thư mục XDG đã chọn.

## Thùng rác

Chỉ mở `trash:///` qua URI handler do desktop đăng ký, có hỗ trợ URI và không bị đánh dấu `Hidden`; handler `NoDisplay` vẫn hợp lệ. GIO có thể trả MIME default trỏ tới entry Hidden nên không chỉ kiểm tra Some/None. Dispatch dùng chính handler đã kiểm tra. DeskMorph không tự duyệt/xóa/khôi phục nội dung Trash. Thiếu handler trả `trash_unsupported` và UI vô hiệu nút kèm lý do. Máy tham chiếu chưa có production Trash handler được xác minh; fixture chỉ chứng minh dispatch URI và việc DeskMorph giữ nguyên dữ liệu test, không chứng minh một trình duyệt Trash cụ thể.

## Bằng chứng và tái hiện

Rust fixtures trong `system_widgets_fixtures.rs` chạy subprocess mới cho từng scenario vì GLib cache môi trường. Mỗi subprocess có HOME/XDG/PATH/MIME riêng và session bus không tồn tại; không thay môi trường của runner hoặc desktop. Bao phủ lựa chọn ưu tiên/Hidden/fallback/thiếu app, lỗi GIO Terminal khi private PATH không có terminal, custom Downloads có khoảng trắng/ký tự shell, quoted executable và argv, thư mục thiếu/file manager thiếu, Trash URI và dữ liệu sentinel còn nguyên.

`tests/systemPopup.test.mjs` chạy component thật với adapter có kiểm soát: capability disable/reason, lỗi cụ thể được dịch vi/en, ngăn request lặp trong lúc chờ và không ghi lỗi muộn khi popup không còn active. Native opt-in:

```sh
/usr/bin/python3 tests/desktop_smoke.py --system-locations-smoke
/usr/bin/python3 tests/desktop_smoke.py --system-open-smoke
```

Ca thứ nhất dùng desktop receivers và MIME/XDG riêng, chỉ mở GTK monitor fixture thuộc test; Downloads/Trash receiver ghi argv. Ca thứ hai kiểm file manager COSMIC Files thật trên desktop tham chiếu và chỉ đóng cửa sổ Downloads mới do ca kiểm thử tạo. Kết quả, phạm vi và cleanup nằm trong PROGRESS.md cùng benchmark liên quan.
