import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from 'typescript';
const url = source => 'data:text/javascript;base64,' + Buffer.from(source).toString('base64');
const jsx = url('export const jsx=(type,props)=>({type,props});export const jsxs=jsx;export const Fragment="Fragment";');
const flush = async () => { for (let i = 0; i < 20; i++) await Promise.resolve(); };
function* nodes(tree) {
  if (!tree || typeof tree !== 'object') return;
  yield tree;
  for (const child of [tree.props?.children].flat(Infinity)) yield* nodes(child);
}

test('media clears disconnected players and binds replacement actions/artwork to the new bus identity', async () => {
  const states = [], refs = [], effects = [], pending = [], calls = [];
  let si = 0, ri = 0, ei = 0, listener, active = true, stopCount = 0;
  const player = busId => ({ busId, name: 'org.mpris.MediaPlayer2.fixture', owner: ':1.5', identity: 'Fixture', title: busId, artists: [], artUrl: 'file:///cover.png', status: 'Playing', canPlay: true, canPause: true });
  let current = [player('old-bus')];
  globalThis.__mediaControlsTest = {
    useState(initial) { const i = si++; if (!(i in states)) states[i] = initial; return [states[i], v => { states[i] = typeof v === 'function' ? v(states[i]) : v; }]; },
    useRef(initial) { return refs[ri++] ||= { current: initial }; },
    useEffect(callback, deps) {
      const i = ei++, old = effects[i];
      if (!old || deps.some((d, j) => !Object.is(d, old.deps[j]))) pending.push(() => { old?.cleanup?.(); effects[i] = { deps, cleanup: callback() }; });
    },
    usePopupActive: () => active, usePopupFocus: () => ({}), useI18n: () => ({ t: key => key }),
    listen: async (name, callback) => { listener = callback; return () => { stopCount++; }; },
    invoke: async (command, args) => { calls.push({ command, args }); return command === 'get_media_players' ? current : command === 'get_media_artwork' ? 'data:image/png;base64,fixture' : undefined; },
  };
  let source = fs.readFileSync(new URL('../src/components/MediaControls.tsx', import.meta.url), 'utf8').replace(/^import .*;\n/gm, '');
  source = 'const {useEffect,useRef,useState,invoke,listen,usePopupActive,usePopupFocus,useI18n}=globalThis.__mediaControlsTest;const ErrorText="ErrorText";\n' + source;
  const output = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, jsx: ts.JsxEmit.ReactJSX } }).outputText.replaceAll('"react/jsx-runtime"', JSON.stringify(jsx));
  const { MediaControls } = await import(url(output));
  const render = () => { si = ri = ei = 0; const tree = MediaControls({ generation: 10 }); pending.splice(0).forEach(f => f()); return tree; };
  const settle = async () => { for (let i = 0; i < 5; i++) { render(); await flush(); } return render(); };
  const button = (tree, label) => [...nodes(tree)].find(n => n.type === 'button' && n.props.children === label);
  try {
    let tree = await settle();
    assert.ok(button(tree, 'mediaPause'));
    assert.equal(calls.find(c => c.command === 'get_media_artwork').args.expectedBusId, 'old-bus');
    listener({ payload: { Err: 'media_bus_unavailable' } }); tree = render();
    assert.equal(button(tree, 'mediaPause'), undefined, 'Disconnected player controls must be removed');
    assert.ok([...nodes(tree)].some(n => n.props?.role === 'alert'));
    current = [player('new-bus')]; listener({ payload: { Ok: current } }); tree = await settle();
    assert.equal(calls.filter(c => c.command === 'get_media_artwork').at(-1).args.expectedBusId, 'new-bus', 'Same unique owner on a new bus must reload artwork');
    button(tree, 'mediaPause').props.onClick(); await settle();
    assert.deepEqual(calls.find(c => c.command === 'control_media').args, { name: current[0].name, expectedOwner: ':1.5', expectedBusId: 'new-bus', action: 'Pause' });
    active = false; render(); listener({ payload: { Err: 'late error' } });
    assert.equal(button(render(), 'retry'), undefined, 'Hidden popup ignores late bus events');
    effects.forEach(e => e.cleanup?.()); assert.equal(stopCount, 1);
  } finally { delete globalThis.__mediaControlsTest; }
});
