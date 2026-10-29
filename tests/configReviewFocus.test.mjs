import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from 'typescript';
const compile = source => 'data:text/javascript;base64,' + Buffer.from(ts.transpileModule(source, {compilerOptions:{module:ts.ModuleKind.ESNext,jsx:ts.JsxEmit.ReactJSX}}).outputText).toString('base64');
const jsx = compile('export const jsx=(type,props)=>({type,props});export const jsxs=jsx;export const Fragment="Fragment";');
function* nodes(tree) { if(!tree || typeof tree!=='object') return; yield tree; for(const child of [tree.props?.children].flat(Infinity)) yield* nodes(child); }
const deferred = () => {let resolve; const promise=new Promise(yes=>{resolve=yes});return {promise,resolve};};
const flush = async () => {for(let i=0;i<12;i++)await Promise.resolve();};

test('review focuses region, cancels to trigger, serializes confirm/undo and respects focus moved elsewhere', async () => {
 const defaults = JSON.parse(fs.readFileSync(new URL('../src/config/defaults.json',import.meta.url)));
 const states=[],refs=[],effects=[],pending=[],layouts=[],calls=[],requests=[];
 let lastReviewRef;
 let si=0,ri=0,ei=0,li=0,config={...defaults,height:64},revision=7,hasFocus=true;
 const focusListeners=new Set();globalThis.window={addEventListener:(_name,handler)=>focusListeners.add(handler),removeEventListener:(_name,handler)=>focusListeners.delete(handler)};
 const body={}; globalThis.document={body,activeElement:body,hasFocus:()=>hasFocus};
 const element = name => ({name,contains(node){return this===node || this.children?.includes(node);},focus(){document.activeElement=this;}});
 const trigger=element('reset'),region=element('review'),confirm=element('confirm'),cancel=element('cancel'),undo=element('undo'),other=element('elsewhere');region.children=[confirm,cancel];
 globalThis.__reviewFocus={
  useState(initial){const i=si++;if(!(i in states))states[i]=initial;return[states[i],value=>{states[i]=typeof value==='function'?value(states[i]):value;}];},
  useRef(initial){return refs[ri++] ||= {current:initial};},
  useEffect(callback,deps){const i=ei++;if(!effects[i]||deps.some((d,j)=>d!==effects[i].deps[j]))pending.push(()=>{effects[i]?.cleanup?.();effects[i]={deps,cleanup:callback()};});},
  useLayoutEffect(callback,deps){const i=li++;if(!layouts[i]||deps.some((d,j)=>d!==layouts[i].deps[j]))pending.push(()=>{layouts[i]?.cleanup?.();layouts[i]={deps,cleanup:callback()};});},
  useConfig:()=>({config,revision,updateConfig:()=>Promise.resolve(true),replaceConfigDocument:(doc,rev)=>{calls.push({doc,rev});const request=deferred();requests.push(request);return request.promise;}}),
  usePlatform:()=>({platform:null}),useI18n:()=>({t:key=>key,language:'vi',text:value=>value}),
  invoke:command=>Promise.resolve(command==='is_autostart_enabled'?false:{config:defaults,changedFields:['height'],expectedRevision:revision}),
 };
 let source=fs.readFileSync(new URL('../src/components/studio/SystemSettings.tsx',import.meta.url),'utf8');
 source=source.replace(/import \{ Fragment, useEffect, useLayoutEffect, useRef, useState \} from .*;/,'const Fragment="Fragment";const {useEffect,useLayoutEffect,useRef,useState}=globalThis.__reviewFocus;')
 .replace(/import \{ (invoke|usePlatform|useI18n) \} from .*;/g,'const {$1}=globalThis.__reviewFocus;')
 .replace(/import \{ useConfig, errorMessage \} from .*;/,'const {useConfig}=globalThis.__reviewFocus;const errorMessage=String;')
 .replace(/import \{ DEFAULT_CONFIG, type TaskbarConfig \} from .*;/,'const DEFAULT_CONFIG='+JSON.stringify(defaults)+';')
 .replace(/import \{ configFieldLabel, configReviewValue \} from .*;/,'const configFieldLabel=(_l,f)=>f,configReviewValue=(_l,_f,v)=>String(v);')
 .replace(/import \{ ErrorText \} from .*;/,'const ErrorText="ErrorText";')
 .replace(/import \{ Card, Toggle \} from .*;/,'const Card="Card",Toggle="Toggle";')
 .replace(/import \{ ShortcutSettings \} from .*;/,'const ShortcutSettings="ShortcutSettings";')
 .replace(/import \{ capabilityReason \} from .*;/,'const capabilityReason=()=>"reason";');
 let output=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ESNext,jsx:ts.JsxEmit.ReactJSX}}).outputText.replaceAll('"react/jsx-runtime"',JSON.stringify(jsx));
 const {SystemSettings}=await import('data:text/javascript;base64,'+Buffer.from(output).toString('base64'));
 const button=(tree,key)=>[...nodes(tree)].find(n=>n.type==='button'&&n.props.children===key);
 const render=()=>{si=ri=ei=li=0;const tree=SystemSettings();const review=[...nodes(tree)].find(n=>n.props?.className==='config-review');
  if(review){lastReviewRef=review.props.ref;lastReviewRef.current=region;}else if(lastReviewRef)lastReviewRef.current=null;
  const undoNode=button(tree,'undo');if(undoNode)undoNode.props.ref.current=undo;
  if(!review&&region.contains(document.activeElement))document.activeElement=body;
  if(!undoNode&&document.activeElement===undo)document.activeElement=body;
  for(const callback of pending.splice(0))callback();return tree;};
 const open=async()=>{let tree=render();trigger.focus();button(tree,'reset').props.onClick({currentTarget:trigger});await flush();return render();};
 try{
  let tree=await open();assert.equal(document.activeElement,region);assert.equal([...nodes(tree)].find(n=>n.props?.className==='config-review').props.tabIndex,-1);
  cancel.focus();button(tree,'cancel').props.onClick();render();assert.equal(document.activeElement,trigger);
  tree=await open();confirm.focus();const save=button(tree,'resetConfirm').props.onClick;const task=save();await save();assert.equal(calls.length,1);
  tree=render();button(tree,'cancel').props.onClick();assert.equal(button(tree,'cancel').props.disabled,true);assert.equal(button(tree,'resetConfirm').props.disabled,true);
  config=defaults;revision=8;requests[0].resolve(true);await task;tree=render();assert.equal(document.activeElement,undo);
  const undoTask=button(tree,'undo').props.onClick();requests[1].resolve(true);await undoTask;render();assert.equal(document.activeElement,trigger);
  tree=await open();confirm.focus();const failed=button(tree,'resetConfirm').props.onClick();tree=render();document.activeElement=body;requests[2].resolve(false);await failed;tree=render();assert.equal(document.activeElement,region);assert.ok(button(tree,'resetConfirm'));assert.equal(button(tree,'resetConfirm').props.disabled,false);
  const moved=button(tree,'resetConfirm').props.onClick();other.focus();requests[3].resolve(true);await moved;render();assert.equal(document.activeElement,other);
  // A review result may arrive after focus has moved to another setting.
  tree=render();trigger.focus();button(tree,'reset').props.onClick({currentTarget:trigger});other.focus();await flush();render();assert.equal(document.activeElement,other);
  hasFocus=false;tree=render();button(tree,'cancel').props.onClick();render();assert.equal(document.activeElement,other);
  trigger.focus();button(render(),'reset').props.onClick({currentTarget:trigger});await flush();render();assert.equal(document.activeElement,trigger);
  hasFocus=true;for(const handler of focusListeners)handler();assert.equal(document.activeElement,region);
 }finally{for(const effect of effects)effect?.cleanup?.();for(const layout of layouts)layout?.cleanup?.();assert.equal(focusListeners.size,0);delete globalThis.window;delete globalThis.document;delete globalThis.__reviewFocus;}
});
