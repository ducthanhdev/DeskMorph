# Bàn phím và accessibility

G5.9 trong kế hoạch triển khai **chưa chốt**. Tài liệu này tách các hành vi đã có bằng chứng khỏi phần còn cần kiểm tra; không phải tuyên bố tuân thủ WCAG hay chứng nhận trình đọc màn hình.

## Các thao tác hiện có

- Studio: Tab/Shift+Tab giữa nút điều hướng và các control; Enter chọn trang. Checkbox dùng Space, range/select dùng phím của control native.
- Studio → Taskbar Studio → Điều khiển Dock bằng bàn phím: Enter chuyển sang nút launcher của Dock, kể cả khi tự ẩn. Dock giữ hiện khi DOM và cửa sổ native còn nhận focus; Tab/Shift+Tab giữa các nút, Enter mở popup, Escape đóng rồi Enter mở lại từ nút nguồn. Nút vào Dock disabled khi Dock tắt hoặc placement chưa hỗ trợ; native cũng kiểm tra Dock enabled/visible.
- Màu chủ đạo: nhập `#RRGGBB` rồi Enter hoặc Lưu. Nút lưu vô hiệu hóa khi mã sai hoặc chưa đổi. Ô màu vẫn dùng được bằng chuột; đường bàn phím dùng ô mã màu vì input color của WebKit có thể bị bỏ qua khi Tab.
- Preset: Đổi tên đưa focus và chọn nội dung ô tên; Enter tạo/đổi tên, Hủy trả về ô tên. Xóa preset, ghim hoặc thư mục chuyển focus sang nút xóa kế tiếp/trước; hết danh sách thì về ô nhập tương ứng. Async completion không lấy focus từ control khác.
- Ghép lớp cửa sổ: Enter/Space mở/đóng disclosure; Tab vào textarea. Role button và aria-expanded bổ sung vì WebKit trên môi trường kiểm thử báo summary mặc định là unknown.
- Import/reset: focus vào vùng xem trước để đọc thay đổi, Tab tới Xác nhận rồi Hủy. Không có thay đổi thì bỏ qua nút Xác nhận disabled. Hủy trả về nút mở, xác nhận chuyển sang Hoàn tác; hoàn tác thành công trở về nút mở. Khóa request lặp trong pending; chờ WebView nhận focus lại sau chooser GTK, không lấy focus từ control khác.
- Lịch: một điểm Tab cho vùng ngày; mũi tên ±1/±7 ngày; Home/End đầu/cuối tuần từ thứ Hai; PageUp/PageDown đổi tháng, Shift đổi năm. Giữ ngày hợp lệ gần nhất khi tháng đích ngắn hơn. Enter/Space chọn, Escape đóng.
- Launcher: tìm kiếm, ArrowUp/Down, Ctrl+Home/End và Enter; Escape đóng. Danh sách cửa sổ có ArrowUp/Down, Home/End, Enter và Escape. Dock hỗ trợ Ctrl+Shift+Left/Right để sắp xếp ghim.
- Audio/media/system: khi control tạm disabled trong request, phục hồi focus đúng control sau khi bật lại nếu focus chưa chuyển đi. Control biến mất hoặc thiếu capability mới thì về Đóng. Scope media riêng để completion của audio không lấy focus media và ngược lại; không phục hồi sau native blur, ẩn popup hoặc người dùng chọn control khác.
- Menu ứng dụng Dock: Shift+F10 hoặc phím Menu mở menu của icon đang focus. Tab/Shift+Tab, ArrowUp/Down vòng qua nút enabled, Home/End tới đầu/cuối; Escape đóng và trở về icon nguồn. Request lỗi giữ focus nút nguồn; row biến mất chuyển tới control enabled đầu tiên, có thể là Chi tiết lỗi. Mở xác nhận buộc dừng đưa focus vào Hủy; Hủy quay lại nút Buộc dừng. Mutation pin và các action dùng chung khóa request đồng bộ.

## Bằng chứng và giới hạn

| Phạm vi | Bằng chứng | Giới hạn |
| --- | --- | --- |
| Dock tự ẩn: nút vào từ Studio, Tab/Shift+Tab và bốn popup Enter/Escape/reopen | [Native vi/en](benchmarks/dock-keyboard-2026-10-29.json), `focusWithin.test.mjs` | 14 nút mỗi ngôn ngữ ở profile test; đặt focus nút Studio ban đầu bằng AT-SPI. Chưa kiểm toàn bộ đường từ global shortcut, control bên trong popup hoặc kích hoạt app được ghim |
| Audio/media/system: Tab hai chiều, tên và disabled; radio Space, media Enter, focus sau request/player thoát; chi tiết lỗi/Retry | [Bốn lượt native vi/en](benchmarks/popup-keyboard-2026-10-29.json), `popupFocus.test.mjs` | Audio thật chỉ đọc; điều khiển media chỉ gửi tới fixture. Không kích hoạt system app, không thay sink/volume/mute; chưa chứng minh mọi hotplug/pending/failure hoặc screen reader |
| Menu pin: Shift+F10/Menu, Tab hai chiều, Home/End/mũi tên, Escape, failed launch focus, force review/cancel, row removal và Enter close | [Native vi/en](benchmarks/context-keyboard-2026-10-29.json), [focus Hủy](benchmarks/context-confirm-vi-2026-10-29.png), `contextActions.test.mjs` | Pin và ba cửa sổ fixture; chỉ request đóng window2, xem/hủy force. Enter xác nhận force có bằng chứng bổ sung bên dưới; nhóm chưa ghim và một desktop action có bằng chứng bổ sung bên dưới; chưa chứng nhận mọi ứng dụng/action |
| Lịch: ngày đích, một điểm Tab, Enter/Escape và focus nhìn thấy | [Native và ảnh](benchmarks/calendar-keyboard-2026-10-29.json), `calendarNavigation.test.mjs` | Native X11, đặt focus ban đầu bằng AT-SPI; chưa chứng minh mọi đường vào lịch |
| Thư viện ảnh: phân trang và bỏ yêu thích trong bộ lọc | [Native vi/en, reduced motion](benchmarks/wallpaper-keyboard-2026-10-29.json), `removalFocus.test.mjs` | Enter/Space thật sau đặt focus ban đầu bằng AT-SPI; 26 ảnh fixture, không apply wallpaper, chưa kiểm toàn bộ Tab/filter/chooser hoặc screen reader |
| Focus sau xóa và Enter đổi tên preset | [Native vi/en](benchmarks/removal-focus-2026-10-29.json), `removalFocus.test.mjs` | Không thay thế kiểm tra toàn bộ thứ tự Tab |
| Màu: định dạng, chỉ patch accentColor, disabled khi chưa đổi, theo config/picker | `appearanceColor.test.mjs`, [native vi/en](benchmarks/accent-keyboard-2026-10-29.json) | Native save qua ô mã màu; không tuyên bố chooser native hỗ trợ bàn phím |
| Studio: Tab/Shift+Tab, tên control và disabled | [Năm tab native](benchmarks/studio-tab-2026-10-29.json), [ảnh textarea focus](benchmarks/studio-disclosure-focus-2026-10-29.png) | 279 lượt control trên trạng thái profile test tiếng Việt; có 24 cặp Apply/Favorite nhưng chưa kích hoạt chúng |
| Import/reset: focus review, Cancel, confirm/undo, no-change disabled | [Native vi/en](benchmarks/config-review-focus-2026-10-29.json), `configReviewFocus.test.mjs` | GTK Open được đặt focus bằng AT-SPI rồi Enter; chưa kiểm toàn bộ navigation trong file chooser hoặc trải nghiệm đọc |
| Chữ Dock/Studio/popup: 82 computed-style fixtures | [Trước/sau và ảnh native](benchmarks/contrast-2026-10-29/contrast-after.json), `contrast_audit.py` | WebKit offscreen, cặp màu phẳng được liệt kê; chưa bao gồm gradient, artwork, icon, viền/focus và mọi trạng thái |
| Chữ lịch: ngày/weekday/banner/hôm nay | `calendarContrast.test.mjs` đọc CSS và composite nền trên trắng | Chỉ các cặp màu đã nêu; chưa audit toàn bộ ứng dụng |
| Viền control và focus: 23 fixture ngoài 82 fixture chữ | [Trước](benchmarks/control-contrast-2026-10-29/before.json), [sau](benchmarks/control-contrast-2026-10-29/after.json), `contrast_audit.py` | 18 vòng focus và 5 viền control/hover; ngưỡng 3:1 so hai phía nền phẳng. Selector focus mô phỏng, không kiểm focus native. Studio dùng nền phẳng khai báo thay gradient; chưa bao phủ gradient, mọi control/trạng thái hoặc clipping |
| Scan issues disclosure | `wallpaperScan.test.mjs` kiểm role/aria-expanded khi toggle | Kiểm renderer bằng adapter, chưa thay thế kiểm native với lỗi scan |

`tests/studio_tab_smoke.py` kiểm cây accessibility của Studio: mọi control trong trạng thái hiện tại có tên, Tab theo thứ tự DOM, Shift+Tab đảo ngược và bỏ qua disabled. Chỉ chạy trong profile test `/tmp/deskmorph-desktop-test/config`; không thực thi các nút mở app/quit/autostart/import/reset. Harness chủ động thử Enter/Space trên disclosure đầu tiên và chụp focus textarea. `--studio-tab-only 0..4` cho phép xác minh từng trang. Guard native xác minh desktop không khóa và PID trước khi gửi phím; khi focus bị ứng dụng khác lấy, harness có thể kích hoạt lại đúng Studio test rồi kiểm guard lại.

## Các phần cần hoàn tất trước khi chốt G5.9

Trạng thái hiện tại được đối chiếu trong [REMAINING_ACCEPTANCE.md](REMAINING_ACCEPTANCE.md). Các đoạn dưới ghi lịch sử phát hiện; bằng chứng bổ sung về sau có thể đã giải quyết một phần. Phần còn thiếu cụ thể hiện là tuyến chooser đến Open; system Enter và audio native contrast/output/volume keys đã đạt.

- Kiểm thêm trạng thái động: lỗi/conflict và concurrent review thực tế, thứ tự điều hướng đầy đủ trong hộp thoại file, thao tác wallpaper favorite/filter/paging và focus sau khi control biến mất/disabled. Import/reset review/cancel/confirm/undo đã có kiểm native vi/en.
- Kiểm đường vào/ra Dock và popup chỉ bằng bàn phím, cùng audio/media/system/context/window actions, kể cả thiếu capability/lỗi và pending.
  Nút vào Dock từ Studio, thứ tự Tab hai chiều và mở/đóng/mở lại launcher/audio/system/calendar trên Dock tự ẩn đã có bằng chứng vi/en. Control bên trong popup và các trạng thái lỗi/pending còn mở.
  Audio/media/system có thêm audit vi/en ở trạng thái thường và audio service thiếu: radio group dùng checked Tab stop, disabled bị bỏ qua, media giữ focus sau Play/Pause, player biến mất về Đóng. Lỗi audio có Enter/Space chi tiết và Enter Retry. Còn context/window actions, system launch failure/pending, thiết bị audio biến mất trong lúc thao tác và các capability thay đổi khác.
  Menu pin đã kiểm vi/en với fixture: keyboard entry/navigation, launch failure, force review/cancel, external row removal và Enter close. Xác nhận force bằng phím đã có bằng chứng bổ sung bên dưới; nhóm chưa ghim và desktop action đã có kiểm fixture vi/en bên dưới; pending/failure của mọi action vẫn chưa được chứng nhận.
- Tiếp tục audit contrast và focus nhìn thấy: 82 fixture chữ hiện đã qua, gồm Dock trên trắng/đen tại opacity .2/.8/.85/.92/1 và một số màu Studio/popup. Chưa bao phủ gradient, icon/artwork, màu accent tùy chỉnh, control borders, focus rings và mọi trạng thái động. Ảnh hoặc tính toán cặp màu riêng lẻ chưa chứng minh toàn bộ.
- Kiểm trình đọc màn hình thực tế, thứ tự đọc/announcement và tác động của role/aria trên WebKit phiên bản mục tiêu. AT-SPI tree chứng minh API được expose, chưa chứng minh trải nghiệm đọc đầy đủ.

## Chạy audit contrast đã có

```sh
/usr/bin/python3 -m unittest discover -s tests -p contrast_audit_test.py
/usr/bin/python3 tests/contrast_audit.py --output /tmp/contrast.json --screenshot /tmp/contrast.png --enforce
/usr/bin/python3 tests/desktop_smoke.py --contrast-native-smoke
```

Audit computed-style dùng context WebKitGTK ephemeral trong Gtk.OffscreenWindow; không xuất cửa sổ, không inject input. Nó đọc màu/opacity/nền từ CSS thật rồi composite alpha và tính luminance sRGB, ngưỡng chữ 4.5:1 không làm tròn trước khi so. Hover được mô phỏng bằng selector `.test-hover`, animation/transition tắt; gradient không được tự quy thành màu phẳng. `--css` cho phép đo baseline bằng cùng harness, báo cáo giữ SHA-256 stylesheet.

Kiểm native dùng profile test, bật clock/stats và tắt auto-hide tạm tại opacity .2/1, chờ layout ổn định rồi crop đúng controls. Kiểm pixel nền #172235 có tolerance 1/channel, xem ảnh để xác nhận đúng nội dung; pixel nền không tự chứng minh tương phản chữ anti-aliasing hay mọi foreground. Finally khôi phục bytes config và khởi động lại profile test. Không sửa hình nền hay ứng dụng của người dùng.


Audit 29/10/2026 bổ sung tương phản phi văn bản: 105 fixture tổng, gồm82 chữ và23 focus/viền. Baseline có5 ca viền dưới3:1 (nút Studio thường/hover, input, textarea, nút audio); sửa border Studio/audio thành #8291a8, hậu kiểm105/105 qua. Mỗi chỉ báo phải có độ rộng dương, tỷ lệ lấy nhỏ nhất giữa nền trong và ngoài control. Focus/hover được ánh xạ selector trong offscreen fixture; không dùng kết quả này để khẳng định mọi vòng focus xuất hiện khi bấm phím, không bị clip, hoặc được screen reader đọc. Các select có background-image, checkbox/range, icon/gradient/artwork và màu accent tùy ý chưa được bao phủ bởi tập mới. G5.9 vẫn mở.


Thư viện wallpaper nay phục hồi focus khi favorite đang focus bị gỡ khỏi danh sách lọc: tới favorite cùng vị trí/cái trước, hết ảnh thì về tìm kiếm. Nút phân trang thành disabled chuyển tới nút phân trang enabled còn lại. Nếu người dùng chuyển focus sang control khác hoặc native window blur, không lấy focus lại. Ca native vi/en với reduced motion đã qua phân trang hai chiều và bỏ favorite cuối; chưa thay thế kiểm apply pending/failure, mọi bộ lọc hoặc toàn bộ luồng bằng Tab.


Bổ sung bộ lọc wallpaper: [native vi/en, reduced motion](benchmarks/wallpaper-filters-keyboard-2026-10-29.json) dùng27 ảnh PNG/JPEG ở hai thư mục. Home/End trên select thư mục và định dạng kiểm cả giao không có kết quả; Z/Backspace trong tìm kiếm kiểm rỗng/khôi phục. Focus giữ ở control đang lọc; chạy lại các ca pagination/favorite. Số ảnh/trang có role=status và aria-atomic=true; đây là contract live region, chưa là bằng chứng trình đọc màn hình đã phát announcement. AT-SPI seed focus cho từng control, chưa chứng minh đường Tab toàn luồng.


Apply/Shuffle/Retry wallpaper dùng scope focus request riêng: giữ focus ở nút nguồn sau khi re-enable; Retry biến mất sau thành công thì về tìm kiếm. Favorite/pagination đặt ranh giới scope để tiếp tục dùng quy tắc cùng index/nút phân trang của thư viện. [Native vi/en, reduced motion](benchmarks/wallpaper-actions-keyboard-2026-10-29.json) qua Enter Apply thành công, file mất/error, phục hồi file/Retry và Shuffle, đối chiếu GSettings sáng/tối trong keyfile riêng. IPC native không bị chèn delay: chưa đo trạng thái pending dài hoặc thao tác chuyển focus trong lúc request thật đang chờ; các ngữ nghĩa đó có test hook riêng. Không đổi hình nền host và không khẳng định compositor đã hiển thị pixel wallpaper từ việc đọc settings.


Bổ sung [xác nhận buộc dừng bằng bàn phím vi/en](benchmarks/context-force-keyboard-2026-10-30/result.json): sau khi đóng fixture window2 và gỡ window3, mở lại menu của window1, Enter vào review, kiểm focus ban đầu ở Hủy, Tab tới Xác nhận buộc dừng và Enter. Popen fixture thoát (exit1 do X server ngắt kết nối qua xkill), popup đóng; không chỉ suy từ IPC thành công. Guard environment xác minh fixture class/profile trước thao tác; cả hai PID fixture và các app test cũ đã thoát, bytes config được khôi phục. Vẫn chưa chứng minh nhóm chưa ghim, desktop actions, contrast toàn ứng dụng hoặc trải nghiệm screen reader.


Bổ sung [tương phản gradient Studio](benchmarks/studio-gradient-contrast-2026-10-30/result.json): `contrast_audit.py` nay có113 fixture, gồm105 ca trước và8 ca chữ giữ nguyên hai radial gradient của `.studio-app` cùng nền card trong suốt. Từ computed style WebKitGTK2.52.6, lấy cận RGB cho mọi stop/composite, rồi cận luminance để tính tỷ lệ thấp nhất bảo thủ. Help/dim thấp nhất6,676:1; cả8 ca vượt4,5:1. Foreground phải opaque, group opacity phải1; URL và interpolation space khác bị từ chối. Đây là cận dưới trên toàn gradient, không dùng màu phẳng thay gradient và không khẳng định từng pixel đã được đo. Cận không đạt cần phép đo bổ sung, không tự kết luận lỗi UI. Icon/artwork/accent tùy chọn, checkbox/range native, clipping và toàn ứng dụng vẫn chưa được chứng nhận. Bốn math reference tests kiểm alpha bounds, unsupported layers, continuous samples và foreground luminance crossing; audit không gửi chuột/phím.


Bổ sung [menu chưa ghim và desktop actions vi/en](benchmarks/context-desktop-actions-2026-10-30/result.json): private desktop entry nhận diện ba cửa sổ fixture qua StartupWMClass. Shift+F10 mở menu, Tab/Shift+Tab đi toàn bộ10 control enabled; Enter gọi desktop action ghi marker riêng và không gọi Exec mặc định, rồi kiểm Exec mặc định bằng marker khác. Enter Ghim/Bỏ ghim lưu đúng desktop ID và phục hồi mọi config field; finally khôi phục bytes, dọn catalogue/fixtures và mở normal test instance. AT-SPI đặt focus ban đầu và source của từng action, không tuyên bố toàn bộ luồng chỉ dùng Tab từ khi mở app. Chỉ fixture action/Exec, không mở ứng dụng người dùng hoặc chứng nhận mọi desktop action.


Bổ sung [audio hotplug khi đang điều hướng](benchmarks/audio-keyboard-hotplug-2026-10-30/result.json): trên private PipeWire/Pulse server, tạo nondefault null sink, đặt focus ở radio của sink đó, unload module thật rồi kiểm radio biến mất và focus chuyển về Đóng. Output mặc định đang dùng được giữ nguyên; không giả event UI hoặc xóa thiết bị host. Cùng lượt chạy qua12 restart service/core, UI mute/volume sau reconnect, một subscription khi hiện và dọn khi ẩn/reopen. Đây là fixture sink biến mất khi đang có focus, chưa phải removal đồng thời với request volume/default đang pending hoặc headset vật lý.


Ca [Orca speech bật thật](benchmarks/orca-speech-2026-10-30/result.json) hiện **chưa đạt** trên Orca49.4/AT-SPI2.58.1. `python3 tests/screen_reader_smoke.py` tạo Speech Dispatcher/socket/preferences và null sink riêng, kiểm playback stream trỏ đúng sink, ghi waveform tạm rồi chạy context keyboard suite gốc. Lượt mặc định có111 speech-output events, đọc tên fixture/nút Mở ứng dụng và có435703 sample âm thanh khác0, nhưng dừng khi Orca dùng End để điều hướng caret thay vì Home/End của app. Phần đọc nhãn/Tab là bằng chứng hẹp, không chứng minh thứ tự đọc/announcement toàn ứng dụng hoặc khả năng hiểu lời nói. Log còn có Orca segmentation fault quanh xử lý defunct accessibles lúc teardown; chưa xác định nguyên nhân/trách nhiệm phía sản phẩm. Hai đối chiếu phím focus mode không đạt và đã gỡ khỏi shared driver; không bỏ assertion Home/End để tạo pass. Reader/helper/null sink đã dọn hết, bytes cấu hình test khôi phục. Audio có cả startup reader, không gán mỗi sample cho một nhãn; raw logs/audio/preferences chỉ ở/tmp. G5.9 tiếp tục mở.


Đối chiếu tiếp bằng `DESKMORPH_ORCA_NAVIGATION=application python3 tests/screen_reader_smoke.py` cũng **chưa đạt**: yêu cầu `caretNavigationEnabled=false` và `structuralNavigationEnabled=false` trong general/default profile riêng, nhưng debug vẫn ghi WebKitGTK script của DeskMorph bật caret navigation. Orca49.4 đã cài khởi tạo `_default_caret_navigation_enabled=True` trong web script và `default.activate()` đặt trạng thái từ field này sau khi load app settings; chưa sửa hoặc kết luận lỗi upstream từ khảo sát đó. Vì vậy lượt này chưa phải bằng chứng “chế độ đọc văn bản đã tắt”.61 speech events,295819 sample khác0, fixture được đọc; vẫn dừng ở Home/End navigation assertion. Reader còn sống trước cleanup nhưng exit−11/segfault được ghi sau cleanup, chưa xác định thời điểm lỗi độc lập với teardown. Profile bytes/default audio phục hồi,0 helper/sink còn lại. Runner giữ tùy chọn đối chiếu và phân biệt cấu hình yêu cầu với trạng thái quan sát; diagnostics mới đã compile, chưa chạy GUI thêm sau bổ sung báo cáo. G5.9 tiếp tục mở.


Đối chiếu Alt+Backspace chạy qua **toàn bộ context keyboard suite vi/en**:16 lần bật/tắt bypass navigation có log xác nhận, giữ nguyên Tab/reverse/Home/End/arrows/Escape, failed launch, force cancel/confirm và owned fixture exit. Bypass là lệnh thật của Orca49 Alt+Backspace; không coi đây là default reader tương thích Home/End trực tiếp. [Bản ghi](benchmarks/orca-bypass-context-2026-10-30/result.json) giữ baseline353 speech events/1294348 sample khác0 nhưng thiếu lỗi launch lẫn warning force.

Bản được giữ lại (`38490a…`) bổ sung ID riêng cho summary chữ trực tiếp của ErrorText, liên kết launch source với summary; force review dùng **nonmodal alertdialog**, warning paragraph liên kết tới cả Hủy/Xác nhận. Lượt native/Orca vi/en trên binary này qua toàn bộ keyboard suite,395 speech events/1489779 sample khác0, đã đọc warning force ở cả hai ngôn ngữ. Launch error có native description nhưng chưa được phát tự động: speech acceptance tổng vẫn `passed:false`, G5.9 còn mở. Chỉ chốt cải thiện description/warning đã có bằng chứng; không tuyên bố sửa toàn bộ live announcements.

`DESKMORPH_CONTEXT_DESCRIPTION_LAB=1 python3 tests/negative_origin_smoke.py` bổ sung [4 ca native description](benchmarks/context-description-lab-2026-10-30/result.json), vi ở scale1/en ở scale2, Dock trên/dưới. Pin fixture chỉ có command cố ý không tồn tại trong root lab; XTest Shift+F10 riêng và AT-SPI thực thi/đọc description, giữ source focus sau lỗi; cùng16 ca placement qua. Không reader, không physical pixel/WM proof trong lab này. Probe WebKit riêng xác nhận plain paragraph/dynamic direct span có description, composite alert/aria-description rỗng; vì vậy không trỏ description vào alert có nút Chi tiết.

Thử nghiệm tiếp theo đưa summary vào live text region tồn tại sẵn chưa được chấp nhận: hai lượt dừng ở GTK/WebKit script navigation/settling, không có bằng chứng cải thiện announcement. Đã gỡ thử nghiệm và rebuild, SHA256 trở về **đúng38490a…** đã đo; không giữ một sửa đổi chưa chứng minh. Helper nay chờ WebKit script ổn định trước khi toggle bypass; guard mới phát hiện đúng lần reader không sẵn sàng, chưa có full acceptance riêng trên bản sản phẩm đã khôi phục. Các failure giữ trong JSON, không bỏ assertions.

55/55 frontend tests, TS/Vite/custom-protocol build,113/113 contrast, Python compile/diff check qua. Runner dùng SPT_NOENV=1 sau khi probe setproctitle tái hiện mất environ marker; driver metadata riêng không lan ownership marker tới normal app. Giữ hai lỗi chuẩn bị stream/ownership và composite-description failure; nguyên nhân stream mismatch đầu chưa xác định vì thiếu target indices ở lượt đó. Audit cuối0 live speech/geometry lab helper,0 owned speech sink, config bytes phục hồi. Raw speech/debug/probe ở/tmp, không commit audio hoặc lời đọc ngoài fixture.


Đối chiếu [Orca trong môi trường riêng](benchmarks/orca-isolated-launch-2026-10-30/result.json) giữ nguyên lỗi launch trên binary38490a…: native description đúng và source giữ focus, nhưng chờ8giây vẫn không có lời đọc lỗi. Ba lượt baseline trên monitor dương trong drawable đều có11 speech-output lines và âm thanh khác0; không còn chỉ dựa vào monitor âm ngoài drawable hoặc giả thuyết suite chuyển focus quá nhanh. Hai thử nghiệm persistent live summary (empty/U+200B) cũng không cải thiện, đã gỡ; build trả về đúng hash đã chốt.

Observer riêng lọc PID/marker của cả native app và WebKit descendants ghi nhận328 children-added,0 text-insert/announcement/description-change trong lượt cuối. Orca có log bỏ qua children event từ live region; dữ liệu này chưa xác định lỗi nằm ở WebKit hay Orca. Observer ban đầu chỉ lọc PID native nên thiếu web-process events, không dùng lượt đó để kết luận event không phát. Probe HTML tối giản chỉ đọc frame, chưa tới document/button nên bị loại khỏi kết luận sản phẩm. Một lỗi chuẩn bị thấy playback sink index4294967295; helper tạm đã đổi sang chờ stream resolve đúng sink, không bỏ routing assertion.

Chỉ chạy vi/scale1/Dock trên trong đối chiếu này, không thay thế native vi/en keyboard regression hoặc kiểm host WM. Audit cuối không còn helper/sink thuộc lab; default sink giữ nguyên qua cleanup assertions. Không lưu raw speech/audio/config hoặc đưa script chẩn đoán sao chép vào repo. G5.9 vẫn mở; không gọi các thử nghiệm này là bản sửa announcement.


Bổ sung [launcher glyph contrast](benchmarks/launcher-glyph-contrast-2026-10-30/result.json): biểu tượng Sparkles của nút mở ứng dụng có nền opaque#e2e8f0 riêng, stroke#0c1017; dùng cùng class ở Dock và preview Studio.24 ca lấy SVG từ lucide-react đang cài, launcher28/34/54px, accent đen/tối/trắng/mặc định, thường/hover. Cận stroke/background đạt15,456:1, vượt3:1; SVG/backplate nằm trong button. Nền ở tâm glyph cố định nên không phụ thuộc gradient người dùng chọn. Trước sửa,12 ca accent tối không đạt cận bảo thủ; cận1:1 không có nghĩa mọi pixel glyph đều có tỷ lệ1:1. [Ảnh trước](benchmarks/launcher-glyph-contrast-2026-10-30/before.png), [sau](benchmarks/launcher-glyph-contrast-2026-10-30/after.png) đã xem.

Tổng audit hiện137/137 (113 ca cũ+24 SVG),4 reference tests và55/55 frontend tests; TS/Vite/native custom-protocol build qua. Binarye107a79a… qua16 native popup placements và4 description/focus cases vi/en, scale1/2, top/bottom trong lab riêng. [Ảnh native Dock](benchmarks/launcher-glyph-contrast-2026-10-30/native-dock.png) trên monitor dương/Xvfb, accent tối xác nhận phần render mới; không WM hoặc input host. Hover là selector fixture, không chứng minh toàn bộ focus ring/clipping; native widgets, icon khác và speech vẫn cần kiểm riêng. Không chạy lại Orca ở binary mới nên không nâng kết quả speech trước đó thành acceptance mới. G5.9 tiếp tục mở.


[Kiểm native controls Studio](benchmarks/studio-native-controls-2026-10-30/result.json) phát hiện checkbox dùng dấu tick trắng trên accent#48b9c7 chỉ2,323:1; núm trượt trắng so với phần track đã tô cũng2,323:1. Đo màu thật từ pixel native, không suy màu checkmark/thumb từ computed CSS. Thêm token control riêng#278b98 cho Toggle/Range: hậu kiểm cảvi/GTK scale1 vàen/scale2 cho tick/fill và thumb/fill đạt4,013:1, fill/unfilled4,615:1; đối chiếu các mảng màu phẳng, không gán tỷ lệ cho pixel anti-aliasing.

`DESKMORPH_STUDIO_WIDGETS_LAB=1 /usr/bin/python3 tests/negative_origin_smoke.py` dùng positive monitor trên Xvfb/bus/profile riêng; Space đổi checked/native config rồi phục hồi, Tab/Shift+Tab tới checkbox kế/trước, arrows tăng/giảm range, Home/End đổi/khôi phục select. Tab từ nút nav cuối bỏ qua preview/restore disabled để tới checkbox đầu. AT-SPI seed focus, không tuyên bố toàn bộ hành trình từ lúc mở app chỉ dùng Tab. Ảnh native có outline#67e8f9 ở cả hai scale và bounds control trong window; [checkbox](benchmarks/studio-native-controls-2026-10-30/after-checkbox-scale2.png), [range](benchmarks/studio-native-controls-2026-10-30/after-range-scale2.png), [select](benchmarks/studio-native-controls-2026-10-30/select-focus-scale2.png) đã xem. Pixel hiện diện không tự chứng minh mọi cạnh outline hoặc mọi màn hình đều không clip.

Giữ hai lỗi phép đo: WebKit trả checkbox bounds cả label nên phải crop ô vuông bên phải của row không help; GdkPixbuf nhận tọa độ logical và trả device pixels, crop scale2 cũ đã lấy sai vùng/double size. Hậu kiểm đổi đơn vị và assert root scale/kích thước PNG, không bỏ focus/pixel assertions. Binary0da7257f… qua16 popup allocation+4 description/focus cũ và137/137 computed contrast; build TS/Vite/custom-protocol qua. Không đổi JS/Rust nên không chạy lại unit suites. Chỉ field cấu hình fixture phục hồi, revision tăng đúng theo thao tác;0 helper còn sống, không input/config/audio host. Select arrow/border contrast, các control khác và Orca launch announcement vẫn chưa được chứng nhận; G5.9 còn mở.


## G5.9 — Lỗi mở ứng dụng được Orca đọc qua ATK native (30/10/2026)

[Bằng chứng đối chiếu](benchmarks/orca-native-announcement-2026-10-30/result.json): binary0e732e01… qua4/4 ca vi/scale1 vàen/scale2, Dock trên/dưới, trong Xvfb/bus/profile riêng. Shift+F10 và Enter thật trên display riêng gây lỗi command cố ý không tồn tại; native description đúng, nguồn giữ focus, Orca phát summary đúng ngôn ngữ và có waveform trên null sink sở hữu. Cả4 reader thoát0 qua Quit chính thức. Baselinee107a79a… dùng cùng phép đo/đọc log sau Quit vẫn không đọc lỗi, dù native description/focus đúng và có speech khác. Không suy khả năng người nghe hiểu từ waveform.

WebKitGTK2.52.6 core queue LiveRegionChanged nhưng switch AT-SPI platform không có case xử lý; probe DOM có focus/document hợp lệ cập nhật text mà không có text-insert/announcement. Dùng standard ATK `notification` (assertive), fallback runtime `announcement`; không gửi trực tiếp vào Orca. Command native chỉ cho menu đang visible/focused/active với generation hiện tại, kiểm giới hạn message. Giữ DOM alert/description và focus, dedupe cùng lỗi/rerender; retry lỗi giống nhau vẫn thông báo. Unsupported API giữ feedback DOM. Guard stale/blur được unit test, chưa có native negative-case acceptance riêng.

[Hồi quy GNOME thật vi/en](benchmarks/orca-native-announcement-2026-10-30/keyboard.json) qua Shift+F10/Menu, Tab/Shift+Tab, disabled skip, arrows/Home/End, Escape trả focus, lỗi launch, force review/cancel, removed-row fallback, Enter đóng và confirm force chỉ trên fixture sở hữu. Config phục hồi. Đây là hồi quy không bật Orca; không thay thế suite có Orca/warning/default browse mode trên binary mới.

55/55 frontend,87 Rust pass/5ignored, TS/Vite/native custom-protocol build qua. Giữ test frontend retry/dedupe/locale và Rust guards vì bảo vệ lỗi cụ thể; giữ helper speech opt-in để tái lập tích hợp thật. Không thêm test mirror implementation, không commit raw speech/audio/profile/upstream source. Harness giữ tiêu chí exit0: SIGTERM từng timeout (-9), sửa bằng private D-Bus Quit; chạy song song từng bị Orca CLI chặn toàn user, nay chạy tuần tự và preflight reader, tuyệt đối không --replace. Sửa tọa độ negative bị sót trong mode positive; không bỏ bounds assertions. Log debug đọc sau reader stop vì tail buffered. Audit cuối0 helper/sink lab, default audio không đổi.

Chốt riêng launch announcement, không chốt G5.9: còn full tab/focus clipping/contrast và screen-reader regression rộng hơn; G2.10 cũng mở. Tổng97/99, release no-go.


## G5.9 — Cuộn control và focus trên ảnh trong Studio (30/10/2026)

[Kiểm native năm trang](benchmarks/studio-focus-scroll-2026-10-30/result.json) phát hiện hai lỗi thật: ô accent bị cắt11px ở đáy khi Tab, và outline nút áp dụng hình nền bị parent overflow:hidden cắt hoàn toàn (0 pixel focus). Bản sửa cuộn cả nhãn/control vào scrollport với margin8px; dùng viền focus bên trong thẻ ảnh, có nền tối riêng để nhận biết trên ảnh sáng/tối.

Binary1172029a… qua cảvi/scale1 vàen/scale2: mỗi ngôn ngữ208 Tab stops trên5 trang, Tab/Shift+Tab đúng thứ tự và bỏ qua disabled, disclosure mapping mở/textarea/collapse đạt. Mỗi lượt203 control sau nav seed được đo bounds nằm trong window và có focus pixel: tổng406.12 select có arrow/fill6,919:1, border/fill5,546:1, border/exterior tối thiểu5,508:1. Focus trên hai fixture ảnh đen/trắng có ring/backing13,145:1, kiểm pixel ảnh đã load thật. Không thao tác setting, bytes config nguyên vẹn.

Harness dùng nav landmark thay first5buttons, vì status Details có thể đứng trước nav; chọn đúng disclosure mapping theo nhãn. Đường Tab bắt đầu từ nav seed, không kiểm status disclosures đứng trước nav hoặc mọi dynamic state. Bounds trong window và pixel focus không tự chứng nhận mọi cạnh ring/ancestor clipping ở mọi trạng thái. Fixture ảnh đen/trắng thuộc lab, không lưu ảnh/tên file cá nhân. [Focus accent](benchmarks/studio-focus-scroll-2026-10-30/accent-focus.png) và [focus ảnh đen](benchmarks/studio-focus-scroll-2026-10-30/wallpaper-black-focus.png) đã xem.

55/55 frontend, TS/Vite/native build, Python compile/diff check qua. Giữ native test vì bắt hai regression thực mà test CSS/điều hướng thuần trước đó bỏ sót; không thêm unit test mirror scrollIntoView. Rust không đổi nên không chạy lại Rust suite. G5.9/G2.10 tiếp tục mở,97/99; cần hồi quy screen reader rộng hơn và DPI/host WM.


## G5.9 — Tương phản biểu tượng chức năng (30/10/2026)

[Bằng chứng](benchmarks/functional-glyph-contrast-2026-10-30/result.json):209/209 computed-style cases đạt, gồm72 ca mới cho glyph Dock, context menu, đóng cửa sổ và launcher. Render lucide-react đang cài với kích thước thật (X context14px, X đóng cửa sổ16px), CSS/control classes thật, nền đen/trắng, thường/hover khi có. Cận tương phản nhỏ nhất trong72 ca mới là5,246:1 (yêu cầu3:1); SVG bounds nằm trong parent. Lưu riêng72 kết quả mới, hash CSS/runner và tổng suite; không nhân bản137 ca cũ hoặc raw computed tree.

Đây là cận bảo thủ từ màu stroke/background và gradient stops trong WebKitGTK offscreen, không chứng nhận artwork/logo ngoài, native controls, focus bàn phím hay toàn bộ accessibility. Không đổi mã sản phẩm; không rebuild hoặc lặp unit suite sản phẩm. G5.9 vẫn mở, tổng97/99.


## G5.9 — Hồi quy Orca trên bản hiện tại đã đạt (30/10/2026)

[Bằng chứng GNOME thật](benchmarks/orca-current-regression-2026-10-30/result.json): binary1172029a… qua toàn bộ context keyboard suite vi/en với Orca bật: Tab/reverse, disabled skip, arrows/Home/End, Escape/source focus, launch error, force review/cancel/confirm và owned fixture exit.342 speech-output lines,1409877 sample khác0; cả tên fixture, Hủy/Cancel, Mở/Open, lỗi launch và warning force hai ngôn ngữ đều được ghi nhận.16 lần bật và16 lần tắt bypass navigation của Orca bằng Alt+Backspace được xác nhận; không coi là default-reader Home/End compatibility.

Harness chờ stream4294967295 resolve về đúng owned sink trước input; sau suite kiểm route lại, xác minh PID service Orca bằng D-Bus rồi gọi Quit chính thức, đợi exit0 trước đọc debug tail. Reader sống suốt suite, không ghi segfault, helper đã thoát và default audio giữ nguyên; config fixture phục hồi. Giữ thay đổi harness vì sửa race/flush và ownership của kiểm tích hợp, không thêm test mirror implementation. Raw audio/debug/preferences ở/tmp, JSON chỉ giữ counts/hash/fixture assertions. Chưa kết luận tính dễ nghe của speech hoặc toàn ứng dụng từ suite menu; G5.9 chờ audit cuối các yêu cầu gốc.


## G5.9 — Audio native keys và tương phản control đã đạt (30/10/2026)

[Bằng chứng](benchmarks/audio-native-controls-2026-10-30/result.json): binary1172029a… qua4/4 GNOME/Xvfb private cases, vi/scale1 vàen/scale2, Dock trên/dưới. XTest Space chọn outputB rồi phục hồiA; Right/Left ghi volumeB từ37 lên38 rồi về37; Space mute/unmuteB, kiểm readback thật và focus sau request. Không dùng AT-SPI set-value/do-action cho các mutation audio. Hai sink đều factory support.null-audio-sink, private socket, không hardware modules.

20 native captures có focus pixel và bounds trong popup: checked white mark/thumb với blue fill3,769:1, blue/exterior4,463:1, filled/unfilled track4,702:1, focus/exterior10,017:1. Unchecked light paint (checkbox border/radio body) so dark paint17,910:1 và exterior16,820:1. Đo các mảng màu thật, không suy từ CSS hoặc pixel anti-aliasing. Ba crop đã xem được giữ để review; palette counts/hash/bounds/ratios trong JSON, không commit toàn window/log/profile.

Lab cũ không có session manager: pactl trực tiếp cũng chỉ đổi default.configured.audio.sink sangB trong khi default.audio.sink vẫnA. Giữ failure này như thiếu precondition, không quy lỗi Space/sản phẩm. PrivateAudioServer nay có opt-in WirePlumber0.5 policy thật, hardware audio/bluetooth/video disabled, session/system bus và XDG riêng. Policy mode không tự ghi default metadata; WirePlumber hoàn tất selection. Nhánh mặc định khôngpolicy và Pulse restart probe vẫn qua. Không cài package host.

Giữ audio_native_controls.py và callback chỉ dành private DISPLAY vì kiểm trực tiếp integration keys/daemon/pixel còn thiếu;14 probe/orchestration tests qua, gồm guard từ chối callback trước truy cập display/app của host. Python compile/diff check qua. Không đổi sản phẩm nên không rebuild/lặp frontend/Rust suite.0 live app/Xvfb/GNOME/PipeWire/Pulse/WirePlumber lab cuối lượt. Chốt riêng audio; G5.9 còn system Enter/chooser route theo REMAINING_ACCEPTANCE.md, G2.10 vẫn mở, tổng97/99.


## G5.9 — Enter thực cho tiện ích hệ thống vi/en (30/10/2026)

[Bằng chứng private GNOME](benchmarks/system-keyboard-private-2026-10-30/result.json):4/4 cases vi/scale1, en/scale2 ×Dock trên/dưới,32 lần XTest Enter thực. Receiver fixtures hiện có kiểm primary monitor launch bị GIO từ chối rồi fallback mở GTK thuộc lab; Downloads giữ argv/path có khoảng trắng và literal shell characters; Downloads mất không tự tạo/launch, phục hồi rồi Enter retry đạt; Trash chỉ gửi trash:/// và không đổi sentinel; capability thiếu làm disabled và có lý do localized. Config bytes và fixture files phục hồi/dọn đúng.

Tái dùng system_locations_smoke.py, chỉ thêm language/report_root tùy chọn; đường cũ mặc định vi giữ nguyên. Adapter mới seed focus AT-SPI rồi Enter, không gọi do_action cho system mutations; PrivateKeyboard kiểm private marker/DISPLAY, owned PID và native activation trước XTest. Hai guard tests (4 subcases) chặn DISPLAY/marker sai, PID sai và focus đổi trước input; compile/diff check qua. Không đổi mã sản phẩm nên không build/lặp unit sản phẩm.

Giữ một initial private driver AssertionError không có stacktrace, không quy lỗi sản phẩm hoặc coi pass; thêm traceback rồi lượt đầy đủ đạt, chưa xác định nguyên nhân failure chuẩn bị đầu.0 live system/geometry/WM/DPI helpers sau suite. Chốt system Enter; G5.9 còn tuyến bàn phím chooser→Open, G2.10 vẫn mở. Tổng97/99.


## Chốt G5.9 trong môi trường tham chiếu — 30/10/2026

[Chooser native4/4](benchmarks/chooser-keyboard-private-2026-10-30/result.json) bổ sung phần còn thiếu: private GNOME/Xvfb, vi/scale1 vàen/scale2, Dock trên/dưới. App cwd và GTK startup-mode=cwd riêng đặt thư mục fixture ban đầu; sau đó chỉ XTest Tab/Home chọn file, Tab/ShiftTab đến Open, Enter mở review, Tab/Cancel trả focus trigger. Không đặt focus/selection bằng AT-SPI trong chooser. Escape chooser và config bytes không đổi đều được xác nhận. Không suy mọi cách duyệt filesystem hoặc filename completion từ fixture này; diagnostic trước được ghi riêng, không tính pass.

[Kiểm toán cuối](REMAINING_ACCEPTANCE.md) đối chiếu G5.9 gốc và chốt phạm vi GNOME X11 tham chiếu. Các đoạn còn-mở phía trên là lịch sử theo thời điểm; giữ giới hạn cụ thể của từng báo cáo. Đây không phải chứng nhận WCAG toàn diện, mọi trạng thái/theme hay mọi cấu hình Orca.

Chạy lại riêng: `DESKMORPH_CHOOSER_KEYS_LAB=1 DESKMORPH_PRIVATE_GNOME_WM=1 /usr/bin/python3 tests/negative_origin_smoke.py`. Cần Xvfb/GNOME có sẵn; runner tạo display/bus/XDG/keyfile riêng, không input desktop host.
