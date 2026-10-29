//! Rectangles use physical screen pixels; content sizes and Dock offsets use
//! logical WebView pixels. Convert the source offset once before placement.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Rect { pub x: i32, pub y: i32, pub width: u32, pub height: u32 }
impl Rect {
    pub fn contains(&self, x: i32, y: i32) -> bool {
        x >= self.x && y >= self.y && i64::from(x) < i64::from(self.x) + i64::from(self.width)
            && i64::from(y) < i64::from(self.y) + i64::from(self.height)
    }
}
fn pixels(value: u32, scale: f64) -> u32 { (f64::from(value) * scale).round() as u32 }
fn coordinate(value: i64) -> i32 { value.clamp(i64::from(i32::MIN), i64::from(i32::MAX)) as i32 }
/// Physical screen X, using the source WebView's scale rather than a destination scale.
pub fn anchor_x(dock: Rect, logical_offset: i32, source_scale: f64) -> i64 {
    i64::from(dock.x) + (f64::from(logical_offset) * source_scale).round() as i64
}
pub fn dock_rect(area: Rect, scale: f64, top: bool, logical_height: u32, hidden: bool, logical_width: u32) -> Rect {
    let margin = pixels(16, scale).min(area.width / 4);
    let width = pixels(logical_width, scale).min(area.width.saturating_sub(margin * 2)).max(1);
    let height = pixels(if hidden { 4 } else { logical_height.clamp(40, 90) }, scale).max(1).min(area.height.max(1));
    let vertical_margin = if hidden { 0 } else { margin.min(area.height.saturating_sub(height)) };
    let y = if top { i64::from(area.y) + i64::from(vertical_margin) }
        else { i64::from(area.y) + i64::from(area.height) - i64::from(height) - i64::from(vertical_margin) };
    Rect { x: coordinate(i64::from(area.x) + i64::from(area.width.saturating_sub(width)) / 2), y: coordinate(y), width, height }
}
/// `anchor` is already an absolute physical screen X; scale only the popup's content size.
pub fn popup_rect(area: Rect, dock: Rect, scale: f64, anchor: i64, width: u32, height: u32, top: bool) -> Rect {
    // Insets must leave at least one physical pixel on very small work areas.
    let horizontal_margin = pixels(10, scale).min(area.width.saturating_sub(1) / 2);
    let vertical_margin = pixels(10, scale).min(area.height.saturating_sub(1) / 2);
    let width = pixels(width, scale).min(area.width.saturating_sub(horizontal_margin * 2)).max(1);
    let height = pixels(height, scale).min(area.height.saturating_sub(vertical_margin * 2)).max(1);
    let min_x = i64::from(area.x) + i64::from(horizontal_margin);
    let max_x = (i64::from(area.x) + i64::from(area.width) - i64::from(width) - i64::from(horizontal_margin)).max(min_x);
    let min_y = i64::from(area.y) + i64::from(vertical_margin);
    let max_y = (i64::from(area.y) + i64::from(area.height) - i64::from(height) - i64::from(vertical_margin)).max(min_y);
    let x = (anchor - i64::from(width) / 2).clamp(min_x, max_x);
    let gap = i64::from(pixels(14, scale));
    let y = if top { i64::from(dock.y) + i64::from(dock.height) + gap } else { i64::from(dock.y) - i64::from(height) - gap };
    Rect { x: coordinate(x), y: coordinate(y.clamp(min_y, max_y)), width, height }
}
#[cfg(test)]
mod tests {
    use super::*;
    fn inside(area: Rect, rect: Rect) {
        assert!(rect.width > 0 && rect.height > 0);
        assert!(area.contains(rect.x, rect.y), "origin outside {area:?}: {rect:?}");
        assert!(area.contains(rect.x + rect.width as i32 - 1, rect.y + rect.height as i32 - 1), "edge outside {area:?}: {rect:?}");
    }
    #[test]
    fn very_small_work_areas_bound_insets_and_oversized_surfaces() {
        for width in [1, 2, 9, 20, 1919] {
            for height in [1, 2, 9, 20, 79] {
                let area = Rect { x: -1920, y: -1080, width, height };
                for scale in [1., 1.25, 1.5, 2.] {
                    for top in [true, false] {
                        for hidden in [true, false] {
                            let dock = dock_rect(area, scale, top, 90, hidden, 6000);
                            inside(area, dock);
                            for offset in [i32::MIN, 0, i32::MAX] {
                                inside(area, popup_rect(area, dock, scale, anchor_x(dock, offset, scale), 380, 620, top));
                            }
                        }
                    }
                }
            }
        }
    }
    #[test]
    fn source_scale_converts_anchor_once_and_destination_scale_sizes_content() {
        let area = Rect { x: -1920, y: -1080, width: 1920, height: 1080 };
        let dock = Rect { x: -1600, y: -110, width: 1100, height: 65 };
        let anchor = anchor_x(dock, 300, 1.25);
        assert_eq!(anchor, -1225);
        let popup = popup_rect(area, dock, 2., anchor, 340, 200, false);
        assert_eq!(popup, Rect { x: -1565, y: -538, width: 680, height: 400 });
        inside(area, popup);
        let top = popup_rect(area, dock, 1.5, anchor, 340, 200, true);
        assert_eq!(top.width, 510);
        assert_eq!(i64::from(top.x) + i64::from(top.width) / 2, anchor);
        inside(area, top);
    }
    #[test]
    fn monitor_origins_and_scales_keep_windows_inside_area() {
        for scale in [1., 1.25, 1.5, 2.] {
            for origin in [-2560, 0, 1920] {
                let area = Rect { x: origin, y: -200, width: 1920, height: 1080 };
                for top in [true, false] {
                    let dock = dock_rect(area, scale, top, 74, false, 1100);
                    assert!(area.contains(dock.x, dock.y));
                    assert!(area.contains(dock.x + dock.width as i32 - 1, dock.y + dock.height as i32 - 1));
                    for anchor in [-100, 0, 550, 5000] {
                        let popup = popup_rect(area, dock, scale, anchor_x(dock, anchor, scale), 340, 600, top);
                        assert!(area.contains(popup.x, popup.y));
                        assert!(area.contains(popup.x + popup.width as i32 - 1, popup.y + popup.height as i32 - 1));
                    }
                    let hidden = dock_rect(area, scale, top, 74, true, 1100);
                    assert!(hidden.height <= 8);
                    assert_eq!(hidden.y, if top { area.y } else { area.y + area.height as i32 - hidden.height as i32 });
                }
            }
        }
    }
}
