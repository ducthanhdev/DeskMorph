import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
const css = fs.readFileSync(new URL('../src/App.css', import.meta.url), 'utf8');
const rule = selector => {
  const start = css.indexOf(selector + ' {');
  assert.ok(start >= 0, selector);
  return css.slice(start, css.indexOf('}', start));
};
const color = (selector, property) => {
  const match = rule(selector).match(new RegExp('(?:^|[;{])\\s*' + property + ':\\s*(#[a-f0-9]{6}|rgba\\([^)]+\\))'));
  assert.ok(match, selector + ' ' + property);
  if (match[1].startsWith('#')) return [1, 3, 5].map(index => parseInt(match[1].slice(index, index + 2), 16)).concat(1);
  return match[1].match(/[\d.]+/g).map(Number);
};
const blend = (front, back) => front.slice(0, 3).map((channel, i) => channel * front[3] + back[i] * (1 - front[3]));
const luminance = rgb => rgb.slice(0, 3).map(value => { const channel = value / 255; return channel <= .04045 ? channel / 12.92 : ((channel + .055) / 1.055) ** 2.4; }).reduce((sum, value, i) => sum + value * [.2126, .7152, .0722][i], 0);
const contrast = (a, b) => { const x = luminance(a), y = luminance(b); return (Math.max(x, y) + .05) / (Math.min(x, y) + .05); };
test('calendar small day/weekday/banner text passes 4.5:1 on worst-case white behind translucent card', () => {
  const background = blend(color('.calendar-flyout-card', 'background'), [255, 255, 255]);
  for (const selector of ['.calendar-weekday-cell', '.calendar-day-cell.is-outside-month', '.calendar-live-banner', '.calendar-day-cell']) {
    const ratio = contrast(color(selector, 'color'), background);
    assert.ok(ratio >= 4.5, selector + ': ' + ratio);
  }
  assert.match(rule('.calendar-day-cell.is-outside-month'), /opacity: 1;/);
  const today = contrast(color('.calendar-day-cell.is-today', 'color'), color('.calendar-day-cell.is-today', 'background'));
  assert.ok(today >= 4.5, 'today ' + today);
});
