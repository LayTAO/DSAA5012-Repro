import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from summarize_full_results import summarize


class FullSummaryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.out=self.root/'results/full-synthetic-small001';self.out.mkdir(parents=True)
        (self.root/'configs').mkdir()
        self.write(self.root/'configs/full-datasets.json',{})
        self.write(self.root/'configs/paper-digitized.json',{'panels':[]})
        self.dataset='POW-S-approx'
        self.write(self.out/'metadata.json',{'datasets':{self.dataset:{'processed':{'sha256':'input-hash'}}},'binary_sha256':{'build/drivers/sigmod':'binary-hash'}})
        self.write(self.out/'reference-POW-S-approx.json',{'status':'ok','dataset':self.dataset,'core_sha256':'cores'})
        self.write(self.out/'core-POW-S-approx-0-validation.json',self.row(0,True))
    def tearDown(self):self.temp.cleanup()
    def write(self,path,value):path.write_text(json.dumps(value))
    def row(self,repeat,export=False):
        return {'label':'core-POW-S-approx-0-'+('validation' if repeat==0 else 'r'+str(repeat)),
                'dataset':self.dataset,'argument':'0','repeat':repeat,'status':'ok','input_sha256':'input-hash',
                'binary_sha256':'binary-hash','command':['taskset','-c','0','${PROJECT_ROOT}/build/drivers/sigmod'],
                'exported_cores':export,'core_sha256':'cores' if export else None,'reported_total_s':1.0+repeat}
    def group(self):return next(g for g in summarize(self.root)['groups'] if (g['dataset'],g['family'],g['argument'])==(self.dataset,'core','0'))
    def test_no_mean_until_all_repeats_validate(self):
        for repeat in [1,2]:self.write(self.out/('core-POW-S-approx-0-r'+str(repeat)+'.json'),self.row(repeat))
        self.assertEqual(self.group()['status'],'pending');self.assertNotIn('reported_total_s',self.group())
        self.write(self.out/'core-POW-S-approx-0-r3.json',self.row(3))
        self.assertEqual(self.group()['status'],'complete');self.assertEqual(self.group()['reported_total_s']['mean'],3.0)
    def test_failed_repeat_is_not_dropped_from_mean(self):
        for repeat in [1,2,3]:
            row=self.row(repeat)
            if repeat==2:row['status']='timeout'
            self.write(self.out/('core-POW-S-approx-0-r'+str(repeat)+'.json'),row)
        self.assertEqual(self.group()['status'],'completed_with_failures');self.assertNotIn('reported_total_s',self.group())
    def test_corrupt_binary_or_core_is_not_accepted(self):
        for repeat in [1,2,3]:self.write(self.out/('core-POW-S-approx-0-r'+str(repeat)+'.json'),self.row(repeat))
        bad=self.row(0,True);bad['core_sha256']='different'
        self.write(self.out/'core-POW-S-approx-0-validation.json',bad)
        self.assertEqual(self.group()['status'],'unvalidated')
        bad=self.row(1);bad['binary_sha256']='wrong-binary';self.write(self.out/'core-POW-S-approx-0-r1.json',bad)
        with self.assertRaisesRegex(RuntimeError,'binary changed'):self.group()

if __name__=='__main__':unittest.main()
