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
