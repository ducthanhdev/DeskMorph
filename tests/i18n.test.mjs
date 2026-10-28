import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from 'typescript';
const source = ts.transpileModule(fs.readFileSync(new URL('../src/i18n/messages.ts', import.meta.url), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.ESNext },
}).outputText;
const { messages, formatCount } = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
test('Vietnamese and English cover the same UI messages', () => {
  assert.deepEqual(Object.keys(messages.vi).sort(), Object.keys(messages.en).sort());
  for (const language of Object.values(messages)) assert.ok(Object.values(language).every(value => value.trim().length));
});
test('window and application counts use locale and plural forms', () => {
  assert.equal(formatCount('en', 'window', 1), '1 window');
  assert.equal(formatCount('en', 'window', 2), '2 windows');
  assert.equal(formatCount('en', 'app', 0), '0 applications');
  assert.equal(formatCount('vi', 'window', 1), '1 cửa sổ');
  assert.equal(formatCount('vi', 'app', 2), '2 ứng dụng');
});
