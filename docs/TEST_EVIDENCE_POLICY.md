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


- Mutter scale capabilities: chỉ lưu JSON đã bỏ serial/EDID và mô tả GetCurrentState/GSettings; không thêm harness/unit test cho một capability snapshot. Ghi riêng feature có trong schema với feature thực sự bật/chạy đạt; không dùng survey integer-global hiện tại để chốt fractional/mixed DPI.


- Orca bypass/description: giữ helper opt-in Alt+Backspace có reader/log ownership và bypass on/off vì tái lập bàn phím thật mà không bỏ Home/End assertions. Regression hiện có kiểm ErrorText target chỉ chứa chữ, ID/link ổn định khi đổi locale và cancel không gửi kill. Giữ baseline, final warning-speech-pass/launch-speech-fail, lỗi chuẩn bị/composite-description và hai thử nghiệm persistent-summary đã gỡ. Commit phần description/warning đã kiểm, không coi whole speech suite đạt. Guard WebKit script mới chưa có full acceptance riêng trên restored product, ghi rõ giới hạn thay vì lược failure.

- Native description lab: mở rộng harness Xvfb có sẵn bằng opt-in fixture missing command, không tạo một harness khác giả markup sản phẩm. Giữ4 native description/focus cases +16 placement trên binary thật cùng hash, private-display keys/PID guard và JSON gọn; raw config/log/probe ở/tmp. Probe HTML sáu cases chỉ là chẩn đoán platform mapping, không thay acceptance của app.


- Isolated launch speech: chỉ giữ JSON đối chiếu baseline/empty-summary/U+200B và positive drawable controls, cùng native description/focus,8giây chờ, speech/waveform counts và cleanup. Script sao chép để chẩn đoán ở/tmp, không đưa thêm harness lớn trùng negative-origin vào repo. Event observer phải tính cả WebKit descendant có ownership marker; lượt chỉ lọc native PID không đủ chứng minh text event vắng mặt. Giữ stream-unresolved preparation failure và giới hạn HTML probe chỉ đọc frame; không nâng thành speech acceptance hoặc root-cause claim. Hai thay đổi live-summary không hiệu quả đã gỡ và rebuild đúng binary hash; không commit thử nghiệm sản phẩm hay chạy thêm suite lặp trên source không đổi. G5.9 vẫn mở.


- Launcher SVG contrast: giữ24 fixture trong audit hiện có vì đo stroke thật từ lucide-react đã cài, background gradient/opaque và bounds trong button ở ba kích thước/bốn accent/thường-hover; không sao chép SVG paths hoặc thêm unit test lặp class CSS. Giữ summary baseline/final với cận bảo thủ,24 geometry/ratio entries và hash; không gọi failed lower bound là tỷ lệ từng pixel. Hai ảnh crop trước/sau và một ảnh native Dock tối là bằng chứng review trực quan mới, không commit toàn bộ screenshot/grid/raw computed tree. Native geometry/description regression dùng lại harness hiện có; không suy thành whole-a11y/Orca/WM acceptance.


- Native Studio controls: giữ nhánh opt-in trong Xvfb harness có sẵn vì baseline thật bắt được tick/thumb contrast2,323:1 và hậu kiểm native vi/en4,013:1; computed CSS không đo được màu UA checkmark/thumb. Keys thật Space/Tab/Shift+Tab/arrows/Home/End đối chiếu native checked/config và disabled skip. Giữ summary palette/counts/rectangles/ratio/hash, baseline fail, hai lỗi crop đã sửa và4 ảnh nhỏ có giá trị review; raw full-window/log/profile ở/tmp. Label crop phải kiểm ô vuông20px và palette, GdkPixbuf crop phải kiểm root scale/đơn vị/logical/device dimensions. Không bỏ assertions khi đo nhầm vùng, không gọi field restore là byte restore hoặc outline pixel hiện diện là chứng nhận clipping toàn app. Không thêm unit test chỉ phản chiếu token CSS hoặc chạy lại unit suites không liên quan.


- Mutter restore preflight: giữ probe opt-in và6 fault tests vì host settings/topology restoration cần kiểm failure paths, user-value unset/explicit và read-only invariant. Giữ JSON method0 reject/pass cùng normalized topology không EDID/serial; backup/user-value/raw state ở/tmp. Method0 chỉ VERIFY, không gọi là monitor apply hoặc fractional acceptance. Method1 fallback mới chuẩn bị/chưa chạy; không dùng unit mocks để chứng nhận host restore. Không bật feature khi chưa có desktop availability mới.


## G2.10 — Fractional feature: khả năng có, trial chưa đạt (30/10/2026)

[Trial trên Mutter thật](benchmarks/dpi-feature-trial-2026-10-30/result.json) công bố scale1,25/1,5 sau khi bật tạm `x11-randr-fractional-scaling`, nhưng đổi primary từ eDP sang HDMI và refresh eDP144Hz thành60Hz. Guard phát hiện topology khác, dừng ca; `passed:false` được giữ nguyên. Không apply scale fractional hoặc tính đây là acceptance ứng dụng.

Cleanup đã phục hồi đúng features/user value, topology, primary, mode/refresh và capabilities ban đầu; fallback ApplyMonitorsConfig method1 TEMPORARY thực sự được dùng, không persistent method2. Không gửi input. Bằng chứng JSON cần giữ vì ghi cả failure và khôi phục thật; không thêm test trùng hoặc raw log. G2.10/G5.9 tiếp tục mở,97/99; release no-go.


## Orca native announcement (30/10/2026)

Giữ [kết quả speech và baseline](benchmarks/orca-native-announcement-2026-10-30/result.json), [keyboard vi/en](benchmarks/orca-native-announcement-2026-10-30/keyboard.json), frontend dedupe/retry/locale test, Rust ownership/generation/message guards và helper speech opt-in. Chúng bảo vệ lỗi thực: DOM có text/description nhưng reader không nói. Chỉ lưu fixture summary/số đo/hash/source URL, không raw audio/debug/preferences hay mã upstream. Speech acceptance yêu cầu summary trong log đã flush, waveform khác0, reader sống lúc đo/thoát0 và stream vào owned null sink; waveform không chứng minh intelligibility.

Giữ failure tọa độ positive, SIGTERM exit-9 và startup reader song song trong metadata; không chuyển các lượt đó thành pass. Private Quit và chạy tuần tự giải quyết harness; không --replace reader người dùng. Các ca4/4 chỉ kiểm launch speech/focus vi/en/top/bottom trên integer scales trong Xvfb; GNOME keyboard regression riêng không bật Orca. Không suy chứng nhận warning/default browse, toàn bộ a11y hoặc fractional/mixed DPI. Audit0 owned helper/sink, audio mặc định giữ nguyên.


## Studio focus scroll/pixels (30/10/2026)

Giữ [bằng chứng406 control](benchmarks/studio-focus-scroll-2026-10-30/result.json), hai crop fixture và harness Tab dùng lại + callback pixel. Nó bắt regression control bị cắt và focus ảnh mất hoàn toàn; native select arrow/border có pixel/ratio riêng. Chỉ giữ số đo/nhãn fixture và counts theo trang, không raw tree/catalogue/profile/ảnh người dùng. Hai failure tọa độ và0 focus pixel được giữ có giới hạn; sửa first-five-buttons/disclosure lookup thuộc harness. 203 pixel samples mỗi ngôn ngữ loại nav seed,208 Tab stops mỗi lượt không đồng nghĩa mọi trạng thái động đã kiểm. Không thêm unit test chỉ kiểm scrollIntoView được gọi.


## Fractional/mixed DPI native survey (30/10/2026)

Giữ [6 ca native](benchmarks/dpi-native-fractional-2026-10-30/result.json) với Mutter requested/readback layouts, GDK workareas/scales, native Dock/launcher bounds, hash binary/diagnostic, failures và exact restore. Giữ runner opt-in cùng5 fault tests orchestration vì đây là thao tác host topology cần bảo vệ restore khi worker fail/timeout/interrupt và tách settings/display cleanup. Dùng lại probe/payload guards cũ; không giữ diagnostic sao chép trong/tmp hoặc raw logs. Metadata phân biệt diagnostic đã chạy thật với safety guards bổ sung mới chỉ fault-test. Native framebuffer allocations không thay thế physical pixels, font sharpness, keyboard/click, Dock dưới, popup khác hoặc negative origin dưới WM. Không đánh dấu G2.10 từ6 ca hẹp này.


## Functional glyph contrast (30/10/2026)

Giữ72 fixture mở rộng trong contrast_audit.py vì đo stroke/gradient và fit SVG thật của các control chưa có bằng chứng; dùng lại renderer/math hiện có, không test lặp markup. [JSON gọn](benchmarks/functional-glyph-contrast-2026-10-30/result.json) giữ cận màu, kích thước SVG và hash, không lưu toàn computed tree hoặc nhân bản137 ca trước.209/209 là kết quả suite offscreen, không thay native focus/Orca acceptance.


## DPI worker preflight (30/10/2026)

Giữ nhánh opt-in dùng chung worker giữa Xvfb và Mutter, cùng [16 kết quả native riêng](benchmarks/dpi-worker-private-2026-10-30/result.json), để phát hiện sai nguồn/kích thước/đơn vị trước host mutation.11 fault tests tiếp tục qua; ma trận48 ca host mới chỉ chuẩn bị, chưa có acceptance. Không commit bản sao probe GNOME Shell/tmp: negative RandR monitor ngoài drawable root không phải topology vật lý dưới WM. Không dùng kết quả đó để đánh dấu G2.10 hoặc quy lỗi sản phẩm.


## Fractional/mixed full matrix (30/10/2026)

Giữ [48 native observations](benchmarks/dpi-native-full-matrix-2026-10-30/result.json) vì mở rộng acceptance từ Dock trên/launcher sang Dock dưới và bốn nguồn trên hai màn hình. JSON giữ before/requested/readback/after, restore flags, PID và binary/runner hash; raw logs/private configs ở/tmp. Mỗi nguồn instance mới nên không nâng thành popup sequencing, keyboard hoặc physical-pixel proof. Không thêm test mirror geometry đã có;11 fault tests hiện có bảo vệ thao tác host, runner mới đã chạy thật và restore đạt.


## Current Orca regression (30/10/2026)

Giữ [JSON hồi quy đạt](benchmarks/orca-current-regression-2026-10-30/result.json) và sửa harness screen_reader_smoke.py vì chạy kiểm bàn phím vi/en không hạ assertions, kiểm speech lỗi/warning trên binary hiện tại, route sink và reader exit0. Chờ stream resolve, PID-guard official Quit và đọc log sau shutdown giải quyết các preparation/flush failures đã ghi trước. Không commit raw speech/audio; bypass-navigation và giới hạn default-reader/human listening ghi rõ, không nâng menu suite thành chứng nhận toàn bộ accessibility.


## Integer output failure and recovery guard (30/10/2026)

Giữ [integer-output trial thất bại](benchmarks/dpi-output-integer-trial-2026-10-30/result.json) riêng với48-ca pass:100%16/16,200%10pass/1fail/5not-run; flags cleanup thất bại không bị ghi đè bởi operatorRecovery đạt.13 fault tests bảo vệ bounded reapply/cooldown và ghi lỗi persistent drift; không thay acceptance host guard mới. Giữ --layouts để tái lập200% độc lập, không phải chạy lại48ca đã đạt. Baseline được xác minh giữ nguyên sau recovery và0helper/sink. Không giữ private GNOME diagnostic không đạt precondition synthetic monitor như test sản phẩm.


## Private GNOME WM geometry (30/10/2026)

Giữ helper GNOME riêng tái dùng negative_origin_smoke.py và [4 ca system native](benchmarks/system-geometry-private-wm-2026-10-30/result.json), không commit các bản sao diagnostic/tmp. Guard test6 subcases cần thiết vì helper gọi Shell --replace và private Escape; phải chặn host DISPLAY/buses/settings/XDG trước Popen. Giữ settling trace có giới hạn và --sources/--repeat để tái hiện failure thật, không thêm unit test mirror polling. Chờ Dock ổn định20samples và assert không đổi qua activation bắt stale-anchor measurement, không làm nhẹ yêu cầu clamp/center/size.4 ca private không thay200% HDMI acceptance, fractional output hoặc negative topology dưới WM.


## Audio native controls (30/10/2026)

Giữ helper audio_native_controls.py tái dùng runner/owned private GNOME và PrivateAudioServer optional policy, cùng [4runs/20captures](benchmarks/audio-native-controls-2026-10-30/result.json). Đây là native integration đã yêu cầu cho G5.9: keys làm thay đổi server thật và pixel control, không test lặp markup. Giữ guard callback host vì callback có thể gửi XTest;14 fault/guard tests qua. WirePlumber profile chỉ policy, hardware disabled, private buses/XDG/socket; không viết sessionmanager giả để phản hồi UI. Lưu protocol-control failure khôngpolicy và ba crop gọn, không raw audio/log/private configs hoặc bản sao probe/tmp. Checked/unchecked paints, focus và range track có ratios >=3:1; không chứng nhận mọi theme, mọi trạng thái hoặc WCAG toàn diện. Default helper/Pulse restart probe qua; không đổi code sản phẩm nên không build/unit suite sản phẩm lại.


## System keys private (30/10/2026)

Giữ adapter system_keyboard_private.py và PrivateKeyboard để dùng receiver fixtures hiện có với Enter thật, thay bằng chứng do_action hẹp. [4cases/32Enter](benchmarks/system-keyboard-private-2026-10-30/result.json) giữ localized checks/argv/receiver window/PID/restore và initial unclassified preparation assertion. Không commit raw logs/private desktop entries hoặc thêm bản sao fixture generator. Guard tests cần thiết vì helper gửi native input: host DISPLAY/marker, wrong PID và lost activation phải không gọi XTest. Đây không là chứng nhận third-party monitor packages hoặc toàn bộ Tab route; chooser route còn thiếu được theo dõi riêng.


## System output200 regression (30/10/2026)

Giữ [12fresh native cases](benchmarks/system-output200-regression-2026-10-30/result.json) vì tái hiện đúng nguồn/màn hình từng thất bại, chạy guard restore mới trên host và kiểm lặp top/bottom. Không lặp48 fractional/mixed cases đã đạt hoặc quy lỗi ban đầu đã sửa khi root cause chưa xác định. Restore cooldown đạt không cần reapply, nên recovery retry vẫn chỉ có fault-test acceptance; bốn non-system output200% HDMI cases còn thiếu được ghi riêng.
