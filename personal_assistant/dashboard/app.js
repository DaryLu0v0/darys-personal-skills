'use strict';
const $ = id => document.getElementById(id);
const labels = {completed:'Completed',active:'Open follow-up',possible:'Possible',parked:'Parked',closed:'Closed',superseded:'Superseded'};
const basisLabels = {documented_implementation:'Documented implementation',reported_check:'Reported check · not rerun',inspected_saved_result:'Saved result inspected',user_decision:'User decision',user_correction:'User correction',proposal:'Proposed next step',observed_record:'Source record inspected'};
let library, project, selected, selectedPaper, collapsed = new Set();
let currentView = ['today','life','research','papers'].includes(location.hash.slice(1)) ? location.hash.slice(1) : 'today';
let attentionData, attentionError, attentionBusy=false;
const readingLabels = {metadata_only:'Metadata only',queued:'To read',reading:'Reading',reviewed:'Reviewed in Hikari'};
function el(tag, cls, text) { const n=document.createElement(tag); if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n; }
function safeLink(text, href) { const a=el('a','',text); try {const u=new URL(href); if(u.protocol!=='https:'||u.username||u.password) throw Error('Unsafe link');a.href=u.href;a.target='_blank';a.rel='noopener noreferrer';}catch{a.removeAttribute('href');a.title='Invalid link';}return a; }
function noteLink(text, target) {const href=HikariLiterature.obsidianOpenUri(target);if(!href)return el('span','meta','Obsidian link unavailable');const a=el('a','obsidian-link',text);a.href=href;return a;}
function date(value) {return value ? new Date(value).toLocaleDateString(undefined,{year:'numeric',month:'short',day:'numeric',timeZone:'UTC'}) : 'Date not established';}
function persist() {try{localStorage.setItem('hikari-view:'+project.id,JSON.stringify([...collapsed]));}catch{}}
function getLayout(nodes, edges, hidden) {
  const byId=new Map(nodes.map(n=>[n.id,n])), parents=new Map(nodes.map(n=>[n.id,[]])), children=new Map(nodes.map(n=>[n.id,[]]));
  edges.forEach(e=>{parents.get(e.to).push(e.from);children.get(e.from).push(e.to);});
  const degree=new Map([...parents].map(([k,v])=>[k,v.length]));const queue=nodes.filter(n=>!degree.get(n.id)).map(n=>n.id),rank=new Map(queue.map(n=>[n,0])),reachable=new Set(queue);
  while(queue.length){const n=queue.shift();for(const child of children.get(n)){rank.set(child,Math.max(rank.get(child)||0,rank.get(n)+1));if(reachable.has(n)&&!hidden.has(n))reachable.add(child);degree.set(child,degree.get(child)-1);if(degree.get(child)===0)queue.push(child);}}
  return {byId,children,parents,rank,reachable};
}
function renderGraph() {
  const layout=getLayout(project.checkpoints,project.relationships,collapsed),query=$('search').value.toLowerCase(),status=$('status').value;
  const visible=project.checkpoints.filter(n=>layout.reachable.has(n.id)&&(status==='all'||n.status===status)&&JSON.stringify([n.title,n.goal,n.done,n.next]).toLowerCase().includes(query));
  $('nodes').replaceChildren();$('edges').replaceChildren();const rows=new Map();
  for(const n of visible){const r=layout.rank.get(n.id);if(!rows.has(r))rows.set(r,[]);rows.get(r).push(n);}
  for(const [rank,nodes] of [...rows].sort((a,b)=>a[0]-b[0])){
    const row=el('div','rank');row.dataset.rank=rank;
    for(const n of nodes){const box=el('div','node '+n.status+(n.id===selected?' selected':''));box.dataset.id=n.id;
      const btn=el('button','node-main');btn.setAttribute('aria-label',n.title+' — '+labels[n.status]);btn.setAttribute('aria-pressed',String(n.id===selected));
      btn.append(el('span','badge '+n.status,labels[n.status]),el('span','node-title',n.title));
      const sourceCount=new Set([...n.evidence_ids,...n.done.flatMap(x=>x.evidence_ids),...n.next.flatMap(x=>x.evidence_ids)]).size;
      const foot=el('span','node-foot');foot.append(el('span','',sourceCount+' sources'),el('span','',n.occurred_at?date(n.occurred_at):'Reconstructed'));btn.append(foot);
      btn.onclick=()=>{selected=n.id;renderGraph();renderDetail();};box.append(btn);
      if(layout.children.get(n.id).length){const c=el('button','collapse',(collapsed.has(n.id)?'+ Show':'− Collapse')+' next branches');c.setAttribute('aria-expanded',String(!collapsed.has(n.id)));c.onclick=()=>{if(collapsed.has(n.id))collapsed.delete(n.id);else collapsed.add(n.id);persist();renderGraph();};box.append(c);}
      row.append(box);
    }$('nodes').append(row);
  }
  $('map-message').textContent=visible.length?`${visible.length} of ${project.checkpoints.length} checkpoints shown · Select a card to inspect its evidence.`:'No checkpoints match. Clear the search or expand branches.';
  requestAnimationFrame(drawEdges);
}
function drawEdges(){
  if(!project||$('research-content').hidden)return;
  const svg=$('edges'),root=$('graph').getBoundingClientRect();svg.replaceChildren();
  const boxes=new Map([...document.querySelectorAll('.node')].map(n=>[n.dataset.id,n.getBoundingClientRect()]));
  for(const e of project.relationships){if(collapsed.has(e.from)||!boxes.has(e.from)||!boxes.has(e.to))continue;const a=boxes.get(e.from),b=boxes.get(e.to),x1=a.left+a.width/2-root.left,y1=a.bottom-root.top,x2=b.left+b.width/2-root.left,y2=b.top-root.top,mid=(y1+y2)/2;
    const path=document.createElementNS('http://www.w3.org/2000/svg','path');path.setAttribute('d',`M${x1},${y1} C${x1},${mid} ${x2},${mid} ${x2},${y2}`);svg.append(path);
  }
}
function section(number,title){const h=el('h3','section-label');h.append(el('span','num',number),document.createTextNode(title));return h;}
function renderEvidence(e){
  const d=el('details','evidence-item');d.append(el('summary','', (e.kind==='conversation'?'◌ ':e.kind==='experiment'?'▧ ':'↗ ')+e.title));
  d.append(el('p','',e.summary),el('span','basis',basisLabels[e.basis]||e.basis));
  if(e.excerpt)d.append(el('blockquote','',e.speaker+': “'+e.excerpt+'”'));
  if(e.url){const link=el('p','');link.append(safeLink(e.kind==='conversation'?'Open exact conversation message ↗':'Open pinned source ↗',e.url));d.append(link);}
  if(e.local_path)d.append(el('p','meta','Local reference: '+e.local_path));
  if(e.native_reference)d.append(el('p','meta','Native conversation reference: '+e.native_reference));
  d.append(el('p','meta','Work: '+date(e.occurred_at)+' · Checked: '+date(e.checked_at)),el('p','meta',e.access_note));
  if(e.source_revision)d.append(el('code','',e.source_revision));return d;
}
function renderDetail(){
  const n=project.checkpoints.find(n=>n.id===selected);if(!n)return;const d=$('detail');d.replaceChildren();
  d.append(el('span','badge '+n.status,labels[n.status]),el('h2','',n.title),el('p','status-note',n.status_note),el('p','date',(n.occurred_at?'Milestone: '+date(n.occurred_at):'Underlying work date not established')+' · Recorded '+date(n.recorded_at)));
  d.append(section('01','GOAL'),el('p','goal',n.goal));
  for(const [key,title,num] of [['done','DONE AND LEARNED','02'],['next','NEXT','03']]){d.append(section(num,title));for(const c of n[key]){const box=el('div','claim');box.append(el('p','',c.text),el('span','basis',basisLabels[c.basis]));d.append(box);}}
  const sources=el('div','evidence-list');sources.append(el('h3','section-label','SUPPORTING EVIDENCE'));
  const ids=new Set([...n.evidence_ids,...n.done.flatMap(x=>x.evidence_ids),...n.next.flatMap(x=>x.evidence_ids)]);
  for(const id of ids)sources.append(renderEvidence(project.evidence.find(e=>e.id===id)));
  for(const ref of HikariLiterature.checkpointPapers(library.papers,project.id,n.id)){const p=ref.paper,box=el('details','evidence-item');box.append(el('summary','','▤ '+p.title),el('p','',ref.relevance),el('p','',p.summary),el('span','basis','Paper · '+p.access.replaceAll('_',' ')),el('p','meta',p.access_note));const open=el('button','quiet','View in literature library →');open.onclick=()=>openPaper(p.id);const action=el('p','');action.append(open);box.append(action);if(p.url){const link=el('p','');link.append(safeLink('Open paper reference ↗',p.url));box.append(link);}if(p.local_path)box.append(el('code','',p.local_path));sources.append(box);}
  d.append(sources);
}
function selectProject(p, reveal = true){
  project=p;selected=p.checkpoints.some(n=>n.id===selected)?selected:(p.checkpoints.find(n=>n.id==='synthesis')||p.checkpoints[0])?.id;
  try{const saved=JSON.parse(localStorage.getItem('hikari-view:'+p.id)||'[]');collapsed=new Set(Array.isArray(saved)?saved:[]);}catch{collapsed=new Set();}
  $('title').textContent=p.title;$('summary').textContent=p.summary;$('coverage').textContent=p.coverage;$('sources').replaceChildren();
  for(const s of p.sources)$('sources').append(safeLink('⌘ '+s.title+' · '+s.branch,s.url+'/tree/'+s.revision));
  $('total').textContent=p.checkpoints.length;for(const s of ['completed','active','possible'])$(s).textContent=p.checkpoints.filter(n=>n.status===s).length;
  $('revision').textContent='Library revision '+p.revision+'\n'+p.applied_updates.length+' reconciled handoff';
    $('candidate-title').textContent=library.candidates[0]?.title||'Sources connected';
    $('candidate-note').textContent=library.candidates[0]?.note||'No pending source mappings.';
  $('workflow-evidence').replaceChildren();for(const e of library.workflow?.evidence||[])$('workflow-evidence').append(renderEvidence(e));
  renderGraph();renderDetail();
  if(reveal)showView('research');
}
function showView(view){
  if(!['today','life','research','papers'].includes(view))view='today';
  currentView=view;$('research-content').hidden=view!=='research';$('papers-content').hidden=view!=='papers';
  $('attention-content').hidden=!['today','life'].includes(view);$('maintenance-panel').hidden=!['research','papers'].includes(view);
  const name={today:'Today',life:'Life',research:'Research paths',papers:'Literature'}[view];
  document.title='Hikari · '+name;$('breadcrumb').textContent=name;
  for(const v of ['today','life','research','papers']){const b=$('nav-'+v);if(v===view)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current');}
  history.replaceState(null,'','#'+view);window.scrollTo(0,0);
  renderAttention();if(view==='research'&&project)requestAnimationFrame(drawEdges);
}

function openPaper(id){
  selectedPaper=id;$('paper-search').value='';for(const key of ['paper-status','paper-project','paper-type'])$(key).value='all';
  renderPapers();showView('papers');
}
function openResearch(backlink){
  const target=library.projects.find(p=>p.id===backlink.project_id);if(!target)return;
  selected=backlink.checkpoint_id||undefined;selectProject(target);
  $('search').value='';$('status').value='all';
  if(backlink.checkpoint_id){const parents=getLayout(project.checkpoints,project.relationships,new Set()).parents,stack=[backlink.checkpoint_id],seen=new Set();
    while(stack.length){const id=stack.pop();if(seen.has(id))continue;seen.add(id);collapsed.delete(id);stack.push(...parents.get(id));}persist();}
  renderGraph();renderDetail();
}
function renderPaperSources(){
  $('vault-note').replaceChildren();
  if(library.vault){$('vault-note').append(el('strong','','Read and write in Obsidian'),el('p','','Paper metadata and notes are read directly from your local vault. Save in Obsidian, then refresh records here.'));if(library.vault.home)$('vault-note').append(noteLink('Open research vault →',library.vault.home));$('vault-note').append(el('p','meta',library.vault.absolute_path));}
  const sources=library.paper_sources||[],gaps=sources.filter(s=>s.status!=='available');
  $('paper-total').textContent=library.papers.length;$('paper-reviewed').textContent=library.papers.filter(p=>p.reading_status==='reviewed').length;
  $('paper-projects').textContent=new Set(library.papers.flatMap(p=>(p.backlinks||[]).map(b=>b.project_id))).size;$('paper-gaps').textContent=gaps.length;
  $('paper-coverage-heading').textContent=`Indexed coverage · ${sources.filter(s=>s.status==='available').length} available sources · ${gaps.length} source gaps`;
  $('paper-source-list').replaceChildren();
  for(const source of sources){const card=el('div','paper-source');card.append(el('strong','',source.title),el('span','badge '+(source.status==='available'?'completed':'active'),source.status),el('p','',source.note),el('p','meta','Checked '+date(source.checked_at)));if(source.url)card.append(safeLink('Source metadata ↗',source.url));$('paper-source-list').append(card);}
  for(const [id,values,label] of [['paper-project',library.projects.map(p=>[p.id,p.title]),'All projects'],['paper-type',[...new Set(library.papers.map(p=>p.type||'unspecified'))].sort().map(t=>[t,t[0].toUpperCase()+t.slice(1)]),'All source types']]){
    const select=$(id),previous=select.value;select.replaceChildren();const all=el('option','',label);all.value='all';select.append(all);for(const [value,title] of values){const option=el('option','',title);option.value=value;select.append(option);}select.value=values.some(v=>v[0]===previous)?previous:'all';
  }
}
function renderPapers(){
  if(!library)return;
  const visible=HikariLiterature.filterPapers(library.papers,{query:$('paper-search').value,status:$('paper-status').value,project:$('paper-project').value,type:$('paper-type').value});
  if(!visible.some(p=>p.id===selectedPaper))selectedPaper=visible[0]?.id;
  $('paper-list').replaceChildren();$('paper-count').textContent=`${visible.length} of ${library.papers.length} indexed references shown`;
  if(!visible.length){$('paper-list').append(el('p','paper-empty',library.papers.length?'No references match these filters. Try another term or clear the filters.':'No references are indexed yet. Add a source-backed canonical paper record to begin.'));$('paper-detail').replaceChildren(el('h2','','Nothing selected'),el('p','goal','Paper details and research backlinks will appear here.'));return;}
  for(const p of visible){const card=el('button','paper-card'+(p.id===selectedPaper?' selected':''));card.setAttribute('aria-label','Open paper: '+p.title);card.setAttribute('aria-pressed',String(p.id===selectedPaper));
    const top=el('span','paper-card-top');top.append(el('span','badge',p.type||'Reference'),el('span','reading-tag',readingLabels[p.reading_status||'metadata_only']));card.append(top,el('strong','paper-title',p.title),el('span','paper-authors',(p.authors?.length?p.authors.join('; '):'Authors not yet verified')+' · '+(p.year||'Year not verified')));
    const count=(p.backlinks||[]).length;
    const foot=el('span','paper-card-foot');foot.append(el('span','',p.venue||'Source metadata only'),el('span','',count+' research link'+(count===1?'':'s')));card.append(foot);card.onclick=()=>{selectedPaper=p.id;renderPapers();if(window.innerWidth<=1160)$('paper-detail').scrollIntoView({block:'start'});};$('paper-list').append(card);
  }renderPaperDetail();
}
function renderPaperDetail(){
  const p=library.papers.find(p=>p.id===selectedPaper),d=$('paper-detail');if(!p)return;d.replaceChildren();
  d.append(el('span','badge',readingLabels[p.reading_status||'metadata_only']),el('h2','',p.title),el('p','paper-byline',p.authors?.length?p.authors.join('; '):'Authors not yet verified'));
  const meta=el('dl','paper-metadata');for(const [name,value] of [['Year',p.year||'Not verified'],['Publication / source',p.venue||'Not verified'],['DOI',p.doi||'Not recorded'],['Source type',p.type||'Unspecified']]){meta.append(el('dt','',name),el('dd','',value));}d.append(meta);
  if(p.url){const row=el('p','paper-link');row.append(safeLink(p.doi?'Open DOI ↗':'Open reference source ↗',p.url));d.append(row);}
  if(p.obsidian){const row=el('div','vault-actions');row.append(noteLink('Open note in Obsidian →',p.obsidian),el('p','meta','Edit this note in Obsidian. This dashboard is a read-only projection.'));if(p.pdf)row.append(el('p','meta',p.pdf.available?'Local PDF attached · reading status unchanged':'PDF attachment is missing on this machine'));else row.append(el('p','meta','No local PDF attached'));d.append(row);}
  d.append(section('01','GENERAL SUMMARY'),el('p','goal',p.summary),el('p','status-note',p.access_note));
  if(p.reading_notes)d.append(el('h3','section-label','READING NOTES'),el('div','note-text',p.reading_notes));
  if(p.relevance_notes)d.append(el('h3','section-label','YOUR PROJECT RELEVANCE NOTES'),el('div','note-text',p.relevance_notes));
  d.append(section('02','RELATED RESEARCH'));
  if(!p.backlinks?.length)d.append(el('p','goal','No project or checkpoint links recorded yet.'));
  for(const backlink of p.backlinks||[]){const box=el('div','paper-backlink');box.append(el('strong','',backlink.project_title+(backlink.checkpoint_title?' / '+backlink.checkpoint_title:' / project context')));for(const relevance of backlink.relevance)box.append(el('p','',relevance));const open=el('button','quiet',backlink.checkpoint_id?'Open checkpoint →':'Open research path →');open.onclick=()=>openResearch(backlink);box.append(open);for(const href of backlink.evidence_urls){const row=el('p','');row.append(safeLink('Context source ↗',href));box.append(row);}d.append(box);}
  d.append(section('03','ORIGIN & ACCESS'));
  for(const origin of p.origins||[]){const source=(library.paper_sources||[]).find(s=>s.id===origin.source_id),box=el('div','paper-origin');box.append(el('strong','',source?.title||origin.source_id),el('code','',origin.record_id),el('p','meta','Metadata checked '+date(origin.checked_at)));box.append(safeLink('Original metadata record ↗',origin.url));if(origin.revision)box.append(el('p','meta','Revision '+origin.revision));d.append(box);}
  if(p.local_path)d.append(el('p','meta','Local source retained at its original location:'),el('code','local-path',p.local_path));
  d.append(el('p','meta','Canonical ID: '+p.id));
}
async function load(){
  $('refresh').disabled=true;$('error').hidden=true;
  try{const r=await fetch('/api/library',{cache:'no-store'});const data=await r.json();if(!r.ok)throw Error(data.error||'Records could not be loaded');library=data;$('projects').replaceChildren();
    if(!library.projects.length){project=undefined;$('title').textContent='Your first research path';$('summary').textContent='No project records yet. Add a validated project and handoff.';$('nodes').replaceChildren();$('detail').replaceChildren();}
    for(const p of library.projects){const b=el('button','','◈  '+p.title);b.onclick=()=>selectProject(p);$('projects').append(b);}if(library.projects.length)selectProject(library.projects.find(p=>p.id===project?.id)||library.projects.find(p=>p.id==='sample-research')||library.projects[0],false);
    renderMaintenance();renderPaperSources();renderPapers();showView(currentView);
  }catch(e){$('error').hidden=false;$('error').textContent=e.message;}
  finally{$('refresh').disabled=false;}
}
function renderMaintenance(){
  const m=library.maintenance||{projects:[],pending_items:[],coverage:[]};
  $('maintenance-heading').textContent=`Conversation intake · ${m.projects.length} project sources · ${m.projects_pending_mapping||0} mappings pending`;
  $('maintenance-note').textContent=m.note||'No conversation batches received yet.';
  $('maintenance-projects').replaceChildren();$('maintenance-pending').replaceChildren();
  for(const p of m.projects){const row=el('p','meta',`${p.title} · ${p.provider} · ${p.mapping_status}${p.canonical_project_id?' → '+p.canonical_project_id:''}`);$('maintenance-projects').append(row);}
  for(const p of m.pending_items||[])$('maintenance-pending').append(el('p','status-note',p.reason));
  for(const c of m.coverage||[])$('maintenance-pending').append(el('p','meta','Coverage: '+c.note));
}
$('search').addEventListener('input',()=>{if(project)renderGraph();});$('status').addEventListener('change',()=>{if(project)renderGraph();});$('expand').onclick=()=>{collapsed.clear();if(project){persist();renderGraph();}};$('refresh').onclick=()=>{load();loadAttention();};
window.addEventListener('resize',()=>requestAnimationFrame(drawEdges));load();
$('nav-research').onclick=()=>showView('research');$('nav-papers').onclick=()=>showView('papers');
$('paper-search').addEventListener('input',renderPapers);for(const id of ['paper-status','paper-project','paper-type'])$(id).addEventListener('change',renderPapers);
$('paper-reset').onclick=()=>{$('paper-search').value='';for(const id of ['paper-status','paper-project','paper-type'])$(id).value='all';renderPapers();};

function renderAttention(){
  $('attention-title').textContent=currentView==='life'?'Life · 日常值得留意的事':'今天需要关注';
  $('attention-intro').textContent=currentView==='life'?'行政、课程支持、日程和工具维护。邮件只提供线索，当前状态仍需要核实。':'先核实，再行动。把需要留意的事和已确认的安排放在一起。';
  $('attention-error').hidden=!attentionError;$('attention-error').textContent=attentionError||'';
  $('attention-list').replaceChildren();$('attention-fyi').replaceChildren();
  if(!attentionData){$('attention-checked').textContent=attentionError?'本地快照不可用，请刷新重试。':'正在读取本地快照…';$('attention-count').textContent='需要关注';$('attention-fyi-title').hidden=true;return;}
  $('attention-checked').textContent=attentionData.checked_at?'检查时间：'+new Date(attentionData.checked_at).toLocaleString(undefined,{timeZoneName:'short'})+' · 邮箱及门户当前状态未实时检查':'尚未导入邮件快照。';
  $('attention-coverage').textContent=attentionData.coverage;$('attention-accounts').replaceChildren();
  for(const account of attentionData.accounts)$('attention-accounts').append(el('p','meta',account.label));
  const items=HikariAttention.visible(attentionData.items,currentView==='life'?'life':'today',$('attention-handled').checked);
  const main=items.filter(i=>!['fyi','confirmed_upcoming'].includes(i.evidence_status)),info=items.filter(i=>['fyi','confirmed_upcoming'].includes(i.evidence_status));
  $('attention-count').textContent=main.filter(i=>HikariAttention.active(i)).length+' 项需要关注'+($('attention-handled').checked?' · '+main.length+' 项显示':'');
  if(!main.length)$('attention-list').append(el('p','attention-empty',attentionData.items.length?'当前筛选下没有需要处理的项目。已处理事项仍保留在本地。':'还没有提醒记录。导入经核实的邮件线索后，它们会出现在这里。'));
  for(const item of main)$('attention-list').append(attentionCard(item));
  $('attention-fyi-title').hidden=!info.length;for(const item of info)$('attention-fyi').append(attentionCard(item));
}
function attentionCard(item){
  const card=el('article','attention-card priority-'+item.priority);card.dataset.attentionId=item.id;
  const head=el('div','attention-card-head');head.append(el('span','attention-kind',HikariAttention.evidenceLabels[item.evidence_status]),el('span','decision-state',HikariAttention.stateLabels[item.decision.status]));
  card.append(head,el('h3','',item.title),el('p','',item.summary));
  if(item.action)card.append(el('p','attention-action','下一步：'+item.action));
  for(const d of item.dates||[])card.append(el('p','attention-date',d.label+'：'+d.local+' · '+d.timezone));
  const source=attentionData.accounts.find(a=>a.id===item.source.account_id);
  card.append(el('p','attention-source',(source?.label||item.source.account_id)+' · 邮件 '+item.source.date));
  const original=HikariAttention.sourceLink(item,attentionData.accounts),links=el('div','attention-links');
  if(original.url)links.append(safeLink(original.label,original.url));
  card.append(el('p','attention-source',original.note));
  if(original.query){const help=el('details','attention-search-help');help.append(el('summary','','无法定位？复制搜索词'),el('p','','请在 '+original.email+' 的 Gmail 搜索框粘贴：'),el('code','',original.query));card.append(help);}
  for(const link of item.links||[])links.append(safeLink(link.title+' ↗',link.url));
  for(const ref of item.project_refs||[]){const p=library?.projects.find(p=>p.id===ref);if(p){const b=el('button','quiet',p.title+' ↗');b.onclick=()=>selectProject(p);links.append(b);}}
  card.append(links);
  if(item.decision.status==='snoozed')card.append(el('p','attention-date','重新显示：'+new Date(item.decision.snooze_until).toLocaleString()+(HikariAttention.active(item)?'（已到时间）':'')));
  const actions=el('div','attention-actions');
  for(const [status,label] of [['resolved','已处理'],['snoozed','稍后提醒 · 24小时'],['not_relevant','不相关'],['active','重新关注']]){
    if(item.decision.status===status||(status==='active'&&item.decision.status==='active'))continue;
    const b=el('button','quiet',label);b.disabled=attentionBusy;b.setAttribute('aria-label',label+'：'+item.title);b.onclick=()=>saveAttention(item,status);actions.append(b);
  }card.append(actions);return card;
}
async function loadAttention(){
  $('attention-feedback').textContent='';
  try{const r=await fetch('/api/attention',{cache:'no-store'});const d=await r.json();if(!r.ok)throw Error(d.error||'无法读取本地快照');attentionData=d;attentionError='';}
  catch(e){attentionError='提醒读取失败：'+e.message;attentionData=undefined;}
  renderAttention();
}
async function saveAttention(item,status){
  if(attentionBusy)return;attentionBusy=true;attentionError='';renderAttention();
  try{const r=await fetch('/api/attention/decision',{method:'POST',headers:{'Content-Type':'application/json','X-Hikari-Token':attentionData.action_token},body:JSON.stringify({id:item.id,status,snooze_until:status==='snoozed'?new Date(Date.now()+86400000).toISOString():null,expected_revision:attentionData.decision_revision})});const d=await r.json();if(!r.ok)throw Error(d.error||'保存失败');attentionData=d;$('attention-feedback').textContent='已在本地保存：'+item.title+' · '+HikariAttention.stateLabels[status];}
  catch(e){attentionError='未保存：'+e.message+'。刷新后再试。';}
  finally{attentionBusy=false;renderAttention();$('attention-handled').focus();}
}
$('nav-today').onclick=()=>showView('today');$('nav-life').onclick=()=>showView('life');
$('attention-handled').onchange=renderAttention;
window.addEventListener('hashchange',()=>showView(location.hash.slice(1)));
loadAttention();
