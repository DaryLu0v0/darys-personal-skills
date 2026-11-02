"""Synthetic-only attention fixtures. Never import real mail data in tests."""
import copy
import json
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import attention
import serve_library
from library import ROOT


class AttentionTests(unittest.TestCase):
    def setUp(self):
        (ROOT/'.local/test-temp').mkdir(parents=True,exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(dir=ROOT/'.local/test-temp'); self.root=Path(self.tmp.name)
        self.source=self.root/'.local/import.json';self.source.parent.mkdir()
        self.snapshot={'schema_version':1,'id':'fixture-initial','checked_at':'2026-11-02T18:14:00Z','coverage':'Synthetic fixture; no real mailbox accessed.',
            'accounts':[{'id':'fixture-account','label':'Test account'}],
            'items':[{'id':'fixture-reminder','title':'研究 <script>fixture</script>','section':'life','priority':'medium','evidence_status':'needs_verification',
                'summary':'Synthetic evidence, not a confirmed task.','action':'Check the synthetic source.','source':{'account_id':'fixture-account','date':'2026-11-02','url':'https://example.test/message/one'},
                'dates':[{'label':'Due','local':'2026-11-06 23:59','timezone':'Unknown'}],'links':[],'project_refs':[]}]}
        self.write(self.snapshot)
    def tearDown(self):self.tmp.cleanup()
    def write(self,snapshot):self.source.write_text(json.dumps(snapshot,ensure_ascii=False),encoding='utf-8')
    def ingest(self):return attention.import_snapshot(self.root,self.source)
    def request(self,status='resolved',until=None):
        return {'id':'fixture-reminder','status':status,'snooze_until':until,'expected_revision':attention.projection(self.root)['decision_revision']}
    def test_replay_and_refresh_preserve_each_user_choice(self):
        self.ingest()
        for status in ['resolved','snoozed','not_relevant','active']:
            until=(datetime.now(timezone.utc)+timedelta(days=1)).isoformat() if status=='snoozed' else None
            attention.decide(self.root,self.request(status,until))
            before=(attention.private(self.root)/'decisions.json').read_bytes()
            self.assertEqual(self.ingest()['status'],'unchanged')
            self.snapshot['id']='fixture-'+status.replace('_','-');self.snapshot['items'][0]['summary']='Updated source '+status
            self.write(self.snapshot);self.ingest()
            self.assertEqual(attention.projection(self.root)['items'][0]['decision']['status'],status)
            self.assertEqual(before,(attention.private(self.root)/'decisions.json').read_bytes())
    def test_repeated_choice_zero_writes_and_stale_tabs_rejected(self):
        self.ingest();request=self.request();attention.decide(self.root,request)
        with self.assertRaisesRegex(ValueError,'changed elsewhere'):attention.decide(self.root,request)
        before=(attention.private(self.root)/'decisions.json').read_bytes()
        attention.decide(self.root,self.request())
        self.assertEqual(before,(attention.private(self.root)/'decisions.json').read_bytes())
    def test_snapshot_identity_stale_and_duplicate_sources(self):
        self.ingest();original=(attention.private(self.root)/'records.json').read_bytes()
        self.snapshot['coverage']='Changed same ID';self.write(self.snapshot)
        with self.assertRaisesRegex(ValueError,'snapshot ID changed'):self.ingest()
        self.snapshot['id']='older';self.snapshot['checked_at']='2026-11-01T18:14:00Z';self.write(self.snapshot)
        with self.assertRaisesRegex(ValueError,'stale snapshot'):self.ingest()
        self.snapshot['id']='duplicate-source';self.snapshot['checked_at']='2026-11-02T18:14:00Z';self.snapshot['items'][0]['id']='different-id';self.snapshot['items'][0]['source']['date']='changed';self.write(self.snapshot)
        with self.assertRaisesRegex(ValueError,'already indexed'):self.ingest()
        self.assertEqual(original,(attention.private(self.root)/'records.json').read_bytes())
    def test_unknown_metadata_unsafe_links_and_bad_dates_rejected(self):
        for mutation in [lambda s:s['items'][0].update(body='Full mail'),lambda s:s['items'][0]['source'].update(url='file:///private'),lambda s:s['items'][0]['links'].append({'title':'bad','url':'javascript:alert(1)'}),lambda s:s.update(checked_at='2026-11-02T18:00:00'),lambda s:s['items'].append(copy.deepcopy(s['items'][0]))]:
            s=copy.deepcopy(self.snapshot);mutation(s)
            with self.assertRaises((ValueError,KeyError,TypeError)):attention.validate(s)
    def test_empty_and_missing_items_preserve_choices(self):
        self.assertEqual(attention.projection(self.root)['items'],[])
        self.ingest();attention.decide(self.root,self.request())
        self.snapshot['id']='empty-refresh';self.snapshot['items']=[];self.write(self.snapshot);self.ingest()
        self.assertEqual(attention.projection(self.root)['items'][0]['decision']['status'],'resolved')
    def test_header_link_refresh_preserves_decisions_and_private_provenance(self):
        self.ingest();attention.decide(self.root,self.request('not_relevant'))
        before=(attention.private(self.root)/'decisions.json').read_bytes()
        self.snapshot['id']='header-refresh';self.snapshot['accounts'][0]['email']='fixture+research@example.test'
        self.snapshot['items'][0]['source'].update(rfc822_message_id='<a+b=c@example.test>',gmail_message_id='1abc',gmail_thread_id='2def',message_id_checked_at='2026-11-02T20:00:00Z',url='https://mail.google.com/mail/?authuser=fixture%2Bresearch%40example.test#search/rfc822msgid%3Aa%2Bb%3Dc%40example.test')
        self.write(self.snapshot);self.assertEqual(self.ingest()['status'],'updated');self.assertEqual(self.ingest()['status'],'unchanged')
        self.assertEqual(before,(attention.private(self.root)/'decisions.json').read_bytes())
        for mutation in [lambda s:s['accounts'][0].update(email='a@example.test&other=x'),lambda s:s['items'][0]['source'].update(rfc822_message_id='1abc'),lambda s:s['items'][0]['source'].update(rfc822_message_id='a@b\nBcc:x'),lambda s:s['items'][0]['source'].update(gmail_thread_id='web/thread'),lambda s:s['items'][0]['source'].update(raw_headers='unnecessary headers')]:
            value=copy.deepcopy(self.snapshot);mutation(value)
            with self.assertRaises(ValueError):attention.validate(value)
    def test_snooze_validation_and_identity(self):
        self.ingest()
        for value in [None,'2020-01-01T00:00:00Z','2030-01-01T00:00:00']:
            with self.assertRaises(ValueError):attention.decide(self.root,self.request('snoozed',value))
        req=self.request();req['id']='../escape'
        with self.assertRaises(ValueError):attention.decide(self.root,req)
    def test_locked_and_interrupted_write_preserves_original(self):
        self.ingest();request=self.request();folder=attention.private(self.root)
        (folder/'.lock').write_text('active writer')
        with self.assertRaisesRegex(ValueError,'writer active'):attention.decide(self.root,request)
        self.assertTrue((folder/'.lock').exists());(folder/'.lock').unlink()
        with patch('maintenance.os.replace',side_effect=OSError('simulated disk failure')):
            with self.assertRaises(OSError):attention.decide(self.root,request)
        self.assertFalse((folder/'decisions.json').exists());self.assertFalse((folder/'.lock').exists())
        self.assertEqual(attention.decide(self.root,request)['items'][0]['decision']['status'],'resolved')
    def test_import_scope_and_confirmed_crosslinks(self):
        public=self.root/'public.json';public.write_bytes(self.source.read_bytes())
        with self.assertRaisesRegex(ValueError,'ignored'):attention.import_snapshot(self.root,public)
        self.snapshot['items'][0]['project_refs']=['fixture-project'];self.write(self.snapshot)
        with self.assertRaisesRegex(ValueError,'unconfirmed project'):self.ingest()
        project=self.root/'library/projects/fixture-project.json';project.parent.mkdir(parents=True);project.write_text('{}')
        self.ingest();self.assertEqual(attention.projection(self.root)['items'][0]['project_refs'],['fixture-project'])
    def test_http_security_and_decision_roundtrip(self):
        self.ingest()
        with patch.object(serve_library,'ROOT',self.root):
            server=serve_library.LoopbackServer(('127.0.0.1',0),serve_library.Handler)
            worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
            def call(method,path,body=None,headers=None):
                conn=HTTPConnection('127.0.0.1',server.server_port);conn.request(method,path,body=body,headers=headers or {});response=conn.getresponse();data=response.read();status=response.status;conn.close();return status,data
            try:
                with self.assertRaises(OSError):
                    serve_library.LoopbackServer(('127.0.0.1',server.server_port),serve_library.Handler)
                status,raw=call('GET','/api/attention');self.assertEqual(status,200);data=json.loads(raw)
                headers={'Origin':f'http://127.0.0.1:{server.server_port}','Content-Type':'application/json','X-Hikari-Token':data['action_token']}
                self.assertEqual(call('POST','/api/attention/decision',json.dumps(self.request()),headers)[0],200)
                self.assertEqual(json.loads(call('GET','/api/attention')[1])['items'][0]['decision']['status'],'resolved')
                for method,path,body,h,code in [
                    ('GET','/.local/attention/records.json',None,{},404),('GET','/../.git/config',None,{},404),('GET','/api/attention',None,{'Host':'evil.test'},403),
                    ('GET','/api/attention',None,{'Origin':'https://evil.test'},403),('GET','/api/attention',None,{'Sec-Fetch-Site':'cross-site'},403),
                    ('POST','/api/attention/decision','{}',{**headers,'Origin':'https://evil.test'},403),('POST','/api/attention/decision','{}',{**headers,'X-Hikari-Token':'bad'},403),
                    ('POST','/api/attention/decision','{}',{**headers,'Content-Type':'text/plain'},415),('POST','/api/attention/decision','{}',headers,409),
                    ('POST','/api/library','{}',headers,501)]:
                    self.assertEqual(call(method,path,body,h)[0],code)
            finally:server.shutdown();server.server_close();worker.join()

if __name__=='__main__':unittest.main()
