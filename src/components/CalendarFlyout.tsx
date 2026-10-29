import { useConfig } from "../config/store";
import { useI18n } from "../i18n/useI18n";
import React, { useState, useEffect } from "react";
import { invoke } from "../ipc";
import { listen } from "@tauri-apps/api/event";
import { useClock } from "../hooks/useClock";
import { ChevronLeft, ChevronRight, Calendar as CalendarIcon, Clock } from "lucide-react";

export const CalendarFlyout: React.FC = () => {
  const { config } = useConfig();
  const { t, locale } = useI18n();
  const [visible, setVisible] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const today = useClock(visible);
  const [viewDate, setViewDate] = useState<Date>(new Date());
  const [selectedDate, setSelectedDate] = useState<Date>(new Date());
  const liveTime = today.toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit", second: config.clockSeconds ? "2-digit" : undefined, hour12: !config.clock24 });

  useEffect(() => {
    let disposed = false;
    let stop: (() => void) | undefined;
    let events = 0;
    const start = async () => {
      try {
        const unlisten = await listen<boolean>("deskmorph:calendar-visibility", ({ payload }) => {
          if (!disposed) { events++; setVisible(payload); }
        });
        if (disposed) { unlisten(); return; }
        stop = unlisten;
        const version = events;
        const active = await invoke<boolean>("get_calendar_visibility");
        if (!disposed && version === events) setVisible(active);
      } catch (e) { if (!disposed) setError(String(e)); }
    };
    void start();
    return () => { disposed = true; stop?.(); };
  }, []);

  // Escape is handled by the native coordinator, scoped to its active generation.

  const currentYear = viewDate.getFullYear();
  const currentMonth = viewDate.getMonth(); // 0 - 11

  const handlePrevMonth = () => {
    setViewDate(new Date(currentYear, currentMonth - 1, 1));
  };

  const handleNextMonth = () => {
    setViewDate(new Date(currentYear, currentMonth + 1, 1));
  };

  const handleTodayJump = () => {
    const now = new Date();
    setViewDate(new Date(now.getFullYear(), now.getMonth(), 1));
    setSelectedDate(now);
  };

  // Calendar calculations (Monday = 0 ... Sunday = 6)
  const firstDayOfWeek = (new Date(currentYear, currentMonth, 1).getDay() + 6) % 7;
  const daysInCurrentMonth = new Date(currentYear, currentMonth + 1, 0).getDate();
  const daysInPrevMonth = new Date(currentYear, currentMonth, 0).getDate();

  const days: { day: number; isCurrentMonth: boolean; date: Date }[] = [];

  // Previous month padding
  for (let i = firstDayOfWeek - 1; i >= 0; i--) {
    const d = daysInPrevMonth - i;
    days.push({
      day: d,
      isCurrentMonth: false,
      date: new Date(currentYear, currentMonth - 1, d),
    });
  }

  // Current month days
  for (let d = 1; d <= daysInCurrentMonth; d++) {
    days.push({
      day: d,
      isCurrentMonth: true,
      date: new Date(currentYear, currentMonth, d),
    });
  }

  // Next month padding to fill a complete 35 or 42 grid
  const remainingCells = (7 - (days.length % 7)) % 7;
  const totalTarget = days.length + remainingCells < 35 ? 35 : days.length + remainingCells;
  const nextMonthPadding = totalTarget - days.length;

  for (let d = 1; d <= nextMonthPadding; d++) {
    days.push({
      day: d,
      isCurrentMonth: false,
      date: new Date(currentYear, currentMonth + 1, d),
    });
  }

  const weekDayNames = Array.from({ length: 7 }, (_, i) => new Intl.DateTimeFormat(locale, { weekday: "short" }).format(new Date(2024, 0, 1 + i)));
  const formatMonthTitle = (date: Date) => new Intl.DateTimeFormat(locale, { month: "long", year: "numeric" }).format(date);
  const formatFullDate = (date: Date) => new Intl.DateTimeFormat(locale, { dateStyle: "full" }).format(date);

  const isSameDay = (d1: Date, d2: Date) => {
    return (
      d1.getDate() === d2.getDate() &&
      d1.getMonth() === d2.getMonth() &&
      d1.getFullYear() === d2.getFullYear()
    );
  };

  return (
    <div className="calendar-flyout-window" onContextMenu={(e) => e.preventDefault()}>
      <div className="calendar-flyout-card">
        {error && <p role="alert">{error}</p>}
        {/* Live Date & Time Banner */}
        <div className="calendar-live-banner">
          <div className="calendar-live-date">
            <CalendarIcon size={13} className="banner-icon" />
            <span>{formatFullDate(today)}</span>
          </div>
          <div className="calendar-live-clock">
            <Clock size={13} className="banner-icon" />
            <span className="live-clock-time">{liveTime}</span>
          </div>
        </div>

        {/* Header: Navigation & Month Title */}
        <div className="calendar-header">
          <h2 className="calendar-month-title">{formatMonthTitle(viewDate)}</h2>

          <div className="calendar-nav-actions">
            <button
              className="calendar-btn-nav"
              onClick={handlePrevMonth}
              title={t("previousMonth")} aria-label={t("previousMonth")}
            >
              <ChevronLeft size={16} />
            </button>
            <button
              className="calendar-btn-today"
              onClick={handleTodayJump}
              title={t("today")}
            >
              {t("today")}
            </button>
            <button
              className="calendar-btn-nav"
              onClick={handleNextMonth}
              title={t("nextMonth")} aria-label={t("nextMonth")}
            >
              <ChevronRight size={16} />
            </button>
          </div>
        </div>

        {/* 7-Day Header */}
        <div className="calendar-grid-weekdays">
          {weekDayNames.map((name, index) => (
            <div
              key={name}
              className={`calendar-weekday-cell ${index >= 5 ? "is-weekend" : ""}`}
            >
              {name}
            </div>
          ))}
        </div>

        {/* Days Grid */}
        <div className="calendar-grid-days">
          {days.map((item, idx) => {
            const isToday = isSameDay(item.date, today);
            const isSelected = isSameDay(item.date, selectedDate);
            const dayOfWeek = (item.date.getDay() + 6) % 7;
            const isWeekend = dayOfWeek >= 5;

            return (
              <button
                aria-label={formatFullDate(item.date)}
                aria-pressed={isSelected}
                key={idx}
                className={`calendar-day-cell ${
                  !item.isCurrentMonth ? "is-outside-month" : ""
                } ${isToday ? "is-today" : ""} ${
                  isSelected && !isToday ? "is-selected" : ""
                } ${isWeekend ? "is-weekend" : ""}`}
                onClick={() => {
                  setSelectedDate(item.date);
                  if (!item.isCurrentMonth) {
                    setViewDate(new Date(item.date.getFullYear(), item.date.getMonth(), 1));
                  }
                }}
              >
                <span className="day-number">{item.day}</span>
                {isToday && <span className="today-glow-dot" />}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
};
export default CalendarFlyout;
