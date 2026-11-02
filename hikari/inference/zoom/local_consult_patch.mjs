// Reversible local backport of openclaw/openclaw#142692 (unmerged at the recorded source revision).
// This changes core meeting lifecycle ownership, never plugin trust or tool policy.
import {readFile, writeFile, mkdir, rename} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {homedir} from 'node:os';
import path from 'node:path';
import {pathToFileURL} from 'node:url';

export const version = '2026.10.9';
export const originalHash = 'c2ea582da96418835cd5e624970df3c9ac1533c74d525dfbcdebabe6e7b55798';
export const runtimeRoot = path.join(homedir(), '.local/lib/node_modules/openclaw');
export const target = path.join(runtimeRoot, 'dist/plugin-sdk/meeting-runtime.js');
export const backupDir = path.join(homedir(), '.config/hikari/patches/142692');
export const backup = path.join(backupDir, 'meeting-runtime.js.original');
export const admissionModule = path.join(runtimeRoot, 'dist/gateway-work-admission-DAV5kkgV.mjs');
export const sha256 = value => createHash('sha256').update(value).digest('hex');

export function consultFunction(source) {
  const start = source.indexOf('async function consultMeetingAgent(params) {');
  const end = source.indexOf('\nasync function handleMeetingRealtimeConsultToolCall', start);
  if (start < 0 || end < 0) throw new Error('Unexpected meeting runtime layout.');
  return source.slice(start, end);
}

export function patchedSource(original) {
  if (sha256(original) !== originalHash) throw new Error('Unrecognized core artifact; refusing to patch.');
  const oldFunction = consultFunction(original);
  const newFunction = oldFunction.replace(
    '\treturn await consultRealtimeVoiceAgent({',
    '\t// Local backport: https://github.com/openclaw/openclaw/pull/142692\n' +
    '\tconst admission = runOutsideGatewayRootWorkAdmission(() =>\n' +
    '\t\ttryBeginGatewayRootWorkAdmission(`meeting:${params.surface.id}:consult`));\n' +
    '\tif (!admission) throw new GatewayDrainingError();\n' +
    '\treturn await admission.run(() => consultRealtimeVoiceAgent({'
  ).replace('\n\t});\n}', '\n\t})).finally(admission.release);\n}');
  if (newFunction === oldFunction || !newFunction.includes('.finally(admission.release)')) {
    throw new Error('Unexpected consult function; refusing to patch.');
  }
  return 'import { S as runOutsideGatewayRootWorkAdmission, M as tryBeginGatewayRootWorkAdmission, t as GatewayDrainingError } from "../gateway-work-admission-DAV5kkgV.mjs";\n' +
    original.replace(oldFunction, newFunction);
}

export async function baselineSource() {
  const current = await readFile(target, 'utf8');
  if (sha256(current) === originalHash) return current;
  const original = await readFile(backup, 'utf8');
  if (sha256(current) !== sha256(patchedSource(original))) {
    throw new Error('Installed core differs from both the original and this patch.');
  }
  return original;
}

async function main(action) {
  if (!['check', 'apply', 'restore'].includes(action)) throw new Error('Use check, apply, or restore.');
  const pkg = JSON.parse(await readFile(path.join(runtimeRoot, 'package.json'), 'utf8'));
  if (pkg.version !== version) throw new Error(`Expected OpenClaw ${version}; found ${pkg.version}. Recheck upstream before changing another version.`);
  const original = await baselineSource();
  const candidate = patchedSource(original);
  const before = await readFile(target, 'utf8');
  if (action !== 'check') {
    await mkdir(backupDir, {recursive: true, mode: 0o700});
    try { await writeFile(backup, original, {flag: 'wx', mode: 0o600}); }
    catch (error) {
      if (error.code !== 'EEXIST' || sha256(await readFile(backup)) !== originalHash) throw error;
    }
    const desired = action === 'apply' ? candidate : original;
    if (sha256(before) !== sha256(desired)) {
      const temporary = target + '.hikari.tmp';
      await writeFile(temporary, desired, {flag: 'wx', mode: 0o644});
      // Do not replace an artifact changed concurrently by an updater.
      if (sha256(await readFile(target)) !== sha256(before)) throw new Error('Core changed during patch preparation.');
      await rename(temporary, target);
    }
    await writeFile(path.join(backupDir, 'receipt.json'), JSON.stringify({
      upstream: 'https://github.com/openclaw/openclaw/pull/142692',
      upstreamHead: '6b739765df4e106f7a3dbc77a8912c205a64ba37',
      upstreamMerged: false, version, target, backup, action,
      originalHash, installedHash: sha256(await readFile(target)), at: new Date().toISOString(),
    }, null, 2) + '\n', {mode: 0o600});
  }
  console.log(JSON.stringify({version, patched: sha256(await readFile(target)) === sha256(candidate), target, backup}));
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  await main(process.argv[2] || 'check');
}
