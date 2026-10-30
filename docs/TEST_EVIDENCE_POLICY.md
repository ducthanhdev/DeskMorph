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

- Dismissal trace: giữ logging debug opt-in tại `hide` với caller/generation vì lỗi stress không tái hiện sau rebuild; không đổi logic để ép test qua. Giữ hai kết quả 12 vòng có/không trace cùng SHA256, giữ riêng failure cũ. Không tuyên bố fix từ kết quả không tái hiện hoặc coi lệnh lọc 0 test là regression suite.

- Output fallback: giữ nhánh opt-in XRandR hai output có preflight và finally restore mode/refresh/position/primary, assert Dock/config/popup trên output còn lại và trở về. Native regression phát hiện tọa độ WM giữ sau remap, có baseline/final cụ thể; giữ JSON kết quả và lỗi focus-delay đối chứng thay vì chỉ báo phần qua. Chưa thay thế physical unplug/mixed-DPI. Nút Open cho chooser giúp cleanup không phụ thuộc Enter/autocomplete; config/profile/binary/log không stage.

- Dock activation timestamp: không thêm test hình thức cho GDK accessor; native focus harness sẵn có tái hiện lỗi và qua11 nhóm ở cả0/500ms, gồm lựa chọn cửa sổ ngoài thắng callback trễ. Giữ JSON hai lượt cùng hash binary và Cargo.lock có direct gdkx11 dependency; không stage log/profile/build. Kết quả này giải quyết lỗi focus audit mới, không nâng thành chứng nhận accessibility hoặc Wayland.

- Physical hotplug: giữ nhánh chờ connector disconnected/connected thật vì cần người vận hành cáp; marker giai đoạn và timeout180s giúp điều phối, không thay bằng software-off. Báo cáo rút gọn topology về HDMI/eDP, ghi rõ XRandR restore bật output sau reconnect; không coi một vòng là soak. Không thêm unit test giả sự kiện để chứng minh physical gate.

- Scheduler system suspend: giữ opt-in gọi suspend thật cùng phép đo BOOTTIME−MONOTONIC>=120s và chờ unlock; default SIGSTOP vẫn phân loại riêng. Giữ sửa nhận diện scheduler alert/Chi tiết sau localization và checkpoint để không mất phần đã đo khi ca sau fail. JSON chỉ lưu lượt đầy đủ138,922s cùng cleanup/phạm vi, ghi rõ lượt cũ lỗi harness; không commit runtime logs/profile/binary. Native flow hiện có bảo vệ deadline/cùng instance/missing-image/recovery/disable nên không thêm unit test lặp code orchestration.

- Popup soak: giữ sampler `/proc` có profile guard/starttime, median growth alarms và Quit/survivors cùng nhánh opt-in30–120phút vì dùng lại để đo lifecycle. Chỉ lưu JSON first/last/summary của lượt chưa đạt và smoke đối chiếu; hàng trăm mẫu raw, runtime log và profile ở/tmp. Failure focus vòng50 giữ nguyên; sửa harness yêu cầu native opening gesture không được gọi là sửa sản phẩm hoặc soak đạt.

- Context force keyboard: mở rộng harness hiện có thay vì tạo bản sao, thêm kiểm environment/Popen owner và quan sát exit sau Tab/Enter. Giữ JSON hai lượt vi/en và cleanup; ảnh review đã có từ ca trước nên không thêm ảnh trùng. Không dùng fixture exit để tuyên bố mọi ứng dụng được force quit hoặc toàn bộ accessibility đã đạt.

- Soak hoàn chỉnh: giữ một JSON summary122 mẫu/first/last và hash binary;122 raw samples ở/tmp. Giữ riêng failure trước sửa harness. Chốt lifecycle bằng liên kết các lượt riêng restart/suspend/hotplug, không gộp thành một soak có mọi sự kiện hoặc chứng nhận leak-free. Không thêm ảnh chụp cho số đo/procfs.

- Gradient Studio: mở rộng audit hiện có thay vì thêm harness WebKit trùng. Giữ2 reference tests mới vì bảo vệ alpha/composite, continuous interpolation, luminance crossing và từ chối cấu hình không hỗ trợ; không phải test lặp markup. JSON chỉ8 ca mới/bounds/hash CSS, tổng113 và giới hạn; không commit computed tree/log của các lượt parser lỗi. Bằng chứng cận tương phản không thay pixel/native-focus/screen-reader audit.

- Unpinned desktop actions: giữ harness native riêng dùng lại desktop driver, private catalogue/window fixture và marker phân biệt default Exec với action. Đây là bằng chứng cho đường keyboard/mutation thật, không phải test mirror markup; giữ JSON vi/en/cleanup, không thêm ảnh/log/profile. Không nâng fixture launch thành chứng nhận mọi ứng dụng.

- Audio focus hotplug: mở rộng harness private audio hiện có, tạo/xóa module thật và kiểm native radio/focus cùng default sink invariant; giữ JSON12 restart và cleanup trên build hiện tại. Không tạo fake hotplug event hoặc chứng nhận physical headset/pending request từ ca focus-only này; không thêm ảnh/log/profile hay unit test chỉ lặp câu lệnh.

- Orca speech: giữ runner opt-in có existing-reader guard, private prefs/socket/null sink và waveform/stream assertions, vì tái lập failure tích hợp thật. Giữ JSON failed/phiên bản/số đo/cleanup và nhãn fixture, không stage audio/debug logs/profile có thể chứa lời đọc startup ngoài app. Không giữ các thử nghiệm gửi phím lặp vào shared drivers khi chưa thành công, không bỏ assertion để tô xanh. Probe Xvfb origin âm vẫn là script chẩn đoán/tmp; chỉ ghi khả thi và giới hạn, chưa tính thành gate hoặc thêm harness chưa chạy ổn định.


- Negative-origin allocation: giữ harness opt-in chạy Xvfb đã có, bus/profile/display riêng, PID/XID và phép đo từng popup sau Dock ổn định; Escape chỉ gửi tới private DISPLAY. Giữ JSON16 ca cùng lỗi phép đo đã sửa và giới hạn không WM/không pixel/mixed DPI; raw logs/profiles/Xvfb executable ở/tmp. Không thêm unit test lặp placement đã có; native matrix bắt được khác biệt AT-SPI logical/X11 physical ở scale2. Không đánh dấu G2.10 từ topology ảo.


- Orca navigation preferences: giữ tùy chọn opt-in để tái lập cấu hình yêu cầu và ghi riêng caret-enabled đã quan sát; không thay assertions shared keyboard. JSON giữ failure mới, waveform counts, exit−11/cleanup và giới hạn preferences không có hiệu lực; không lưu raw speech/debug. Không tính lượt này thành kiểm focus mode thành công; diagnostics bổ sung sau run chỉ compile, không tuyên bố đã chạy GUI phiên bản đó.
