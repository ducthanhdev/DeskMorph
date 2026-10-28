import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from 'typescript';

const source = ts.transpileModule(fs.readFileSync(new URL('../src/windowGroups.ts', import.meta.url), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.ESNext },
}).outputText;
const { groupWindows } = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
const window = (id, class_name, is_active = false) => ({ id, class_name, title: id, is_active });

test('all matching windows belong to one pinned app, including the active window', () => {
  const result = groupWindows([window('1', 'Google-Chrome'), window('2', 'google-chrome', true)], [
    { id: 'chrome', matchClasses: ['chrome'] },
    { id: 'overlapping-rule', matchClasses: ['google-chrome'] },
  ]);
  assert.deepEqual(result.pinnedItems.map(g => g.windows.map(w => w.id)), [['1', '2'], []]);
  assert.equal(result.pinnedItems[0].windows.some(w => w.is_active), true);
  assert.deepEqual(result.unpinnedGroups, []);
});

test('unpinned apps group by case-insensitive class and remain separate from pinned apps', () => {
  const result = groupWindows([
    window('1', 'chrome'), window('2', 'Terminal'), window('3', 'terminal'), window('4', 'Editor'),
  ], [{ id: 'chrome', matchClasses: ['chrome'] }]);
  assert.deepEqual(result.unpinnedGroups.map(g => g.map(w => w.id)), [['2', '3'], ['4']]);
});

test('empty lists and removing a pin preserve the remaining windows', () => {
  assert.deepEqual(groupWindows([], []).unpinnedGroups, []);
  assert.equal(groupWindows([], [{ id: 'idle', matchClasses: ['files'] }]).pinnedItems[0].windows.length, 0);
  assert.deepEqual(groupWindows([window('1', 'chrome'), window('2', 'chrome')], []).unpinnedGroups[0].map(w => w.id), ['1', '2']);
});
