'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const {filterPapers} = require('../dashboard/literature.js');
const {obsidianOpenUri} = require('../dashboard/literature.js');
const {checkpointPapers} = require('../dashboard/literature.js');
const papers = [
  {id:'a',title:'Spherical waves',authors:['Mörlein, Leonardo'],year:2025,doi:'10.1234/example',type:'article',reading_status:'metadata_only',backlinks:[{project_id:'one'},{project_id:'two'}],origins:[{source_id:'vault-a',record_id:'native-key'}]},
  {id:'b',title:'研究路径与文献',reading_status:'reviewed',backlinks:[{project_id:'two'}]},
  {id:'c',title:'<script>alert(1)</script>',type:'manual'}
];
test('empty query returns every record without changing input',()=>{
  const before=JSON.stringify(papers);assert.equal(filterPapers(papers,{query:'  '}).length,3);assert.equal(JSON.stringify(papers),before);
});
test('Unicode and accent-insensitive author search',()=>{
  assert.equal(filterPapers(papers,{query:'研究'})[0].id,'b');assert.equal(filterPapers(papers,{query:'morlein'})[0].id,'a');
});
test('search supports DOI and source origin keys',()=>{
  for(const query of ['10.1234','NATIVE-KEY','vault-a'])assert.equal(filterPapers(papers,{query})[0].id,'a');
});
test('one record can belong to multiple projects without duplication',()=>{
  assert.equal(filterPapers(papers,{project:'one'}).length,1);assert.equal(filterPapers(papers,{project:'two'}).length,2);
});
test('missing metadata and combined filters are handled',()=>{
  assert.equal(filterPapers(papers,{status:'metadata_only'}).length,2);assert.equal(filterPapers(papers,{type:'unspecified'})[0].id,'b');
  assert.equal(filterPapers(papers,{project:'two',status:'reviewed'})[0].id,'b');
});
test('no match and genuinely empty collection',()=>{
  assert.deepEqual(filterPapers(papers,{query:'does not exist'}),[]);assert.deepEqual(filterPapers([]),[]);
});
test('markup remains literal data',()=>{
  assert.equal(filterPapers(papers,{query:'<script>'})[0].title,'<script>alert(1)</script>');
});
test('checkpoint view derives both link sources without duplicating papers or widening context',()=>{
  const records=[{id:'shared',backlinks:[{project_id:'a',checkpoint_id:'node',relevance:['specific']},{project_id:'a',checkpoint_id:'node',relevance:['specific','extra']},{project_id:'b',checkpoint_id:'node',relevance:['other project']}]},
    {id:'general',backlinks:[{project_id:'a',checkpoint_id:null,relevance:['project only']}]},{id:'unlinked'}];
  const before=JSON.stringify(records), result=checkpointPapers(records,'a','node');
  assert.equal(result.length,1);assert.equal(result[0].paper.id,'shared');assert.equal(result[0].relevance,'specific\n\nextra');
  assert.deepEqual(checkpointPapers(records,'a','missing'),[]);assert.equal(JSON.stringify(records),before);
});
test('Obsidian open permits only the exact known encoded note path',()=>{
  const absolute_path='E:\\研究 Vault\\Papers\\模式 #1 & 2.md';
  const uri='obsidian://open?path='+encodeURIComponent(absolute_path);
  assert.equal(obsidianOpenUri({absolute_path,uri}),uri);
  for(const unsafe of [uri+'&append=1',uri+'&content=bad',uri+'&path=other',uri+'#extra',uri.replace('//open?','//new?'),uri.replace('//open?','//user@open?'),'javascript:alert(1)','obsidian://open?path=elsewhere','obsidian://open?vault=other&file=note']){
    assert.equal(obsidianOpenUri({absolute_path,uri:unsafe}),null);
  }
  assert.equal(obsidianOpenUri({absolute_path:'relative.md',uri:'obsidian://open?path=relative.md'}),null);
});
