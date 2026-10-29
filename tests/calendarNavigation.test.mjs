import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from 'typescript';
const source = ts.transpileModule(fs.readFileSync(new URL('../src/calendarNavigation.ts', import.meta.url), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.ESNext },
}).outputText;
const { calendarDestination: move } = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
const parts = date => [date.getFullYear(), date.getMonth() + 1, date.getDate()];
test('calendar keyboard crosses months/years, clamps month/year jumps and uses Monday weeks', () => {
  assert.deepEqual(parts(move(new Date(2026, 11, 31), 'ArrowRight')), [2027, 1, 1]);
  assert.deepEqual(parts(move(new Date(2026, 0, 1), 'ArrowLeft')), [2025, 12, 31]);
  assert.deepEqual(parts(move(new Date(2026, 9, 29), 'ArrowUp')), [2026, 10, 22]);
  assert.deepEqual(parts(move(new Date(2026, 9, 29), 'ArrowDown')), [2026, 11, 5]);
  assert.deepEqual(parts(move(new Date(2026, 9, 29), 'Home')), [2026, 10, 26]);
  assert.deepEqual(parts(move(new Date(2026, 9, 29), 'End')), [2026, 11, 1]);
  assert.deepEqual(parts(move(new Date(2024, 0, 31), 'PageDown')), [2024, 2, 29]);
  assert.deepEqual(parts(move(new Date(2024, 1, 29), 'PageDown', true)), [2025, 2, 28]);
  assert.deepEqual(parts(move(new Date(2026, 2, 31), 'PageUp')), [2026, 2, 28]);
  assert.equal(move(new Date(), 'Tab'), null);
  assert.equal(move(new Date(), 'Enter'), null);
});
