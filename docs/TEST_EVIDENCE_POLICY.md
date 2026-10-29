# Đánh giá test và bằng chứng trước commit

Commit test là cần thiết khi test bảo vệ hành vi hoặc cho phép người khác tái lập kết luận. Không commit mọi file đã dùng để kiểm tra. Tài liệu đánh giá, kết quả, giới hạn và tiến độ vẫn cập nhật cho từng phần chốt.

| Loại file | Quyết định mặc định | Căn cứ cần có |
| --- | --- | --- |
| Regression `.test.mjs`, Rust test | Giữ | Kiểm hành vi/lỗi có ý nghĩa; tránh chỉ lặp cấu trúc implementation |
| Harness native/compositor và fixture | Giữ khi tái sử dụng được | Lệnh chạy rõ, assertion, môi trường/phụ thuộc, nhận diện ownership và cleanup; opt-in nếu tác động GUI |
| Script chẩn đoán một lần | Để `/tmp`, không stage | Chỉ dùng điều tra, không bảo vệ hành vi hoặc tái lập cổng kiểm thử |
| JSON kết quả | Chọn một báo cáo đủ chứng minh | Version/hash, phạm vi, kết quả, giới hạn; ưu tiên tóm tắt thay dump protocol/computed tree không liên quan |
| Ảnh chụp | Chọn trạng thái khác nhau cần chứng minh | Phải xem ảnh, có liên hệ assertion; không lưu mọi lần chạy hoặc ảnh trùng |
| Log, cache, profile, binary và gói build | Không commit | Chỉ giữ ở vị trí tạm/artifact; tài liệu dẫn recipe/hash khi cần |

Trước stage, xem `git status`, diff và danh sách file mới; ghi rõ vì sao giữ test mới, chạy kiểm phù hợp rồi cập nhật tài liệu. Không thêm test cho thay đổi nhỏ chỉ để tăng số lượng. Test trong repo không đồng nghĩa tự chạy được trong CI: native harness cần được ghi rõ điều kiện chạy.

## Đánh giá hiện tại

- Các test frontend và Rust đang bảo vệ serialization/config, request lifetime, launch/GIO, focus và lỗi adapter; có lý do giữ cùng code sản phẩm.
- Các harness Wayland/GNOME và fixture cho phép tái lập bằng chứng GUI có ownership/cleanup; giữ source cần thiết thay vì chỉ lưu ảnh và một lời khẳng định đã test.
- Riêng khảo sát COSMIC mới: giữ worker và tích hợp lab vì còn dùng để triển khai/kiểm adapter. Báo cáo commit chỉ gồm phần liên quan và hai ảnh màu khác nhau; log chẩn đoán/full protocol dump ở `/tmp`.
- Báo cáo cũ có phần verbose hoặc ảnh cùng trạng thái có thể gọn hơn. Chưa audit từng file; không tự xóa test/bằng chứng hoặc rewrite commit cũ theo suy đoán. Khi dọn cần kiểm mọi link tài liệu, khả năng tái chạy và bảo toàn bằng chứng cho checkbox đã chốt.

Tài liệu này ghi quyết định kỹ thuật theo yêu cầu người dùng, không tạo bước xin phép bổ sung trước các commit đã được giao.

- Chuẩn bị parser COSMIC: giữ ba Rust regression trong module, kiểm bảo toàn byte/comment/unknown enum và đường dẫn Unicode/escaping, từ chối cấu hình mơ hồ/không hỗ trợ, etag conflict/0600/symlink. Có giá trị bảo vệ dữ liệu người dùng; không thêm script diagnostic hoặc log build vào commit. Chưa coi các test này thay thế runtime/UI hay bảo đảm chống mọi race.

- Per-output COSMIC/state isolation: giữ sửa harness và guard hash một file state host vì phát hiện tác động ngoài lab thật. Giữ JSON5 pha và2 ảnh override/live-update đã xem; ảnh màu trùng chỉ ghi hash/sample. Không commit log/bản upstream tải tạm; ghi URL commit và hash nguồn để đối chiếu. Bằng chứng cũ được đính chính thay vì xóa lịch sử.

- Native write COSMIC: giữ regression color/output/resolver và Rust native_lab_edit opt-in được worker gọi2 lần (all/per-output). Guard/tmp/config/state/output và byte/pixel assertion có giá trị hơn script ghi RON độc lập. Chỉ commit JSON kết quả/hash/sample; ảnh màu trùng và log ở/tmp. Suite thường bỏ qua native test là chủ ý, báo cáo phân biệt rõ với invocation runtime đã qua.

- COSMIC batch/preflight: giữ8 Rust regression cho dữ liệu, rollback/conflict và lỗi quyền thật; cùng test native opt-in kiểm all+per-output qua compositor. Hàm hook nội bộ cho fault injection không expose IPC. JSON tóm tắt mới có source hash/sample; không commit ảnh màu trùng/log/cargo artifacts. Tests không chứng minh atomic nhiều file, crash recovery hoặc mọi TOCTOU; tài liệu ghi rõ giới hạn.

- COSMIC Studio/defaults: giữ6 Rust regression (schema strict +5 defaults/create/rollback/probe),1 i18n recovery-guidance regression và worker UI dùng lại qua AT-SPI/IPC/pixel, có nhận diện PID/cleanup và thông báo completion. Report tóm tắt lưu cùng binary hash hồi quy GNOME; giữ2 ảnh đã xem (Studio hồng, Retry xanh), không thêm mọi capture màu trùng hoặc log/lượt harness lỗi. UI frame chỉ chứng minh render, không gắn assertion nền phẳng cho vùng cửa sổ. Không tính en Apply cũ có source trùng sẵn hoặc lượt worker lỗi là bằng chứng cuối.

- Geometry scale 200%: giữ mở rộng harness logical/physical vì phép đo native tại scale 2 cần cả tọa độ AT-SPI và GDK đúng đơn vị, kiểm clamp workarea và khôi phục config. Giữ JSON 16 rectangle có PID/lệnh/hash binary; không commit log hay profile. Bằng chứng GTK scale 2 không thay thế fractional/mixed-DPI hoặc audit nội dung popup.

- Stress audio restart: giữ biến số vòng và chẩn đoán native active-owner/app-state để tái lập lỗi popup biến mất sau 6 vòng; guard focus và retry AT-SPI có timeout/owner-live giúp phân biệt lỗi phép đo. Giữ báo cáo `passed:false` cùng hồi quy 3 vòng đã qua; không nâng kết quả hẹp thành stress/soak đạt, không commit dump sinks/log/private configs.
