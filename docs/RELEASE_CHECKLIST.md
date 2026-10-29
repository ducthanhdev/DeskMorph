# Checklist phát hành — 0.1.0 development

Đã có `.deb` development0.1.0 cho Ubuntu/Pop!_OS24.04 amd64, [recipe và kiểm thử](PACKAGING.md), SHA256 `f138ca13d82a29ff9ced3b4b9fe3194b60cd03ce43cfac2b4c508035250a6b15`. Chưa có release candidate hoặc artifact đã qua cài sạch. Chỉ tick khi có bằng chứng/version/artifact tương ứng; không phát hành chỉ vì build thành công.

- [ ] Chốt phạm vi và mọi đầu việc bắt buộc trong IMPLEMENTATION_PLAN.md; xử lý lỗi nghiêm trọng trước tính năng mở rộng.
- [ ] Ghi commit, toolchain, distro/desktop/session, dependency versions và artifact checksum.
- [ ] Unit/build/CI pass trên commit ứng viên; ghi rõ native tests không thuộc CI headless.
- [ ] Luồng search → launch → pin → reorder → activate/close → restart pass; popup/focus/auto-hide/overflow và bàn phím được stress test.
- [ ] Config migration/corruption/import/reset/concurrent updates không mất dữ liệu; backup và lỗi IO được kiểm tra.
- [ ] CSP/IPC/asset scope được native regression; icon/thumbnail vẫn tải đúng và path ngoài scope bị từ chối.
- [ ] Monitor topology/hotplug/mixed DPI và sleep/resume được test hoặc giới hạn được chốt rõ; không gắn nhãn verified cho môi trường chưa chạy.
- [ ] Wallpaper/audio/media/system services restart, missing capability và hardware cases trong phạm vi release được kiểm tra.
- [ ] Chốt định dạng gói cho distro mục tiêu; kiểm thử icon/menu/autostart trên tài khoản sạch.
- [ ] Cài mới, nâng cấp giữ cấu hình và gỡ executable/desktop entry được thử bằng artifact thực; không tự xóa dữ liệu cá nhân.
- [ ] README/architecture/changelog/known limitations khớp code; thêm ảnh chụp native đã xác minh.
- [ ] Người phụ trách release quyết định version/artifact sau khi các cổng trên đạt; chưa publish trong phiên triển khai này.
