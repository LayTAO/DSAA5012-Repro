#!/usr/bin/env python3
"""Generate documented seed/counter adaptations without editing upstream checkouts."""
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main():
    out=ROOT/'build/extended/generated';out.mkdir(parents=True,exist_ok=True)
    source=ROOT/'external/hyper-k-core/src/Algorithm_withInfo/fullNbrCoreDecomposition.cpp'
    original=source.read_text();text=original
    replacements=[
        ('#include "../Hypergraph.h"','#include "Hypergraph.h"'),
        ('#include "NbrCD.h"','#include "Algorithm_withInfo/NbrCD.h"'),
        ('++iter;','++iter;\n        std::size_t observed_computed=0, observed_changed=0;'),
        ('auto compute_start = std::chrono::high_resolution_clock::now();','++observed_computed;\n            const auto observed_old_core=currentNodeCore;\n            auto compute_start = std::chrono::high_resolution_clock::now();'),
        ('std::chrono::high_resolution_clock::now() - decide_start).count();\n        }\n    }','std::chrono::high_resolution_clock::now() - decide_start).count();\n            if(currentNodeCore<observed_old_core) ++observed_changed;\n        }\n        std::cout << iter << "," << observed_computed << "," << observed_changed << std::endl;\n    }')]
    for before,after in replacements:
        if text.count(before)!=1:raise RuntimeError('Unexpected upstream SUC source')
        text=text.replace(before,after)
    (out/'suc_counters.cpp').write_text(text)
    generator=ROOT/'external/hyper-k-core/src/graphTool/generateGraph.cpp'
    gen=generator.read_text().replace('#include "../Hypergraph.h"','#include "Hypergraph.h"').replace('#include "graphTool.h"','#include "graphTool/graphTool.h"')
    if gen.count('std::random_device rd;')!=4:raise RuntimeError('Unexpected upstream generator')
    gen='#include <cstdint>\nextern std::uint32_t repro_seed;\n'+gen.replace('std::random_device rd;','auto rd=[](){return repro_seed;};')
    (out/'seeded_generator.cpp').write_text(gen)
    record={'suc_original_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
            'suc_generated_sha256':hashlib.sha256(text.encode()).hexdigest(),
            'generator_original_sha256':hashlib.sha256(generator.read_bytes()).hexdigest(),
            'generator_generated_sha256':hashlib.sha256(gen.encode()).hexdigest(),
            'changes':['Add observational per-iteration computed/changed counters to SUC info implementation; no algorithm update changes.',
                       'Replace random_device seed draws in a generated copy with explicit repro_seed; retain original neighbor power-law generator.'],
            'claim':'Synthetic results are same-scale approximations, not identical paper inputs.'}
    (ROOT/'results/setup/extended-adaptations.json').write_text(json.dumps(record,indent=2)+'\n')

if __name__=='__main__':main()
