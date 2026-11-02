const test=require('node:test');const assert=require('node:assert/strict');const a=require('../dashboard/attention.js');
const item=(status='active')=>({id:'fixture',section:'life',priority:'medium',project_refs:[],decision:{status}});
const accounts=[{id:'new',email:'new+research@example.test'},{id:'old',email:'older@example.test'}];
const linked=(account='new',id='<a+b/c=d@example.test>')=>({source:{account_id:account,date:'2026-11-02',rfc822_message_id:id,gmail_message_id:'1abc',gmail_thread_id:'2def',url:'https://mail.google.com/mail/u/0/#all/1abc'}});
test('exact email search selects the named account and encodes the whole query',()=>{
  for(const account of accounts){const link=a.sourceLink(linked(account.id),accounts),url=new URL(link.url);assert.equal(url.searchParams.get('authuser'),account.email);assert.equal(decodeURIComponent(url.hash.slice('#search/'.length)),'in:anywhere rfc822msgid:a+b/c=d@example.test');assert.equal(link.kind,'exact-search');assert.match(url.hash,/%2B/);assert.match(url.hash,/%3D/);assert.doesNotMatch(url.hash,/1abc|2def|#all/);}
});
test('Gmail message and thread IDs never become browser identifiers',()=>{
  const value=linked();delete value.source.rfc822_message_id;const link=a.sourceLink(value,accounts);assert.equal(link.kind,'date-search');assert.equal(link.query,'after:2026/11/01 before:2026/11/04');assert.doesNotMatch(link.url,/1abc|2def/);
  value.source.rfc822_message_id='1abc';assert.equal(a.sourceLink(value,accounts).kind,'date-search');delete value.source.date;assert.equal(a.sourceLink(value,accounts).kind,'unavailable');
});
test('unsafe headers, ambiguous account and invalid dates never create exact links',()=>{
  for(const id of ['<a@example.test> OR from:someone','a@example.test\nBcc:x','<nested<id@example.test>>','<img src=x>'])assert.equal(a.sourceLink(linked('new',id),accounts).kind,'date-search');
  assert.equal(a.sourceLink(linked('unknown'),accounts).kind,'unavailable');const value=linked();delete value.source.rfc822_message_id;value.source.date='2026-02-31';assert.equal(a.sourceLink(value,accounts).kind,'unavailable');
});
test('Unicode header and legacy account selector remain safely encoded',()=>{
  const value=linked('new','研究+ID@example.test');const link=a.sourceLink(value,accounts);assert.equal(decodeURIComponent(new URL(link.url).hash.slice(8)),'in:anywhere rfc822msgid:研究+ID@example.test');
  value.source.url='https://mail.google.com/mail/u/?authuser=older%40example.test#all/1abc';assert.equal(a.sourceLink(value,[]).email,'older@example.test');value.source.url='https://evil.test/?authuser=older%40example.test';assert.equal(a.sourceLink(value,[]).kind,'unavailable');
});
test('decisions hide handled items unless requested',()=>{for(const s of ['resolved','not_relevant']){assert.equal(a.visible([item(s)],'today').length,0);assert.equal(a.visible([item(s)],'life',true).length,1);}});
test('snooze returns after its exact timestamp',()=>{const i=item('snoozed');i.decision.snooze_until='2026-11-03T00:00:00Z';assert.equal(a.active(i,Date.parse('2026-11-02T23:59:59Z')),false);assert.equal(a.active(i,Date.parse(i.decision.snooze_until)),true);});
test('one record can appear via crosslink without duplication',()=>{const i=item();i.project_refs=['research-fixture'];assert.deepEqual(a.visible([i],'research'),[i]);assert.equal(a.visible([i],'today').length,1);});
test('priority sorting, empty sources and literal Unicode',()=>{const i=item();i.title='研究 <script>fixture</script>';const h={...item(),id:'high',priority:'high'};assert.equal(a.visible([i,h],'today')[0],h);assert.deepEqual(a.visible([],'today'),[]);assert.equal(a.visible([i],'life')[0].title,i.title);});
