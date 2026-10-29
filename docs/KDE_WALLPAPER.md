# KDE Plasma wallpaper research

KDE Plasma 5.27.12 exposes the wallpaper API through `org.kde.plasmashell` at
`/PlasmaShell`, method `org.kde.PlasmaShell.evaluateScript`. The script shipped
by KDE's `setaswallpaper.desktop` selects `org.kde.image`, enters the
`[Wallpaper, org.kde.image, General]` group, and writes the `Image` file URI for
each desktop returned by `desktopsForActivity(currentActivity())`.

A private KWin 5.27.11 virtual Wayland compositor and Plasma shell were started
with private XDG and D-Bus state. The method call returned successfully, which
confirms API ownership and method shape. This is API research only. The virtual
KWin output does not advertise `wl_shm`, so a Wayland screenshot client cannot
capture its pixels; KWin's screenshot D-Bus method also requires an authorised
caller. Therefore the product keeps KDE wallpaper unsupported until a nested
runtime can prove visible pixels, readback, unavailable-service handling, and
failure behavior. No KDE package was installed on the host.

See the concise [research result](benchmarks/kde-wallpaper-research-2026-10-29/results.json).
