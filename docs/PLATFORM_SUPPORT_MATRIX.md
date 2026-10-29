# Ma trận phiên bản và luồng cốt lõi

Ma trận này là phạm vi công bố của bản development hiện tại. `Verified` nghĩa là
luồng sản phẩm đã chạy trên đúng phiên bản ghi dưới đây; `Experimental` nghĩa là
chỉ một capability đã chạy và không được dùng để hứa hỗ trợ toàn desktop;
`Unsupported` nghĩa là UI phải giữ trạng thái thiếu hỗ trợ.

| Tổ hợp đã kiểm | Trạng thái | Luồng đã kiểm và bằng chứng |
| --- | --- | --- |
| Pop!_OS 24.04, GNOME Shell 46.0, X11, x86_64 | Verified | Dock/launcher/window grouping/focus/keyboard, Studio vi/en, Apply/Retry/Shuffle wallpaper, audio/media/system widgets, restart và error paths; các lượt native cuối ghi trong `docs/PROGRESS.md` và benchmark tương ứng. |
| GNOME Shell 46 / Mutter 46.2 Wayland, output ảo scale 1 | Experimental, wallpaper-only | Studio vi/en Apply/Retry/Shuffle và light/dark wallpaper pixels đã chạy trong [wallpaper-visible](benchmarks/wallpaper-visible-2026-10-29/results.json). Window management, placement và auto-hide vẫn unsupported theo [WAYLAND_ADAPTER_DECISION](WAYLAND_ADAPTER_DECISION.md). |
| COSMIC cosmic-bg 1.11.0 (9520e16), cosmic-comp 8cb1802, KWin-independent nested output `WINIT-0` | Experimental, wallpaper-only | Studio vi/en, tạo config thiếu, invalid/read-only, Apply/Retry/Shuffle và pixels đã chạy trong [cosmic-studio](benchmarks/cosmic-studio-2026-10-29/results.json). Không công bố Dock/window management, multi-monitor hoặc scheduler COSMIC. |
| KDE Plasma 5.27.12 / KWin 5.27.11 | Unsupported | API `evaluateScript` đã nghiên cứu trong [KDE report](benchmarks/kde-wallpaper-research-2026-10-29/results.json), nhưng chưa có visible-pixel/readback proof; sản phẩm không bật adapter. |

Các tổ hợp không có trong bảng không thuộc phạm vi hỗ trợ công bố. Mỗi bản ghi
phải giữ version, output và giới hạn; không suy từ một output nested thành hỗ trợ
mọi màn hình, DPI hoặc desktop khác.
