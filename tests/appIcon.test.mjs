import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from 'typescript';
const compile = source => ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, jsx: ts.JsxEmit.ReactJSX } }).outputText;
const url = source => 'data:text/javascript;base64,' + Buffer.from(source).toString('base64');
const jsx = url('export const jsx = (type, props) => ({ type, props });');
test('missing/broken app icons render a bounded fallback and a new cache path can recover', async () => {
  let failed = null;
  globalThis.__appIconTest = { useState: () => [failed, value => { failed = value; }], convertFileSrc: path => 'asset:' + path };
  const source = fs.readFileSync(new URL('../src/components/AppIcon.tsx', import.meta.url), 'utf8')
    .replace(/import \{ useState \} from .*;/, 'const { useState } = globalThis.__appIconTest;')
    .replace(/import \{ convertFileSrc \} from .*;/, 'const { convertFileSrc } = globalThis.__appIconTest;')
    .replace(/import \{ AppWindow \} from .*;/, 'const AppWindow="fallback";');
  const { AppIcon } = await import(url(compile(source).replaceAll('"react/jsx-runtime"', JSON.stringify(jsx))));
  assert.equal(AppIcon({ path: null, size: 18 }).type, 'fallback');
  const image = AppIcon({ path: '/cache/old.png', size: 32 });
  assert.equal(image.type, 'img'); assert.equal(image.props.width, 32); assert.equal(image.props.height, 32);
  assert.equal(image.props.alt, ''); assert.equal(image.props.draggable, false);
  image.props.onError(); assert.equal(AppIcon({ path: '/cache/old.png' }).type, 'fallback');
  assert.equal(AppIcon({ path: '/cache/new.png' }).type, 'img');
  delete globalThis.__appIconTest;
});
