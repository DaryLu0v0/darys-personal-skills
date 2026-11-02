'use strict';
/* No source data or accounts are bundled here. All content comes from the local API. */
const HikariAttention = (() => {
  const stateLabels={active:'待关注',resolved:'已处理',snoozed:'稍后提醒',not_relevant:'不相关'};
  const evidenceLabels={needs_verification:'当前状态待核实',course_deadline_role_unverified:'课程角色与任务待确认',confirmed_upcoming:'已确认的安排',fyi:'知悉即可'};
  function active(item,now=Date.now()) {const d=item.decision||{status:'active'};return d.status==='active'||(d.status==='snoozed'&&Date.parse(d.snooze_until)<=now);}
  function visible(items,view,includeHandled=false,now=Date.now()) {return items.filter(i=>(view==='today'||i.section===view||(view==='research'&&i.project_refs?.length))&&(includeHandled||active(i,now))).sort((a,b)=>({high:0,medium:1,low:2}[a.priority]-{high:0,medium:1,low:2}[b.priority]));}
  function sourceLink(item,accounts=[]) {
    const source=item.source||{}, account=accounts.find(a=>a.id===source.account_id);
    let email=account?.email||'';
    if(!email)try{const old=new URL(source.url);if(old.protocol==='https:'&&old.hostname==='mail.google.com'&&!old.username&&!old.password)email=old.searchParams.get('authuser')||'';}catch{}
    if(!/^[^\s<>"@?&#]+@[^\s<>"@?&#]+$/.test(email))return {kind:'unavailable',note:'邮箱账号未确认，暂无法定位原邮件。'};
    const raw=typeof source.rfc822_message_id==='string'?source.rfc822_message_id.trim():'';
    const id=raw.startsWith('<')&&raw.endsWith('>')?raw.slice(1,-1):raw;
    let query,label,note,kind;
    if(id.length<=1000&&/^[^\s<>"@]+@[^\s<>"@]+$/.test(id)){
      query='in:anywhere rfc822msgid:'+id;label='查找这封原邮件 ↗';kind='exact-search';
      note='按邮件标识搜索。Gmail 可能先显示结果列表，请打开匹配邮件。';
    }else{
      // API message IDs and thread IDs are deliberately not treated as web permalinks.
      const value=source.date;
      if(!/^\d{4}-\d{2}-\d{2}$/.test(value||''))return {kind:'unavailable',note:'缺少邮件标识和可靠日期，暂无法定位原邮件。'};
      const day=new Date(value+'T00:00:00Z');
      if(!Number.isFinite(+day)||day.toISOString().slice(0,10)!==value)return {kind:'unavailable',note:'来源日期无效，暂无法定位原邮件。'};
      const bound=offset=>new Date(+day+offset*86400000).toISOString().slice(0,10).replaceAll('-','/');
      query='after:'+bound(-1)+' before:'+bound(2);label='在来源日期附近查找 ↗';kind='date-search';
      note='缺少邮件标识；此日期搜索可能返回多封邮件，并非原邮件直达链接。';
    }
    return {kind,email,query,label,note,url:'https://mail.google.com/mail/?authuser='+encodeURIComponent(email)+'#search/'+encodeURIComponent(query)};
  }
  return {stateLabels,evidenceLabels,active,visible,sourceLink};
})();
if(typeof module!=='undefined')module.exports=HikariAttention;
