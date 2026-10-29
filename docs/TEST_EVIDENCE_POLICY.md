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
