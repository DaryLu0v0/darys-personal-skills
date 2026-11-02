// Compatibility handling uses normal browser navigation and public Gateway RPCs.
export const GREETING = "Say briefly: Hikari's voice is connected. I am ready to listen.";
const pageState = `() => {
  const frame = document.getElementById('webclient');
  const d = frame?.contentDocument || document;
  const visible = element => !!element?.getBoundingClientRect().width;
  const leave = d.querySelector('button[aria-label="Leave" i]');
  const end = d.querySelector('button[aria-label="End" i],button[aria-label="End meeting" i]');
  const mic = d.querySelector('button[aria-label="mute my microphone" i],button[aria-label="unmute my microphone" i]');
  const guest = visible(leave);
  const host = visible(end) && visible(mic);
  if (guest) {
    const closePanel = d.querySelector('button[aria-label="close the participants list pane"]');
    if (visible(closePanel)) closePanel.click();
  }
  return {url:location.href, frameUrl:frame?.src || null, guest, host};
}`;

export function directMeetingUrl(state, invitation) {
  if (!state.frameUrl || !state.guest) return null;
  const top = new URL(state.url);
  const inner = new URL(state.frameUrl);
  const meetingId = new URL(invitation).pathname.match(/^\/j\/(\d+)\/?$/)?.[1];
  if (!meetingId || top.protocol !== 'https:' || inner.origin !== top.origin ||
      !/(^|\.)zoom\.us$/i.test(inner.hostname) || inner.username || inner.password ||
      inner.pathname !== `/wc/${meetingId}/join`) {
    throw new Error('The embedded Zoom page does not match this meeting.');
  }
  return inner.href;
}

export async function prepareVoicePage(client, session) {
  const targetId = session?.chrome?.browserTab?.targetId;
  if (!targetId) return false;
  const inspect = () => client.request('browser.request', {
    method:'POST', path:'/act', body:{kind:'evaluate',targetId,fn:pageState}, timeoutMs:15000,
  });
  let state = (await inspect()).result;
  if (state.host) throw new Error('Hikari is the Zoom host. Reclaim host from your own Zoom participant, then choose Connect voice.');
  const direct = directMeetingUrl(state, session.url);
  if (direct) {
    await client.request('browser.request', {
      method:'POST',path:'/navigate',body:{url:direct,targetId},timeoutMs:20000,
    });
    for (let attempt=0; attempt<15; attempt++) {
      await new Promise(resolve=>setTimeout(resolve,1000));
      state = (await inspect()).result;
      if (state.guest && !state.frameUrl) break;
    }
  }
  if (state.frameUrl && state.guest) throw new Error('Zoom reopened its embedded page. Voice is not connected yet.');
  return state.guest;
}

export async function runMeetingAction(client, method, params) {
  if (method === 'zoommeetings.speak') {
    // Refresh real bridge health before calling speak; the plugin can cache old readiness.
    const current = await client.request('zoommeetings.status', {sessionId:params.sessionId});
    if (!current.session) return current;
    if (!await prepareVoicePage(client,current.session)) return {
      ok:false, error:{message:'Complete Zoom admission in the browser, then choose Connect voice.'},
      session:current.session,
    };
    await client.request('zoommeetings.status', {sessionId:params.sessionId});
    return client.request(method,params);
  }
  let result;
  if (method === 'zoommeetings.join') {
    const status = await client.request('zoommeetings.status', {});
    const active = (status.sessions || []).filter(session => session.state === 'active');
    const meetingPath = new URL(params.url).pathname.replace(/\/$/, '');
    if (active.length > 1 || active.some(session => new URL(session.url).pathname.replace(/\/$/, '') !== meetingPath)) {
      throw new Error('Hikari is already in another meeting. Leave that meeting before joining this one.');
    }
    result = active.length === 1 ? {session: active[0], reused: true} : await client.request(method, params);
  } else result = await client.request(method,params);
  if (method !== 'zoommeetings.join' || !result.session) return result;
  if (await prepareVoicePage(client,result.session)) {
    const refreshed = await client.request('zoommeetings.status', {sessionId:result.session.id});
    if (refreshed.session?.chrome?.health?.speechReady !== true) {
      return client.request('zoommeetings.speak',{sessionId:result.session.id,message:GREETING});
    }
    return refreshed;
  }
  return result;
}
