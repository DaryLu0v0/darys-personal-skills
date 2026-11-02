// Keep the authenticated Gateway caller alive for the lifetime of Zoom audio.
// Only the current Linux user can access the control socket.
import net from 'node:net';
import {readFile, mkdir, chmod, lstat, unlink} from 'node:fs/promises';
import {homedir} from 'node:os';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {runMeetingAction} from './local_session_actions.mjs';

const privateDir = path.join(process.env.XDG_RUNTIME_DIR || `/run/user/${process.getuid()}`, 'hikari');
const socketPath = path.join(privateDir, 'meeting.sock');
const [action = 'status', ...args] = process.argv.slice(2);

function payloadFor(action, args) {
  if (action === 'status') return ['zoommeetings.status', args[0] ? {sessionId: validId(args[0])} : {}];
  if (action === 'join') {
    const url = new URL(args[0]);
    if (url.protocol !== 'https:' || url.username || url.password ||
        !/(^|\.)zoom\.us$/i.test(url.hostname) || !/^\/j\/\d+\/?$/.test(url.pathname)) {
      throw new Error('Enter a Zoom HTTPS meeting invitation.');
    }
    return ['zoommeetings.join', {url:args[0], mode:'bidi', transport:'chrome'}];
  }
  if (action === 'speak') {
    if (!args[1]?.trim() || args[1].length > 8000) throw new Error('A short speech request is required.');
    return ['zoommeetings.speak', {sessionId:validId(args[0]), message:args[1]}];
  }
  if (action === 'leave') return ['zoommeetings.leave', {sessionId:validId(args[0])}];
  throw new Error('Unsupported meeting action.');
}
function validId(value) {
  if (typeof value !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}$/.test(value)) {
    throw new Error('A valid meeting session is required.');
  }
  return value;
}

if (action !== 'serve') {
  payloadFor(action, args);
  const result = await new Promise((resolve, reject) => {
    const connection = net.createConnection(socketPath);
    let received = '';
    connection.setTimeout(240000, () => connection.destroy(new Error('The meeting request timed out. Check status before retrying.')));
    connection.on('connect', () => connection.write(JSON.stringify({action,args})+'\n'));
    connection.on('data', data => {
      received += data.toString();
      if (received.length > 2 * 1024 * 1024) connection.destroy(new Error('Unexpectedly large meeting response.'));
    });
    connection.on('error', reject);
    connection.on('end', () => {
      try { resolve(JSON.parse(received)); } catch { reject(new Error('The local meeting controller returned an invalid response.')); }
    });
  });
  console.log(JSON.stringify(result, null, 2));
  if (result.ok === false || result.found === false) process.exitCode = 1;
} else {
  process.umask(0o077);
  await mkdir(privateDir, {recursive:true,mode:0o700});
  await chmod(privateDir,0o700);
  try {
    const stat = await lstat(socketPath);
    if (!stat.isSocket()) throw new Error('The controller socket path is occupied by a non-socket file.');
    // systemd starts a single service instance; its prior socket can survive a crash.
    await unlink(socketPath);
  } catch (error) { if (error.code !== 'ENOENT') throw error; }
  const runtimeRoot = process.env.HIKARI_OPENCLAW_ROOT || path.join(homedir(), '.local/lib/node_modules/openclaw');
  const {GatewayClient} = await import(pathToFileURL(path.join(runtimeRoot, 'dist/plugin-sdk/gateway-runtime.js')));
  const config = JSON.parse(await readFile(path.join(homedir(), '.openclaw/openclaw.json'), 'utf8'));
  const token = config.gateway?.auth?.token;
  if (typeof token !== 'string' || !token) throw new Error('The local gateway token is not configured.');
  const safeError = error => String(error?.message || error).replaceAll(token,'[redacted]').replace(/sk-[A-Za-z0-9_-]+/g,'[redacted]');
  let connected = false;
  const client = new GatewayClient({
    url:`ws://127.0.0.1:${config.gateway.port || 18989}`, token,
    clientName:'cli', clientDisplayName:'Hikari local meeting controller',
    clientVersion:'hikari-local-1', mode:'cli', role:'operator',
    scopes:['operator.admin'], requestTimeoutMs:210000,
    onHelloOk:() => { connected=true; console.log('Hikari meeting controller connected.'); },
    onClose:() => { connected=false; console.log('Gateway connection closed; meeting voice needs reconnecting.'); },
    onConnectError:error => console.error(safeError(error)),
  });
  client.start();
  let pending = Promise.resolve();
  const server = net.createServer(connection => {
    let input = '';
    let submitted = false;
    connection.setTimeout(240000, () => connection.destroy());
    connection.on('error', () => {});
    connection.on('data', data => {
      if (submitted) return;
      input += data.toString();
      if (input.length > 16384) { connection.destroy(); return; }
      if (!input.includes('\n')) return;
      submitted = true;
      pending = pending.then(async () => {
        try {
          const request = JSON.parse(input.split('\n')[0]);
          if (!Array.isArray(request.args) || !request.args.every(x=>typeof x==='string')) throw new Error('Invalid meeting request.');
          const [method, params] = payloadFor(request.action, request.args);
          if (!connected) throw new Error('The local gateway is still connecting. Try again in a moment.');
          const result = await runMeetingAction(client, method, params);
          connection.end(JSON.stringify(result)+'\n');
        } catch (error) {
          connection.end(JSON.stringify({ok:false,error:{message:safeError(error)}})+'\n');
        }
      });
    });
  });
  server.listen(socketPath, async () => { await chmod(socketPath,0o600); });
  for (const signal of ['SIGTERM','SIGINT']) process.once(signal, () => {
    client.stop();
    server.close();
    setTimeout(()=>process.exit(),1000).unref();
  });
}
