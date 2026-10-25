import React, { useEffect, useState } from "react";
import { invoke, convertFileSrc } from "@tauri-apps/api/core";
import { emit } from "@tauri-apps/api/event";
import { SystemStats, TaskbarConfig, WallpaperInfo, DEFAULT_PINNED_APPS } from "./types";
import {
  Image,
  Sliders,
  Store,
  Settings,
  Shuffle,
  Cpu,
  HardDrive,
  Check,
  Sparkles,
  Layers,
  Palette,
  Power,
  AppWindow,
  Monitor,
  ExternalLink,
  RefreshCw,
  Maximize2,
  EyeOff,
  Pin,
  Globe,
  Terminal,
  Folder,
  Code2,
} from "lucide-react";

export const Studio: React.FC = () => {
  const [activeTab, setActiveTab] = useState<"wallpaper" | "taskbar" | "market" | "settings">("wallpaper");
  const [stats, setStats] = useState<SystemStats | null>(null);
  const [wallpapers, setWallpapers] = useState<WallpaperInfo[]>([]);
  const [currentWallpaper, setCurrentWallpaper] = useState<string>("");
  const [customFolder, setCustomFolder] = useState<string>("");
  const [autostart, setAutostart] = useState<boolean>(false);
  const [isApplying, setIsApplying] = useState<boolean>(false);
  const [feedbackMsg, setFeedbackMsg] = useState<string | null>(null);

  // Taskbar config state
  const [config, setConfig] = useState<TaskbarConfig>({
    enabled: false,
    position: "bottom",
    height: 52,
    autoHide: false,
    opacity: 0.85,
    borderRadius: 16,
    showClock: true,
    showStats: true,
    showShuffle: true,
    showApps: true,
    accentColor: "#48b9c7",
    pinnedApps: DEFAULT_PINNED_APPS,
    bouncingLaunch: true,
    dynamicShadow: true,
    magnification: true,
    maxMagnificationScale: 1.35,
  });

  // Load initial settings
  useEffect(() => {
    const saved = localStorage.getItem("deskmorph_config");
    let activeConf = config;
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        activeConf = {
          ...config,
          ...parsed,
          autoHide: false,
          enabled: true,
          pinnedApps: parsed.pinnedApps || DEFAULT_PINNED_APPS,
          bouncingLaunch: parsed.bouncingLaunch !== undefined ? parsed.bouncingLaunch : true,
          dynamicShadow: parsed.dynamicShadow !== undefined ? parsed.dynamicShadow : true,
          magnification: parsed.magnification !== undefined ? parsed.magnification : true,
          maxMagnificationScale: parsed.maxMagnificationScale !== undefined ? parsed.maxMagnificationScale : 1.35,
        };
        setConfig(activeConf);
        localStorage.setItem("deskmorph_config", JSON.stringify(activeConf));
      } catch (e) {
        console.error(e);
      }
    }
    if (activeConf.enabled) {
      invoke("toggle_taskbar", { visible: true }).catch(console.error);
      invoke("reposition_taskbar", {
        position: activeConf.position,
        height: activeConf.height || 52,
      }).catch(console.error);
    }

    // Check autostart
    invoke<boolean>("is_autostart_enabled")
      .then((res) => setAutostart(res))
      .catch((e) => console.error(e));

    // Get current wallpaper
    invoke<string>("get_current_wallpaper")
      .then((res) => setCurrentWallpaper(res))
      .catch((e) => console.error(e));

    // Load wallpapers
    loadWallpapers();

    // Stats loop
    const fetchStats = async () => {
      try {
        const res = await invoke<SystemStats>("get_system_stats");
        setStats(res);
      } catch (e) {
        console.error(e);
      }
    };
    fetchStats();
    const interval = setInterval(fetchStats, 2000);
    return () => clearInterval(interval);
  }, []);

  const showNotification = (msg: string) => {
    setFeedbackMsg(msg);
    setTimeout(() => setFeedbackMsg(null), 3000);
  };

  const loadWallpapers = async (folder?: string) => {
    try {
      const list = await invoke<WallpaperInfo[]>("get_wallpapers", {
        folder: folder || null,
      });
      setWallpapers(list);
    } catch (err) {
      console.error("Error loading wallpapers", err);
    }
  };

  const handleApplyWallpaper = async (path: string) => {
    setIsApplying(true);
    try {
      await invoke("set_wallpaper", { path });
      setCurrentWallpaper(path);
      showNotification("Đã áp dụng ảnh nền mới thành công!");
    } catch (err) {
      showNotification(`Lỗi khi đổi ảnh nền: ${err}`);
    } finally {
      setIsApplying(false);
    }
  };

  const handleShuffleWallpaper = async () => {
    if (wallpapers.length === 0) return;
    const rand = wallpapers[Math.floor(Math.random() * wallpapers.length)];
    await handleApplyWallpaper(rand.path);
  };

  const updateConfig = (newConf: Partial<TaskbarConfig>) => {
    const updated = { ...config, ...newConf };
    setConfig(updated);
    localStorage.setItem("deskmorph_config", JSON.stringify(updated));

    // Emit event directly to taskbar window!
    emit("deskmorph:config-update", updated).catch(console.error);

    // Sync with backend if taskbar visibility or position/height changed
    if ("enabled" in newConf) {
      invoke("toggle_taskbar", { visible: newConf.enabled }).catch(console.error);
    }
    if ("position" in newConf || "height" in newConf || ("enabled" in newConf && newConf.enabled)) {
      invoke("reposition_taskbar", {
        position: newConf.position || config.position,
        height: newConf.height !== undefined ? newConf.height : config.height || 52,
      }).catch(console.error);
    }
  };

  const togglePinnedApp = (appId: string) => {
    const list = config.pinnedApps || DEFAULT_PINNED_APPS;
    const updatedList = list.map((app) =>
      app.id === appId ? { ...app, enabled: app.enabled === false ? true : false } : app
    );
    updateConfig({ pinnedApps: updatedList });
    showNotification("Đã cập nhật danh sách ứng dụng ghim trên Dock!");
  };

  const handleToggleAutostart = async () => {
    const next = !autostart;
    try {
      await invoke("set_autostart", { enabled: next });
      setAutostart(next);
      showNotification(next ? "Đã bật khởi động cùng máy!" : "Đã tắt khởi động cùng máy!");
    } catch (err) {
      showNotification(`Lỗi: ${err}`);
    }
  };

  const handleInstallAppIcon = async () => {
    try {
      await invoke("install_app_icon");
      showNotification("Đã đăng ký DeskMorph vào Menu Ứng Dụng Pop!_OS!");
    } catch (err) {
      showNotification(`Lỗi: ${err}`);
    }
  };

  const accentColors = [
    { name: "Pop Teal", hex: "#48b9c7" },
    { name: "Cyber Violet", hex: "#8b5cf6" },
    { name: "Electric Blue", hex: "#3b82f6" },
    { name: "Neon Emerald", hex: "#10b981" },
    { name: "Sunset Amber", hex: "#f59e0b" },
    { name: "Rose Ruby", hex: "#f43f5e" },
  ];

  const presets = [
    {
      name: "Nord Minimalist",
      desc: "Tông màu lạnh xám xanh, thanh dock nhỏ gọn, thanh lịch.",
      color: "#88c0d0",
      opacity: 0.75,
      radius: 12,
      pos: "bottom" as const,
    },
    {
      name: "Cyberpunk Glow",
      desc: "Màu neon tím violet, bo góc mạnh mẽ, hiển thị toàn bộ widget.",
      color: "#8b5cf6",
      opacity: 0.9,
      radius: 20,
      pos: "top" as const,
    },
    {
      name: "Pop!_OS Pure",
      desc: "Tông màu Teal đặc trưng của System76, hiện đại và chuẩn xác.",
      color: "#48b9c7",
      opacity: 0.85,
      radius: 16,
      pos: "bottom" as const,
    },
  ];

  return (
    <div className="studio-app">
      {/* Toast Feedback */}
      {feedbackMsg && (
        <div className="toast-feedback">
          <Sparkles size={16} color="#48b9c7" />
          <span>{feedbackMsg}</span>
        </div>
      )}

      {/* Top Header */}
      <header className="studio-header">
        <div className="header-brand">
          <div className="logo-box">
            <Sparkles size={20} color="#0c0f17" />
          </div>
          <div>
            <div className="brand-title-row">
              <h1 className="brand-title">DeskMorph Studio</h1>
              <span className="version-pill">v0.1.0 Commercial</span>
            </div>
            <p className="brand-subtitle">Linux Desktop Customization Suite • Pop!_OS Native</p>
          </div>
        </div>

        {/* Live system pills */}
        <div className="header-stats">
          <div className="sys-badge">
            <span className="sys-dot online" />
            <span>X11 Session</span>
          </div>

          {stats && (
            <>
              <div className="stat-chip">
                <Cpu size={14} color="#48b9c7" />
                <span>CPU: {stats.cpu_usage.toFixed(0)}%</span>
              </div>
              <div className="stat-chip">
                <HardDrive size={14} color="#8b5cf6" />
                <span>RAM: {stats.ram_percent.toFixed(0)}%</span>
              </div>
            </>
          )}
        </div>
      </header>

      {/* Main Body */}
      <div className="studio-body">
        {/* Sidebar Nav */}
        <nav className="studio-nav">
          <button
            className={`nav-btn ${activeTab === "wallpaper" ? "active" : ""}`}
            onClick={() => setActiveTab("wallpaper")}
          >
            <Image size={18} />
            <span>Wallpaper Engine</span>
          </button>

          <button
            className={`nav-btn ${activeTab === "taskbar" ? "active" : ""}`}
            onClick={() => setActiveTab("taskbar")}
          >
            <Sliders size={18} />
            <span>Taskbar Studio</span>
          </button>

          <button
            className={`nav-btn ${activeTab === "market" ? "active" : ""}`}
            onClick={() => setActiveTab("market")}
          >
            <Store size={18} />
            <span>Theme Store</span>
            <span className="nav-badge">Pro</span>
          </button>

          <button
            className={`nav-btn ${activeTab === "settings" ? "active" : ""}`}
            onClick={() => setActiveTab("settings")}
          >
            <Settings size={18} />
            <span>Cài đặt hệ thống</span>
          </button>
        </nav>

        {/* Content Area */}
        <main className="studio-main">
          {/* TAB 1: WALLPAPER ENGINE */}
          {activeTab === "wallpaper" && (
            <div className="tab-pane animate-fade">
              <div className="pane-header">
                <div>
                  <h2>Quản lý Hình Nền Tự Động</h2>
                  <p>Chọn ảnh nền hệ thống, tự động quét thư mục hoặc đổi hình ngẫu nhiên chỉ bằng 1 click.</p>
                </div>
                <div className="pane-actions">
                  <button className="btn-secondary" onClick={() => loadWallpapers(customFolder)}>
                    <RefreshCw size={15} />
                    <span>Làm mới</span>
                  </button>
                  <button className="btn-primary" onClick={handleShuffleWallpaper} disabled={isApplying}>
                    <Shuffle size={15} />
                    <span>Đổi ngẫu nhiên</span>
                  </button>
                </div>
              </div>

              {/* Active Hero Card */}
              {currentWallpaper && (
                <div className="hero-wallpaper-card">
                  <div className="hero-preview-thumb">
                    <img
                      src={convertFileSrc(currentWallpaper)}
                      alt="Active Wallpaper"
                      className="hero-thumb-img"
                    />
                  </div>
                  <div className="hero-info">
                    <span className="hero-tag">ĐANG ÁP DỤNG TRÊN POP!_OS</span>
                    <h3 className="hero-title">{currentWallpaper.split("/").pop()}</h3>
                    <p className="hero-path">{currentWallpaper}</p>
                  </div>
                </div>
              )}

              {/* Folder Selector */}
              <div className="custom-folder-row">
                <input
                  type="text"
                  placeholder="Nhập đường dẫn thư mục ảnh riêng (VD: /home/.../Pictures/Wallpapers)"
                  value={customFolder}
                  onChange={(e) => setCustomFolder(e.target.value)}
                  className="folder-input"
                />
                <button
                  className="btn-secondary"
                  onClick={() => loadWallpapers(customFolder)}
                >
                  Quét thư mục
                </button>
              </div>

              {/* Gallery Grid */}
              <div className="wallpaper-grid">
                {wallpapers.map((wp) => {
                  const isActive = currentWallpaper.includes(wp.filename);
                  return (
                    <div
                      key={wp.path}
                      className={`wallpaper-card ${isActive ? "active-card" : ""}`}
                      onClick={() => handleApplyWallpaper(wp.path)}
                    >
                      <div className="wallpaper-thumb-wrapper">
                        <img
                          src={convertFileSrc(wp.path)}
                          alt={wp.filename}
                          className="wallpaper-thumb-img"
                          loading="lazy"
                        />
                        {isActive && (
                          <div className="active-badge">
                            <Check size={14} />
                            <span>Đang dùng</span>
                          </div>
                        )}
                      </div>
                      <div className="wallpaper-info">
                        <span className="wallpaper-name" title={wp.filename}>
                          {wp.filename}
                        </span>
                        <button className="quick-apply-btn">
                          {isActive ? "Đang chạy" : "Áp dụng"}
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* TAB 2: TASKBAR STUDIO */}
          {activeTab === "taskbar" && (
            <div className="tab-pane animate-fade">
              <div className="pane-header">
                <div>
                  <h2>Taskbar Studio (Dock Tùy Biến)</h2>
                  <p>Thiết kế thanh taskbar độc lập, không viền, nổi trên màn hình với hiệu ứng kính mờ.</p>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                  <button
                    className={`toggle-switch-btn ${config.enabled ? "on" : "off"}`}
                    onClick={() => {
                      const next = !config.enabled;
                      updateConfig({ enabled: next });
                      showNotification(next ? "Đã BẬT Taskbar và hiển thị ở mép màn hình!" : "Đã TẮT Taskbar!");
                    }}
                  >
                    <Power size={16} />
                    <span>{config.enabled ? "BẬT (Nhấn để Tắt)" : "TẮT (Nhấn để Bật)"}</span>
                  </button>

                  <button
                    className="action-btn secondary"
                    onClick={() => {
                      updateConfig({ enabled: true, autoHide: false });
                      invoke("toggle_taskbar", { visible: true }).catch(console.error);
                      invoke("reposition_taskbar", {
                        position: config.position,
                        height: config.height || 52,
                      }).catch(console.error);
                      showNotification("Đã đưa Taskbar nổi lên trên màn hình!");
                    }}
                    title="Buộc hiển thị Taskbar và căn chỉnh vị trí"
                    style={{ padding: "8px 14px", fontSize: "12px", display: "flex", alignItems: "center", gap: "6px" }}
                  >
                    <RefreshCw size={14} />
                    <span>Hiện Taskbar ngay</span>
                  </button>
                </div>
              </div>

              {/* Live Preview Box */}
              <div className="preview-container">
                <span className="preview-label">Bản Xem Trước Trực Quan</span>
                <div className="preview-desktop-mock">
                  <div
                    className="preview-dock"
                    style={{
                      height: `${Math.round((config.height || 52) * 0.82)}px`,
                      background: `rgba(15, 20, 32, ${config.opacity})`,
                      borderRadius: `${config.borderRadius}px`,
                      borderColor: "rgba(255, 255, 255, 0.15)",
                      marginTop: config.position === "bottom" ? "115px" : "10px",
                    }}
                  >
                    <div className="mock-brand">
                      <div className="brand-dot" style={{ background: config.accentColor }} />
                      <span>DeskMorph</span>
                    </div>

                    {config.showApps && (
                      <div className="mock-group">
                        <div className="mock-icon" />
                        <div className="mock-icon" />
                        <div className="mock-icon" />
                      </div>
                    )}

                    {config.showStats && (
                      <div className="mock-stat-pill">
                        <Cpu size={12} color={config.accentColor} />
                        <span>24%</span>
                      </div>
                    )}

                    {config.showShuffle && (
                      <div className="mock-stat-pill">
                        <Shuffle size={12} color="#fff" />
                      </div>
                    )}

                    {config.showClock && (
                      <div className="mock-clock">
                        <span>20:45</span>
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Controls Grid */}
              <div className="settings-cards-grid">
                {/* Position & Geometry */}
                <div className="setting-card">
                  <h3>
                    <Monitor size={17} color="#48b9c7" />
                    <span>Vị trí hiển thị</span>
                  </h3>
                  <div className="choice-buttons">
                    <button
                      className={`choice-btn ${config.position === "bottom" ? "selected" : ""}`}
                      onClick={() => updateConfig({ position: "bottom" })}
                    >
                      Dưới đáy (Đề xuất)
                    </button>
                    <button
                      className={`choice-btn ${config.position === "top" ? "selected" : ""}`}
                      onClick={() => updateConfig({ position: "top" })}
                    >
                      Trên đỉnh màn hình
                    </button>
                  </div>
                </div>

                {/* Accent Color */}
                <div className="setting-card">
                  <h3>
                    <Palette size={17} color="#8b5cf6" />
                    <span>Màu chủ đạo (Accent Color)</span>
                  </h3>
                  <div className="color-palette-row">
                    {accentColors.map((c) => (
                      <button
                        key={c.hex}
                        className={`color-choice-btn ${config.accentColor === c.hex ? "active-color" : ""}`}
                        style={{ background: c.hex }}
                        onClick={() => updateConfig({ accentColor: c.hex })}
                        title={c.name}
                      >
                        {config.accentColor === c.hex && <Check size={14} color="#000" />}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Opacity Slider */}
                <div className="setting-card">
                  <div className="slider-header">
                    <h3>
                      <Layers size={17} color="#10b981" />
                      <span>Độ trong suốt (Kính mờ)</span>
                    </h3>
                    <span className="slider-value">{Math.round(config.opacity * 100)}%</span>
                  </div>
                  <input
                    type="range"
                    min="0.4"
                    max="1.0"
                    step="0.05"
                    value={config.opacity}
                    onChange={(e) => updateConfig({ opacity: parseFloat(e.target.value) })}
                    className="custom-slider"
                  />
                </div>

                {/* Border Radius */}
                <div className="setting-card">
                  <div className="slider-header">
                    <h3>
                      <AppWindow size={17} color="#f59e0b" />
                      <span>Bo tròn góc (Radius)</span>
                    </h3>
                    <span className="slider-value">{config.borderRadius}px</span>
                  </div>
                  <input
                    type="range"
                    min="4"
                    max="28"
                    step="2"
                    value={config.borderRadius}
                    onChange={(e) => updateConfig({ borderRadius: parseInt(e.target.value) })}
                    className="custom-slider"
                  />
                </div>

                {/* Taskbar Height Slider */}
                <div className="setting-card">
                  <div className="slider-header">
                    <h3>
                      <Maximize2 size={17} color="#38bdf8" />
                      <span>Chiều cao Taskbar (Height)</span>
                    </h3>
                    <span className="slider-value">{config.height || 52}px</span>
                  </div>
                  <input
                    type="range"
                    min="42"
                    max="74"
                    step="2"
                    value={config.height || 52}
                    onChange={(e) => updateConfig({ height: parseInt(e.target.value) })}
                    className="custom-slider"
                  />
                </div>

                {/* Auto-Hide Option */}
                <div className="setting-card">
                  <div className="slider-header">
                    <h3>
                      <EyeOff size={17} color="#ec4899" />
                      <span>Tự động ẩn Dock (Auto-Hide)</span>
                    </h3>
                    <button
                      className={`toggle-switch-btn ${config.autoHide ? "on" : "off"}`}
                      style={{ padding: "5px 12px", fontSize: "11px" }}
                      onClick={() => updateConfig({ autoHide: !config.autoHide })}
                    >
                      <Power size={13} />
                      <span>{config.autoHide ? "BẬT" : "TẮT"}</span>
                    </button>
                  </div>
                  <p style={{ fontSize: "12px", color: "var(--text-muted)", margin: "0" }}>
                    Tự giấu thanh Dock và trượt lên khi bạn rê chuột xuống mép màn hình.
                  </p>
                </div>
              </div>

              {/* Widget Toggles */}
              <div className="widget-toggle-card">
                <h3>Các Thành Phần Hiển Thị Trên Taskbar</h3>
                <div className="widget-toggle-list">
                  <label className="toggle-label">
                    <input
                      type="checkbox"
                      checked={config.showClock}
                      onChange={(e) => updateConfig({ showClock: e.target.checked })}
                    />
                    <span>Đồng hồ & Ngày giờ thực</span>
                  </label>

                  <label className="toggle-label">
                    <input
                      type="checkbox"
                      checked={config.showStats}
                      onChange={(e) => updateConfig({ showStats: e.target.checked })}
                    />
                    <span>Chỉ số % CPU và RAM trực tiếp</span>
                  </label>

                  <label className="toggle-label">
                    <input
                      type="checkbox"
                      checked={config.showShuffle}
                      onChange={(e) => updateConfig({ showShuffle: e.target.checked })}
                    />
                    <span>Nút Đổi Ảnh Nền ngẫu nhiên nhanh (Shuffle)</span>
                  </label>

                  <label className="toggle-label">
                    <input
                      type="checkbox"
                      checked={config.showApps}
                      onChange={(e) => updateConfig({ showApps: e.target.checked })}
                    />
                    <span>Thanh ứng dụng (Pinned Apps & Running Apps)</span>
                  </label>

                  <label className="toggle-label">
                    <input
                      type="checkbox"
                      checked={config.bouncingLaunch !== false}
                      onChange={(e) => updateConfig({ bouncingLaunch: e.target.checked })}
                    />
                    <span>Hiệu ứng nảy icon khi mở (Bouncing Launch Animation)</span>
                  </label>

                  <label className="toggle-label">
                    <input
                      type="checkbox"
                      checked={config.dynamicShadow !== false}
                      onChange={(e) => updateConfig({ dynamicShadow: e.target.checked })}
                    />
                    <span>Bóng đổ / Vệt sáng động dưới chân icon (Dynamic Shadow/Glow)</span>
                  </label>

                  <label className="toggle-label">
                    <input
                      type="checkbox"
                      checked={config.magnification !== false}
                      onChange={(e) => updateConfig({ magnification: e.target.checked })}
                    />
                    <span>Hiệu ứng phóng to dạng sóng macOS (Magnification Wave)</span>
                  </label>
                </div>
              </div>

              {/* Pinned Applications Section */}
              <div className="widget-toggle-card" style={{ marginTop: "16px" }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "14px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <Pin size={18} color="#38bdf8" />
                    <h3 style={{ margin: 0, fontSize: "15px", fontWeight: "700" }}>Ứng Dụng Được Ghim Trên Dock (Pinned Apps)</h3>
                  </div>
                  <span style={{ fontSize: "12px", color: "var(--text-dim)" }}>
                    Nhấn vào biểu tượng trên Dock để mở app khi chưa chạy
                  </span>
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: "10px" }}>
                  {(config.pinnedApps || DEFAULT_PINNED_APPS).map((app) => (
                    <div
                      key={app.id}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        padding: "10px 14px",
                        background: "rgba(255, 255, 255, 0.04)",
                        borderRadius: "10px",
                        border: "1px solid rgba(255, 255, 255, 0.07)",
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                        <div
                          style={{
                            width: "32px",
                            height: "32px",
                            borderRadius: "8px",
                            background: "rgba(255, 255, 255, 0.07)",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            color: app.color || "#38bdf8",
                          }}
                        >
                          {app.iconType === "chrome" && <Globe size={18} />}
                          {app.iconType === "code" && <Code2 size={18} />}
                          {app.iconType === "terminal" && <Terminal size={18} />}
                          {app.iconType === "files" && <Folder size={18} />}
                          {app.iconType === "settings" && <Settings size={18} />}
                        </div>
                        <div>
                          <div style={{ fontSize: "13px", fontWeight: "600", color: "#f1f5f9" }}>{app.name}</div>
                          <div style={{ fontSize: "11px", color: "var(--text-dim)", fontFamily: "monospace" }}>{app.command}</div>
                        </div>
                      </div>

                      <button
                        className={`toggle-switch-btn ${app.enabled !== false ? "on" : "off"}`}
                        style={{ padding: "4px 10px", fontSize: "11px" }}
                        onClick={() => togglePinnedApp(app.id)}
                      >
                        <span>{app.enabled !== false ? "Đã ghim" : "Bỏ ghim"}</span>
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* TAB 3: THEME STORE (COMMERCIAL PRO) */}
          {activeTab === "market" && (
            <div className="tab-pane animate-fade">
              <div className="pane-header">
                <div>
                  <h2>Marketplace & Mẫu Giao Diện Sẵn (Theme Presets)</h2>
                  <p>Mô hình thương mại hóa: Tải và áp dụng các theme đỉnh cao hoặc mua bán preset từ cộng đồng.</p>
                </div>
                <div className="pro-pill-badge">
                  <Sparkles size={14} />
                  <span>Pro Store Edition</span>
                </div>
              </div>

              <div className="presets-grid">
                {presets.map((p) => (
                  <div key={p.name} className="preset-card">
                    <div className="preset-color-bar" style={{ background: p.color }} />
                    <div className="preset-body">
                      <h3>{p.name}</h3>
                      <p>{p.desc}</p>
                      <div className="preset-meta">
                        <span>Vị trí: {p.pos}</span>
                        <span>Bo góc: {p.radius}px</span>
                      </div>
                      <button
                        className="btn-primary full-width"
                        onClick={() => {
                          updateConfig({
                            accentColor: p.color,
                            opacity: p.opacity,
                            borderRadius: p.radius,
                            position: p.pos,
                            enabled: true,
                          });
                          showNotification(`Đã áp dụng mẫu giao diện: ${p.name}!`);
                        }}
                      >
                        Áp Dụng Preset Này
                      </button>
                    </div>
                  </div>
                ))}
              </div>

              <div className="commercial-banner">
                <div className="banner-text">
                  <h3>🚀 Bạn Muốn Kiếm Tiền Từ Theme Của Mình?</h3>
                  <p>DeskMorph Creator Program cho phép bạn tải lên các bộ Custom Taskbar và Wallpaper Packs để bán trên chợ ứng dụng.</p>
                </div>
                <button className="btn-secondary" onClick={() => alert("Tính năng Creator Program sẽ mở ở bản v1.0!")}>
                  Tìm hiểu thêm
                </button>
              </div>
            </div>
          )}

          {/* TAB 4: SYSTEM SETTINGS */}
          {activeTab === "settings" && (
            <div className="tab-pane animate-fade">
              <div className="pane-header">
                <div>
                  <h2>Cài Đặt Hệ Thống & Tích Hợp</h2>
                  <p>Quản lý quyền tự khởi động cùng máy và tích hợp biểu tượng vào Pop!_OS.</p>
                </div>
              </div>

              <div className="settings-list">
                <div className="setting-row">
                  <div>
                    <h4>Khởi động cùng máy (Autostart on Boot)</h4>
                    <p>Tự động chạy ngầm DeskMorph khi bạn đăng nhập vào Pop!_OS.</p>
                  </div>
                  <button
                    className={`toggle-switch-btn ${autostart ? "on" : "off"}`}
                    onClick={handleToggleAutostart}
                  >
                    <Power size={16} />
                    <span>{autostart ? "ĐÃ BẬT" : "ĐÃ TẮT"}</span>
                  </button>
                </div>

                <div className="setting-row">
                  <div>
                    <h4>Đăng ký Icon vào Menu Ứng Dụng Pop!_OS</h4>
                    <p>Tạo file .desktop để bạn có thể tìm thấy và mở DeskMorph từ danh sách ứng dụng.</p>
                  </div>
                  <button className="btn-secondary" onClick={handleInstallAppIcon}>
                    <ExternalLink size={15} />
                    <span>Cài Đặt App Icon</span>
                  </button>
                </div>

                <div className="setting-row">
                  <div>
                    <h4>Thông Tin Môi Trường Thực Thi</h4>
                    <p>Hệ điều hành: Pop!_OS 24.04 (Noble) • Display Server: X11 • Engine: Tauri 2 + Rust Core</p>
                  </div>
                  <div className="badge-tag">Native Linux</div>
                </div>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
};
