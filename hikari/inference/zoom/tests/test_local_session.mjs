import test from 'node:test';
import assert from 'node:assert/strict';
import {directMeetingUrl,prepareVoicePage,runMeetingAction} from '../local_session_actions.mjs';

const invite='https://example.zoom.us/j/12345678901?pwd=example';
const state={url:'https://app.zoom.us/wc/12345678901/join?fromPWA=1',
  frameUrl:'https://app.zoom.us/wc/12345678901/join?from=pwa&pwd=example',guest:true,host:false};
test('only the observed same-origin page for the same meeting can replace the wrapper',()=>{
  assert.equal(directMeetingUrl(state,invite),state.frameUrl);
  for (const frameUrl of ['https://example.org/wc/12345678901/join',
    'https://app.zoom.us/wc/99999999999/join','http://app.zoom.us/wc/12345678901/join']) {
    assert.throws(()=>directMeetingUrl({...state,frameUrl},invite));
  }
  assert.equal(directMeetingUrl({...state,guest:false},invite),null);
  assert.equal(directMeetingUrl({...state,frameUrl:null},invite),null);
});
test('host and admission states never trigger a fabricated readiness result',async()=>{
  const session={url:invite,chrome:{browserTab:{targetId:'test-tab'}}};
  await assert.rejects(()=>prepareVoicePage({request:async()=>({result:{host:true}})},session),/Reclaim host/);
  assert.equal(await prepareVoicePage({request:async()=>({result:{guest:false,host:false}})},session),false);
});
test('voice recovery refreshes state before speaking and preserves the actual result',async()=>{
  const calls=[];
  const session={id:'test-session',url:invite,chrome:{browserTab:{targetId:'test-tab'}}};
  const client={request:async(method,params)=>{
    calls.push({method,params});
    if(method==='zoommeetings.status')return {session};
    if(method==='browser.request')return {result:{...state,frameUrl:null}};
    return {spoken:false,session};
  }};
  const result=await runMeetingAction(client,'zoommeetings.speak',{sessionId:'test-session',message:'Hello'});
  assert.equal(result.spoken,false);
  assert.deepEqual(calls.map(c=>c.method),['zoommeetings.status','browser.request','zoommeetings.status','zoommeetings.speak']);
});
test('join reuses an active meeting and refuses a second meeting',async()=>{
  const session={id:'existing',state:'active',url:invite};
  const calls=[];
  const client={request:async(method)=>{calls.push(method);return {sessions:[session]};}};
  const result=await runMeetingAction(client,'zoommeetings.join',{url:invite});
  assert.equal(result.session.id,'existing');
  assert.equal(result.reused,true);
  assert.deepEqual(calls,['zoommeetings.status']);
  await assert.rejects(()=>runMeetingAction(client,'zoommeetings.join',{url:'https://zoom.us/j/99999999999'}),/another meeting/);
  assert.ok(!calls.includes('zoommeetings.join'));
});
