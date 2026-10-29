import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from 'typescript';
const compile = source => 'data:text/javascript;base64,' + Buffer.from(ts.transpileModule(source, { compilerOptions: {
  module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX,
} }).outputText).toString('base64');
const jsx = compile('export const jsx=(type,props)=>({type,props}); export const jsxs=jsx;');
function* nodes(tree) {
  if (!tree || typeof tree !== 'object') return;
  yield tree;
  for (const child of [tree.props?.children].flat(Infinity)) yield* nodes(child);
}
test('accent keyboard form rejects invalid codes and follows picker/external config changes', async () => {
  const defaults = JSON.parse(fs.readFileSync(new URL('../src/config/defaults.json', import.meta.url)));
  const states = [], effects = [], pending = [], patches = [];
  let index = 0, effectIndex = 0, config = defaults;
  globalThis.__appearanceColor = {
    useState(initial) { const slot = index++; if (!(slot in states)) states[slot] = initial; return [states[slot], value => { states[slot] = typeof value === 'function' ? value(states[slot]) : value; }]; },
    useEffect(callback, deps) { const slot = effectIndex++; if (!effects[slot] || deps.some((value, i) => value !== effects[slot][i])) pending.push(() => { effects[slot] = deps; callback(); }); },
    useRemovalFocus: () => ({root:{current:null},fallback:{current:null},onFocusCapture(){}}),
    useConfig: () => ({config, updateConfig: async patch => { patches.push(patch); config = {...config,...patch}; return true; }}),
    useI18n: () => ({t: key => key}),
  };
  let source = fs.readFileSync(new URL('../src/components/studio/AppearanceSettings.tsx', import.meta.url), 'utf8')
    .replace(/import \{ useEffect, useState \} from .*;/, 'const {useEffect,useState}=globalThis.__appearanceColor;')
    .replace(/import \{ (useRemovalFocus|useConfig|useI18n) \} from .*;/g, 'const {$1}=globalThis.__appearanceColor;')
    .replace(/import \{ ErrorText \} from .*;/, 'const ErrorText="ErrorText";')
    .replace(/import \{ Card, Range, Toggle \} from .*;/, 'const Card="Card",Range="Range",Toggle="Toggle";')
    .replace('"../../dockAppearance"', JSON.stringify(compile(fs.readFileSync(new URL('../src/dockAppearance.ts', import.meta.url), 'utf8'))));
  const output = ts.transpileModule(source, { compilerOptions: {module: ts.ModuleKind.ESNext, jsx: ts.JsxEmit.ReactJSX} }).outputText.replaceAll('"react/jsx-runtime"', JSON.stringify(jsx));
  const {AppearanceSettings} = await import('data:text/javascript;base64,' + Buffer.from(output).toString('base64'));
  const render = () => { index = effectIndex = 0; const tree = AppearanceSettings(); for(const callback of pending.splice(0)) callback(); return tree; };
  const input = tree => [...nodes(tree)].find(n => n.type === 'input' && n.props['aria-label'] === 'accent');
  const form = tree => [...nodes(tree)].find(n => n.type === 'form' && [...nodes(n)].some(child => child === input(tree)));
  const save = tree => [...nodes(tree)].find(n => n.props?.['aria-label'] === 'save accent');
  try {
    let tree = render(); assert.equal(input(tree).props.value, defaults.accentColor); assert.equal(save(tree).props.disabled, true);
    input(tree).props.onChange({target:{value:'#xyz'}}); tree = render();
    assert.equal(save(tree).props.disabled, true); form(tree).props.onSubmit({preventDefault(){}}); assert.deepEqual(patches, []);
    input(tree).props.onChange({target:{value:'#336699'}}); tree = render();
    assert.equal(save(tree).props.disabled, false); form(tree).props.onSubmit({preventDefault(){}});
    assert.deepEqual(patches, [{accentColor:'#336699'}]); render(); tree = render(); assert.equal(save(tree).props.disabled, true);
    const picker = [...nodes(tree)].find(n => n.type === 'input' && n.props.type === 'color');
    assert.equal(picker.props.tabIndex, -1); assert.equal(picker.props['aria-hidden'], 'true');
    picker.props.onChange({target:{value:'#abcdef'}}); render(); tree = render(); assert.equal(input(tree).props.value, '#abcdef');
    config = {...config,accentColor:'#123456'}; render(); tree = render(); assert.equal(input(tree).props.value, '#123456');
  } finally { delete globalThis.__appearanceColor; }
});
