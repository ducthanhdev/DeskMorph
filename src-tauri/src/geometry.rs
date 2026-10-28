#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Rect { pub x: i32, pub y: i32, pub width: u32, pub height: u32 }
impl Rect {
    pub fn contains(&self, x: i32, y: i32) -> bool {
        x >= self.x && y >= self.y && i64::from(x) < i64::from(self.x) + i64::from(self.width)
            && i64::from(y) < i64::from(self.y) + i64::from(self.height)
    }
}
pub fn dock_rect(area: Rect, scale: f64, top: bool, logical_height: u32, hidden: bool, logical_width: u32) -> Rect {
    let px = |n: f64| (n * scale).round() as u32;
    let margin = px(16.0).min(area.width / 4);
    let width = px(logical_width as f64).min(area.width.saturating_sub(margin * 2)).max(1);
    let height = if hidden { px(4.0) } else { px(logical_height.clamp(40, 90) as f64) }.max(1).min(area.height.max(1));
    let y = if top { area.y + if hidden { 0 } else { margin as i32 } }
        else { area.y + area.height as i32 - height as i32 - if hidden { 0 } else { margin as i32 } };
    Rect { x: area.x + (area.width - width) as i32 / 2, y, width, height }
}
pub fn popup_rect(area: Rect, dock: Rect, scale: f64, anchor: i32, width: u32, height: u32, top: bool) -> Rect {
    let margin = (10.0 * scale).round() as u32;
    let width = ((width as f64 * scale).round() as u32).min(area.width.saturating_sub(margin * 2)).max(1);
    let height = ((height as f64 * scale).round() as u32).min(area.height.saturating_sub(margin * 2)).max(1);
    let min_x = area.x + margin as i32;
    let max_x = (area.x + area.width as i32 - width as i32 - margin as i32).max(min_x);
    let min_y = area.y + margin as i32;
    let max_y = (area.y + area.height as i32 - height as i32 - margin as i32).max(min_y);
    let x = (dock.x + (anchor as f64 * scale).round() as i32 - width as i32 / 2).clamp(min_x, max_x);
    let gap = (14.0 * scale).round() as i32;
    let y = if top { dock.y + dock.height as i32 + gap } else { dock.y - height as i32 - gap };
    Rect { x, y: y.clamp(min_y, max_y), width, height }
}
#[cfg(test)]
mod tests {
    use super::*;
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
                        let popup = popup_rect(area, dock, scale, anchor, 340, 600, top);
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
