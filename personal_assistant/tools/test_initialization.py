import tempfile
import unittest
from pathlib import Path
from library import ROOT, load_library
from sample_data import prepare

class InitializationTests(unittest.TestCase):
    def setUp(self):
        (ROOT/'.local/test-temp').mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'.local/test-temp');self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def test_empty_start_and_no_overwrite(self):
        data=prepare(self.root,demo=False)
        self.assertEqual(data['projects'],[]);self.assertEqual(data['papers'],[])
        old={p:p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        with self.assertRaisesRegex(ValueError,'already exists'):prepare(self.root,demo=True)
        self.assertEqual(old,{p:p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
    def test_demo_contains_only_synthetic_records_and_no_schedule(self):
        data=prepare(self.root)
        self.assertEqual(len(data['projects']),2);self.assertEqual(len(data['papers']),3)
        self.assertTrue(all('synthetic' in p['coverage'].lower() for p in data['projects']))
        self.assertFalse((self.root/'library/maintenance/schedule.json').exists())
        self.assertEqual(load_library(self.root)['maintenance']['submissions'],0)

if __name__=='__main__':unittest.main()
