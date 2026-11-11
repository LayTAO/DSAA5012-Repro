"""Regression tests for prospective resource gates and comparison cohorts."""
import copy
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import supplement_load_policy as policy
from audit_supplement_v2 import policy_summary

def sample(t,active=True):
    cpu={f'cpu{k}':{'total':int(t*100),'idle':int(t*100)} for k in list(range(32))+list(range(64,96))}
    cpu['cpu0']['idle']=0
    return {'monotonic_s':t,'cpu':cpu,'load':[11,11,11],'memavailable_kib':900*1024**2,
            'cpu_pressure_some_avg10_pct':0,'memory_pressure_some_avg10_pct':0,
            'io_pressure_full_avg10_pct':0,
            'algorithm_task':{'pid':1,'start_ticks':5,'cpu_ticks':int(t*os.sysconf('SC_CLK_TCK'))} if active else None}

class ResourcePolicyTests(unittest.TestCase):
    def test_global_load_above_eight_can_pass_with_idle_local_cpu(self):
        a,b=sample(0,False),sample(5,False);b['cpu']['cpu0']['idle']=500
        self.assertTrue(policy.gate_decision(a,b)['accepted'])
        b['load'][0]=172
        self.assertIn('global_load',policy.gate_decision(a,b)['reasons'])

    def test_busy_selected_cpu_is_rejected(self):
        self.assertIn('cpu0_busy',policy.gate_decision(sample(0),sample(5))['reasons'])

    def test_pressure_rejects_otherwise_idle_machine(self):
        a,b=sample(0,False),sample(5,False);b['cpu']['cpu0']['idle']=500
        for key,threshold in [('cpu_pressure_some_avg10_pct',5),('memory_pressure_some_avg10_pct',1),('io_pressure_full_avg10_pct',5)]:
            q=copy.deepcopy(b);q[key]=threshold+1
            self.assertIn(key,policy.gate_decision(a,q)['reasons'])

    def test_own_work_and_one_tick_terminal_interval_are_not_contention(self):
        a,b,c=sample(0),sample(5),sample(10);end=sample(10.001,False)
        end['cpu']['cpu64']['total']+=1
        self.assertTrue(policy.assess(sample(0,False),[a,b,c,end],10.001)['load_control_pass'])

    def test_sibling_and_competing_cpu_activity_are_rejected(self):
        a,b,c=sample(0),sample(5),sample(10)
        sibling=copy.deepcopy(c);sibling['cpu']['cpu64']['idle']-=100
        self.assertIn('sibling_busy_or_unobserved',policy.assess(a,[b,sibling],10)['load_control_reasons'])
        other=copy.deepcopy(c);other['algorithm_task']['cpu_ticks']-=int(2.5*os.sysconf('SC_CLK_TCK'))
        self.assertIn('other_cpu0_activity',policy.assess(a,[b,other],10)['load_control_reasons'])

    def test_incomplete_cpu_observation_is_not_qualified(self):
        self.assertIn('cpu0_observation_incomplete',policy.assess(sample(0,False),[sample(5,False)],5)['load_control_reasons'])

    def test_mixed_cohorts_are_descriptive_and_failed_attempts_not_dropped(self):
        rows=[dict(repeat=i,status='ok',historical_core_match=True,load_control_pass=True,label=str(i),reported_execution_s=i) for i in range(1,4)]
        self.assertTrue(policy_summary(rows)['load_control_pass'])
        rows[2]['load_policy_id']=policy.POLICY['id'];q=policy_summary(rows)
        self.assertTrue(q['mixed_load_policies']);self.assertFalse(q['load_control_pass'])
        self.assertEqual(q['reported_execution_s']['mean'],2)
        rows[1]['status']='timeout'
        self.assertNotIn('reported_execution_s',policy_summary(rows))

if __name__=='__main__':unittest.main()
