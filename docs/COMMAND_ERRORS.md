# Lỗi command và thử lại

Mọi `invoke` của UI đi qua `src/ipc.ts`. Adapter chuyển rejection thành `CommandError` có `code`, `message`, `command`, `context`. Native đang có cả chuỗi lỗi và object; adapter giữ mã có sẵn (`app_missing: …`, `{code,message}`), lỗi chưa có mã nhận `<command>_failed`. Không cần đổi toàn bộ wire format native cùng lúc. `convertFileSrc` vẫn dùng API gốc. String hiển thị gồm thông điệp và `[mã; command]`, tránh `[object Object]` và giúp xác định thao tác thất bại. Context không tự chép invoke arguments vào log/thông báo.

Dock tách lỗi enumerate cửa sổ khỏi lỗi thao tác: poll thành công không xóa lỗi launch/shuffle. Thông báo nằm trong chiều cao native Dock, nhận chuột, có vùng cuộn khi dài; giữ Dock hiện khi còn lỗi. Thử lại dùng đúng command/path đã thất bại; đóng thông báo không chạy lại lệnh. Launcher giữ app thất bại độc lập với kết quả tìm kiếm mới để vẫn thử lại desktop ID đó. Native popup coordinator và lifetime/generation vẫn quản lý đóng popup.

Hình nền tách lỗi thao tác khỏi lỗi thư viện và polling. Đường dẫn ảnh thất bại được giữ để thử lại; shuffle thất bại thử shuffle lại. Chỉ hiển thị đã áp dụng khi backend xác minh GNOME nhận URI. Ảnh biến mất sau scan không đổi URI hiện tại và không báo thành công. Thư viện có nút thử quét lại.

Lưu cấu hình có hai kết quả lỗi khác nhau:

- Chưa persist: giữ cấu hình/revision trước đó, UI giữ lỗi và nút Thử lại gửi lại patch/mutation/document ban đầu. Retry gửi expectedRevision từ trước lần thất bại; backend kiểm tra dưới mutex và từ chối nếu cửa sổ khác đã đổi cấu hình. Review import cũng giữ expectedRevision nên không tự bỏ qua xung đột.
- Đã persist nhưng native apply/broadcast lỗi: backend gửi `context: {persisted: true, revision}` và thông điệp nêu rõ đã lưu. Snapshot vẫn được phát kể cả layout configure lỗi. Thử lại gọi `retry_config_apply` với snapshot mới nhất dưới config mutex, không ghi thêm revision và không phát lại toggle/move/import. Kiểm thử đơn vị giả lập trường hợp này; chưa inject lỗi window manager thật để ép nhánh apply lỗi.

Snapshot event không tự xóa lỗi thao tác. Retry cấu hình có khóa để hai click liên tiếp không gửi mutation hai lần. Một thao tác lưu thành công tiếp theo xóa lỗi cũ trong cùng cửa sổ.

Không diễn giải mọi `false` là lỗi: tắt autostart hợp lệ trả false, popup generation cũ có thể trả false. Launch trả true chỉ xác nhận hệ thống đã nhận dispatch/spawn; không chứng minh process sẽ tiếp tục chạy hay tạo cửa sổ. GIO Desktop Action không có API trả lỗi downstream. Không tự retry tác vụ gây side effect; người dùng chủ động bấm Thử lại.

Kiểm thử: `npm test`, build frontend/custom-protocol, native Rust suite và `tests/desktop_smoke.py --restart --command-errors-smoke`. Native harness dùng hồ sơ `/tmp/deskmorph-desktop-test`, executable ghi marker, desktop entry riêng, thư mục config chmod tạm và ảnh bị xóa sau scan; finally khôi phục quyền thư mục, cấu hình và cả hai URI hình nền GNOME. Click Retry Dock thực hiện qua XTest với guard desktop unlocked/focus/PID/pointer. Nhánh persist-apply lỗi và double-click retry dùng kiểm thử đơn vị với backend giả lập; không tuyên bố đã gây lỗi window manager thật.
