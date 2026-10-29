import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from 'typescript';

const source = ts.transpileModule(fs.readFileSync(new URL('../src/dateTime.ts', import.meta.url), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.ESNext },
}).outputText;
const { formatClock, formatClockDateTime } = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
const normalize = text => text.replace(/[\u00a0\u202f]/g, ' ');

test('clock preferences use 00 at midnight, 12 at noon, optional seconds and localized day periods', () => {
  for (const [locale, am, pm] of [['vi-VN', 'SA', 'CH'], ['en-US', 'AM', 'PM']]) {
    const midnight = new Date(2026, 9, 29, 0, 5, 9);
    const noon = new Date(2026, 9, 29, 12, 5, 9);
    const late = new Date(2026, 9, 29, 23, 59, 58);
    assert.equal(formatClock(midnight, locale, { clock24: true, clockSeconds: true }), '00:05:09');
    assert.equal(formatClock(noon, locale, { clock24: true, clockSeconds: false }), '12:05');
    assert.equal(formatClock(late, locale, { clock24: true, clockSeconds: true }), '23:59:58');
    assert.equal(normalize(formatClock(midnight, locale, { clock24: false, clockSeconds: true })), `12:05:09 ${am}`);
    assert.equal(normalize(formatClock(noon, locale, { clock24: false, clockSeconds: false })), `12:05 ${pm}`);
    assert.equal(normalize(formatClock(late, locale, { clock24: false, clockSeconds: true })), `11:59:58 ${pm}`);
  }
});

test('schedule timestamps keep locale date order and respect both clock preferences at day/year boundaries', () => {
  const before = new Date(2026, 11, 31, 23, 59, 58);
  const after = new Date(2027, 0, 1, 0, 0, 1);
  for (const [locale, datePattern] of [['vi-VN', /31\/12\/26/], ['en-US', /12\/31\/26/]]) {
    const full = normalize(formatClockDateTime(before.getTime(), locale, { clock24: true, clockSeconds: true }));
    assert.match(full, datePattern); assert.match(full, /23:59:58/); assert.doesNotMatch(full, /PM|CH/);
    const short = normalize(formatClockDateTime(before, locale, { clock24: false, clockSeconds: false }));
    assert.match(short, datePattern); assert.match(short, /11:59/); assert.doesNotMatch(short, /:58/);
    assert.match(short, locale === 'vi-VN' ? /CH/ : /PM/);
    const next = formatClockDateTime(after, locale, { clock24: true, clockSeconds: true });
    assert.match(next, /1\/1\/27|01\/01\/27/); assert.match(next, /0{1,2}:00:01/);
    assert.equal(formatClock(after, locale, { clock24: true, clockSeconds: true }), '00:00:01');
  }
});
