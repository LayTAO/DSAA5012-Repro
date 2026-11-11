#!/usr/bin/env python3
"""Generate an isolated timing-only variant of pinned RUC+LB code."""
from pathlib import Path
import os,subprocess,json,hashlib
from benchmark import ROOT,digest
if os.environ.get('TMPDIR')!=str(ROOT/'.runtime/tmp'):raise RuntimeError('Guard required')
out=ROOT/'build/supplement-20261110';out.mkdir(parents=True,exist_ok=True)
original=ROOT/'external/hyper-k-core/src/Algorithm_withInfo/Final_nbrCoreDecomposition.cpp'
s=original.read_text();replacements=[
 ('#include "../Hypergraph.h"','#include "Hypergraph.h"\n#include "supplement_timer.h"'),
 ('#include "NbrCD.h"','#include "Algorithm_withInfo/NbrCD.h"'),
 ('auto init_start =','auto & timing = supplement::timer();\n    auto init_start ='),
 ('auto time_start = std::chrono::high_resolution_clock::now();','auto time_start = timing.begin(0);'),
 ('compute_time += std::chrono::duration<double>(\n                    std::chrono::high_resolution_clock::now() - time_start).count();','timing.end(0,time_start);'),
 ('time_start = std::chrono::high_resolution_clock::now();','time_start = timing.begin(1);'),
 ('decide_time += std::chrono::duration<double>(\n                        std::chrono::high_resolution_clock::now() - time_start).count();','timing.end(1,time_start);'),
 ('std::cout << "decide_time: " << decide_time','timing.print();\n    if(timing.migrations) throw std::runtime_error("Per-region timer migrated");\n    decide_time=timing.seconds(1);compute_time=timing.seconds(0);\n    std::cout << "decide_time: " << decide_time')]
for a,b in replacements:
 if s.count(a)!=1:raise RuntimeError('Unexpected pinned source: '+a)
 s=s.replace(a,b)
source=out/'Final_tsc.cpp';source.write_text(s)
flags=['g++','-O3','-DNDEBUG','-std=c++20','-fopenmp','-fstack-protector-strong','-Iexternal/hyper-k-core/src','-Isrc/drivers']
info=[p for p in (ROOT/'external/hyper-k-core/src/Algorithm_withInfo').glob('*.cpp') if p.name not in ['Final_nbrCoreDecomposition.cpp','fullNbrCoreDecomposition.cpp']]
cmd=flags+['src/drivers/sigmod_extended.cpp','external/hyper-k-core/src/Hypergraph.cpp']+[str(p) for p in (ROOT/'external/hyper-k-core/src/Algorithm').glob('*.cpp')]+[str(p) for p in info]+['build/extended/generated/suc_counters.cpp',str(source),'-o',str(out/'sigmod_tsc')]
subprocess.run(cmd,cwd=ROOT,check=True)
subprocess.run(flags+['src/drivers/timer_calibration.cpp','-o',str(out/'timer_calibration')],cwd=ROOT,check=True)
subprocess.run(flags+['src/drivers/profile_initialization.cpp','external/hyper-k-core/src/Hypergraph.cpp','-o',str(out/'profile_initialization')],cwd=ROOT,check=True)
record={'original_sha256':digest(original),'generated_sha256':digest(source),'binary_sha256':digest(out/'sigmod_tsc'),'command':cmd,'changes':'Only per-region instrumentation replaced; algorithm, vertex order and counter logic retained. Pinned, fenced RDTSCP; calibrated to CLOCK_MONOTONIC_RAW; full and Bernoulli 1/32 sampled timing; raw and empty-pair-adjusted estimates both preserved.','manual_reference':'https://cdrdv2-public.intel.com/825743/325462-sdm-vol-1-2abcd-3abcd-4.pdf','zero_timed_experiment_changes':True}
(ROOT/'results/supplement-20261110/timer-adaptation.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record),flush=True)
