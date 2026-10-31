# Kế hoạch đổi màn hình chính của hệ điều hành

Ngày lập: 31/10/2026. Trạng thái: chỉ lập kế hoạch, chưa triển khai hoặc thay cấu hình màn hình.

Tài liệu giai đoạn tiếp theo: [Phân tích hệ thống](PRIMARY_MONITOR_SYSTEM_ANALYSIS.md), gồm khảo sát API chỉ đọc, yêu cầu, mô hình dữ liệu và các điểm cần kiểm chứng trước khi thiết kế.

Thiết kế triển khai: [System Design v1](PRIMARY_MONITOR_SYSTEM_DESIGN.md), quy định module, IPC, recovery agent, khóa theo session và các cổng kiểm chứng GNOME.

## 1. Kết quả mong muốn

Trong Studio → Màn hình, người dùng thấy các màn hình đang hoạt động, biết màn nào là chính và có thể đặt màn khác làm màn hình chính của desktop. Thiết lập này tác động đến hệ điều hành; lựa chọn “Màn hình đặt Dock” tiếp tục điều khiển riêng vị trí Dock.

Khi đổi primary, giữ nguyên vị trí trái/phải/trên/dưới, mode, tần số quét, scale, rotation, trạng thái bật/tắt và nhóm mirror. Desktop quyết định vị trí panel/cửa sổ của nó; ứng dụng không hứa tự di chuyển mọi cửa sổ.

## 2. Phạm vi phiên bản đầu

- Ưu tiên GNOME/Mutter trên môi trường hiện có; probe D-Bus capability ở runtime. Kiểm riêng X11 và Wayland trước khi công bố hỗ trợ từng môi trường.
- Chỉ cho chọn logical monitor đang hoạt động. Màn đang kết nối nhưng tắt hiển thị trạng thái, không tự bật để đặt primary.
- Nhóm mirror là một logical monitor: chọn nhóm làm primary, không gán primary độc lập cho từng đầu nối trong nhóm.
- Một màn hình: hiển thị primary và giải thích chưa có màn khác để chuyển.
- Desktop không có adapter đã kiểm chứng: hiển thị lý do và lối mở cài đặt màn hình hệ thống nếu tìm được ứng dụng phù hợp.
- Chưa triển khai tự đổi primary khi khởi động/cắm cáp, thay bố trí hoặc scale, Windows, KDE và COSMIC. Không ghi đè lựa chọn hệ điều hành lúc mở DeskMorph.

## 3. Khảo sát và chốt cơ chế hệ thống

- [ ] P1.1 Probe `org.gnome.Mutter.DisplayConfig`: introspection, GetCurrentState, MonitorsChanged, phương thức apply và giới hạn cấu hình. Tái sử dụng kinh nghiệm từ harness Mutter hiện có, không đưa mã test vào runtime.
- [ ] P1.2 Đọc topology thực: logical monitor, connector, mode ID, scale, transform, primary, layout mode và các thuộc tính cần bảo toàn. Dùng snapshot có serial/revision, không chỉ tên màn hình từ Tauri.
- [ ] P1.3 Trong môi trường thử riêng, xác minh VERIFY, cách apply/persist và cơ chế xác nhận/timeout do compositor cung cấp. Xác định ai hiển thị hộp xác nhận để tránh hai hộp cạnh tranh.
- [ ] P1.4 Chứng minh khả năng phục hồi nếu UI không phản hồi hoặc tiến trình chết. Ưu tiên timeout do compositor quản lý; nếu không có, cần cơ chế giám sát độc lập được kiểm chứng trước khi mở tính năng. Timer trong React hoặc trong cùng tiến trình không đủ làm bảo đảm phục hồi.
- [ ] P1.5 Kiểm chứng việc lưu qua logout/login hoặc restart phiên desktop. Phân biệt rõ thay đổi tạm và đã lưu.

Đầu ra: ghi nhận API và policy cho từng môi trường. Chưa qua cơ chế phục hồi thì chỉ cung cấp trạng thái đọc và mở cài đặt hệ thống.

## 4. Native backend

- [ ] P2.1 Tạo module `src-tauri/src/displays/` với adapter GNOME, model snapshot và lỗi có mã ổn định. Capability quản lý primary độc lập với capability đặt Dock.
- [ ] P2.2 Cung cấp IPC dự kiến: `get_display_state`, `preview_primary_monitor`, `confirm_primary_monitor`, `revert_primary_monitor`. Preview trả transaction ID và deadline do native quản lý; confirm/revert chỉ nhận transaction hiện hành.
- [ ] P2.3 Đọc snapshot mới trước khi apply; xác minh target còn hoạt động và revision khớp. Target là logical monitor có identity từ adapter, không suy ra bằng vị trí hoặc tên hiển thị.
- [ ] P2.4 Tạo cấu hình từ snapshot, chỉ đổi cờ primary. Giữ nguyên thuộc tính khác; VERIFY trước khi apply nếu backend hỗ trợ. Không chạy shell với tên connector do UI cung cấp.
- [ ] P2.5 Serialize mutation: tối đa một giao dịch đang chờ xác nhận trong toàn ứng dụng. Chọn màn vốn đang là primary trả thành công không thay đổi.
- [ ] P2.6 Đọc lại trạng thái sau apply/confirm/revert. Chỉ báo thành công khi trạng thái hệ điều hành xác nhận; phản ánh lỗi lưu nếu preview thành công nhưng persist thất bại.
- [ ] P2.7 Khi hotplug hoặc desktop Settings thay đổi topology giữa giao dịch: vô hiệu hóa giao dịch, refresh và báo rõ. Chỉ khôi phục khi snapshot còn tương thích và trạng thái hiện tại vẫn thuộc giao dịch của mình; không apply lại snapshot cũ lên màn đã rút hoặc ghi đè thay đổi mới bên ngoài.
- [ ] P2.8 Subscribe sự kiện thay đổi, gộp sự kiện trùng và hủy subscription khi thoát. Lỗi D-Bus, unsupported, serial cũ, target mất, apply bị từ chối và rollback thất bại có thông báo riêng.

## 5. Giao diện Studio

- [ ] P3.1 Thêm mục “Màn hình” vào Studio, có tên/connector, độ phân giải, scale và nhãn “Màn hình chính”. Danh sách là bắt buộc; sơ đồ vị trí chỉ thêm nếu hỗ trợ nhận diện rõ hơn.
- [ ] P3.2 Nút “Đặt làm màn hình chính” cho từng logical monitor hợp lệ. Vô hiệu hóa nút trên primary hiện tại và trong lúc có giao dịch.
- [ ] P3.3 Mô tả ngắn tác động đến desktop và giữ nguyên bố trí. Chọn → áp dụng thử → “Giữ thay đổi” hoặc “Hoàn tác”, thời gian dự kiến 15–20 giây, chốt theo cơ chế compositor đã xác minh.
- [ ] P3.4 Chỉ có một nơi điều khiển xác nhận. Nếu compositor cung cấp hộp xác nhận, Studio theo dõi kết quả thay vì dựng countdown độc lập không cùng deadline.
- [ ] P3.5 UI tiếng Việt/Anh, thao tác bằng bàn phím, focus hợp lý, thông báo screen reader khi áp dụng/hoàn tác/lỗi. Timeout vẫn hoạt động khi Studio mất focus hoặc bị đóng.
- [ ] P3.6 Refresh theo thay đổi desktop và có nút tải lại. Hiển thị lỗi kèm thử lại; không để lựa chọn optimistic tồn tại khi apply thất bại.

## 6. Tích hợp với Dock

- [ ] P4.1 Bổ sung primary vào thông tin màn hình để UI và layout phản ánh cùng nguồn trạng thái đã xác minh.
- [ ] P4.2 Khi primary đổi, đóng popup cũ và cập nhật layout sau khi topology ổn định. Watcher hiện dựa trên signature monitor cần nhận cả thay đổi primary dù geometry giữ nguyên.
- [ ] P4.3 Chế độ Dock “Màn hình chính” theo primary mới; chế độ màn cụ thể giữ màn đã chọn; “Tất cả màn hình” giữ đúng một Dock trên mỗi logical monitor đang hoạt động.
- [ ] P4.4 Kiểm quá trình hoán đổi primary window/extra window: dọn state và cửa sổ thừa, không mất focus ngoài ý muốn, không tạo hai Dock chồng nhau hoặc để lại vùng input trong suốt.
- [ ] P4.5 Primary là trạng thái của desktop, không thêm vào cấu hình export/import/preset của DeskMorph và không tự áp lại từ cấu hình cũ.

## 7. Kiểm thử và tiêu chí nghiệm thu

### Kiểm tự động có giá trị

- [ ] P5.1 Fixture adapter: đổi đúng primary và bảo toàn toàn bộ thuộc tính; một màn; mirror; target tắt/mất; serial cũ; D-Bus lỗi; VERIFY/apply/persist thất bại.
- [ ] P5.2 State machine giao dịch: chống hai request đồng thời, confirm trễ, timeout, rollback, topology thay đổi và thay đổi bên ngoài. Kiểm cơ chế phục hồi khi tiến trình chết bằng integration phù hợp.
- [ ] P5.3 UI: capability, trạng thái pending/error, vi/en, bàn phím và focus; không tạo test chỉ kiểm sự xuất hiện của chuỗi mã nguồn.
- [ ] P5.4 Hồi quy tích hợp Dock khi đổi primary giữ nguyên geometry; test phải phát hiện Dock trùng, không chỉ đếm tiến trình.

### Kiểm thực tế, tách khỏi unit test

- [ ] P6.1 Hai màn laptop/HDMI: chuyển A → B → A ít nhất ba vòng, xác minh primary bằng API hệ điều hành, không chỉ nhãn UI.
- [ ] P6.2 Chạy ba chế độ Dock (primary/cụ thể/tất cả), vị trí trên/dưới; đo vị trí/kích thước/input region và kiểm popup trên từng màn hình.
- [ ] P6.3 Giữ thay đổi, hoàn tác thủ công, hết giờ, đóng Studio và kill tiến trình trong thời gian thử. Không chấp nhận nếu mất khả năng điều khiển hoặc không phục hồi như thiết kế.
- [ ] P6.4 Rút/cắm HDMI trong giao dịch; đổi primary từ Settings ngoài ứng dụng; ứng dụng phản ánh trạng thái mới và không ghi đè thao tác bên ngoài.
- [ ] P6.5 Mixed DPI, độ phân giải/tần số quét khác nhau, mirror và ba màn nếu có thiết bị. Xác minh thuộc tính trước/sau được giữ; trường hợp thiếu môi trường ghi chưa kiểm.
- [ ] P6.6 Kiểm persistence qua restart ứng dụng và logout/login; bàn phím/screen reader vi/en. Chạy X11/Wayland riêng, chỉ công bố môi trường đã đạt.

Nghiệm thu khi chuyển primary đúng, không thay thuộc tính ngoài phạm vi, không tạo Dock trùng, trạng thái UI khớp desktop và phục hồi đã được kiểm chứng. Kết quả lỗi phải hiển thị trung thực; không đánh dấu đạt các ca thiếu phần cứng/môi trường.

## 8. Thứ tự thực hiện và dự toán

| Chặng | Công việc | Ước lượng công sức |
| --- | --- | --- |
| 1 | P1: khảo sát API, persistence, cơ chế phục hồi | 0,5–1 ngày |
| 2 | P2: adapter, giao dịch và xử lý lỗi | 1–2 ngày |
| 3 | P3–P4: Studio, vi/en, đồng bộ Dock | 1–1,5 ngày |
| 4 | P5–P6: kiểm tự động và native, sửa lỗi | 1–2 ngày |
| 5 | Tài liệu, bằng chứng, build, commit tiếng Việt | 0,5 ngày |

Tổng dự kiến 4–7 ngày công cho phạm vi GNOME, điều chỉnh sau chặng 1. Mở rộng desktop khác là hạng mục riêng. Chưa bao gồm thời gian chờ phần cứng hoặc phiên desktop rảnh để thử thay đổi thật.

Không đổi cấu hình màn hình thật trong bước lập kế hoạch. Khi triển khai, hoàn thiện và kiểm adapter trong môi trường riêng trước; các ca thay topology trên desktop người dùng cần sắp xếp khoảng kiểm thử phù hợp. Mỗi lượt ghi baseline, PID/profile sở hữu, bằng chứng trước/sau và kết quả khôi phục; không commit log riêng tư hoặc binary.
