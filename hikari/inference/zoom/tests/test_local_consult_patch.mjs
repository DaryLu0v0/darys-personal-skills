// Run inside the provisioned Hikari WSL installation. Exercises the actual
// installed lifecycle helpers, with only the expensive agent turn replaced.
import test from 'node:test';
import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
import {baselineSource, patchedSource, consultFunction, admissionModule} from '../local_consult_patch.mjs';

const admission = await import(pathToFileURL(admissionModule));
const original = await baselineSource();
function loadConsult(source, run) {
  return new Function('normalizeAgentId', 'resolveDefaultAgentId', 'normalizeOptionalString',
    'resolveRealtimeVoiceAgentConsultToolsAllow', 'consultRealtimeVoiceAgent',
    'runOutsideGatewayRootWorkAdmission', 'tryBeginGatewayRootWorkAdmission', 'GatewayDrainingError',
    consultFunction(source) + '\nreturn consultMeetingAgent;')(
      id => id, () => 'main', value => value?.trim(), () => ['read', 'web_fetch'], run,
      admission.S, admission.M, admission.t);
}
const params = {
  agentId: 'main', surface: {id: 'zoom-meetings', provider: 'zoom'},
  runtime: {agent: {}}, config: {}, meetingSessionId: 'regression',
  toolPolicy: 'safe-read-only', args: {question: 'Read the local test file'}, transcript: [],
  abortSignal: new AbortController().signal,
};
async function afterCreationReturns(consult) {
  const root = admission.M('ws:zoommeetings.join');
  assert.ok(root);
  let proceed;
  const gate = new Promise(resolve => { proceed = resolve; });
  let result;
  await root.run(async () => { result = (async () => { await gate; return consult(params); })(); });
  root.release();
  proceed();
  return result;
}

test('released meeting request reproduces the installed failure; backport admits the later turn', async () => {
  const run = async received => {
    if (admission.m()) throw new admission.t();
    assert.deepEqual(received.toolsAllow, ['read', 'web_fetch']);
    assert.equal(received.abortSignal, params.abortSignal);
    return {text: 'read verified'};
  };
  await assert.rejects(afterCreationReturns(loadConsult(original, run)), /temporarily unavailable/);
  assert.deepEqual(await afterCreationReturns(loadConsult(patchedSource(original), run)), {text: 'read verified'});
  assert.equal(admission.s(), 0);
});

test('failed agent turns release their admission', async () => {
  const consult = loadConsult(patchedSource(original), async () => { throw new Error('provider failed'); });
  await assert.rejects(afterCreationReturns(consult), /provider failed/);
  assert.equal(admission.s(), 0);
});

test('a real gateway restart still refuses new meeting work', async () => {
  const fence = admission.n();
  assert.ok(fence);
  let ran = false;
  try {
    await assert.rejects(loadConsult(patchedSource(original), async () => { ran = true; })(params), /restarting/);
    assert.equal(ran, false);
    assert.equal(admission.s(), 0);
  } finally { fence.rollback(); }
});
