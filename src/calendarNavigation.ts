/** Local civil dates avoid DST and month-overflow surprises in calendar navigation. */
export function calendarDestination(date: Date, key: string, shift = false): Date | null {
  const next = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  const offsets: Record<string, number> = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7 };
  if (key in offsets) next.setDate(next.getDate() + offsets[key]);
  else if (key === "Home" || key === "End") {
    const weekday = (next.getDay() + 6) % 7;
    next.setDate(next.getDate() + (key === "Home" ? -weekday : 6 - weekday));
  } else if (key === "PageUp" || key === "PageDown") {
    const day = next.getDate();
    next.setDate(1);
    next.setMonth(next.getMonth() + (key === "PageUp" ? -1 : 1) * (shift ? 12 : 1));
    next.setDate(Math.min(day, new Date(next.getFullYear(), next.getMonth() + 1, 0).getDate()));
  } else return null;
  return next;
}
