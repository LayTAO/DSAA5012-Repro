#!/usr/bin/env python3
"""Extract Figures 7/9/10/11 from the paper's vector graphics, keeping provenance."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import pdfplumber

ORDER=['HI','CO','GE','DB','DF','THS','AM','TAS','AMZ','SOA','POW-S','POW-L']
def rounded(value):return float(format(value,'.3g'))
def ticks(page,left,lo,hi,minwidth,maxwidth):
    return sorted({round(l['top'],5) for l in page.lines if abs(l['x1']-left)<.002 and minwidth<l['width']<maxwidth and lo<l['top']<hi and l['height']<.001},reverse=True)

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('pdf',type=Path);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    result={'doi':'10.1145/3709656','source_pdf_sha256':hashlib.sha256(args.pdf.read_bytes()).hexdigest(),
            'kind':'published_vector_graphic_estimates_and_explicit_text_labels',
            'precision_note':'Vector-derived values have three significant figures, not original experimental observations. Sparse polylines retain PDF simplification.',
            'panels':[]}
    with pdfplumber.open(args.pdf) as pdf:
        page=pdf.pages[20];values=[]
        for dataset,left,last in [('DF',68.199,33),('THS',167.302,27),('TAS',266.405,32),('AMZ',365.508,29)]:
            ys=ticks(page,left,220,275,.85,.86)
            assert len(ys)==(6 if dataset=='TAS' else 7)
            step=statistics.mean(a-b for a,b in zip(ys,ys[1:]))
            curves=[c for c in page.curves if left<c['x0']<left+4 and c['width']>60 and 225<c['top']<240]
            assert len(curves)==4
            for c in curves:
                dash=c.get('dash');pattern=tuple(dash[0]) if dash else ()
                method={():'2',(74,32):'0',(128,32,20,32):'1',(20,33):'5'}[pattern]
                points=[{'iteration':round(1+(x-c['x0'])/(c['x1']-c['x0'])*(last-1)),
                         'computed_estimate':rounded(10**((ys[0]-y)/step)),'x_pt':x,'top_pt':y} for x,y in c['pts']]
                assert all(1<=p['iteration']<=last for p in points)
                values.append({'dataset':dataset,'argument':method,'points':points,'bottom_tick_top_pt':ys[0],'points_per_decade':step})
        result['panels'].append({'figure':7,'pdf_page':21,'unit':'unfiltered vertices','values':values})
        ys=ticks(page,270.54414,340,393,.93,.95);assert len(ys)==5
        step=statistics.mean(a-b for a,b in zip(ys,ys[1:]));values=[]
        bars=sorted([r for r in page.rects if 270<r['x0']<440 and 340<r['top']<392 and 6.5<r['width']<6.6 and r['fill']],key=lambda r:r['x0'])
        assert len(bars)==12
        for dataset,bar in zip(ORDER,bars):values.append({'dataset':dataset,'estimate':rounded((ys[0]-bar['top'])/step*.05),'bar_top_pt':bar['top']})
        result['panels'].append({'figure':9,'pdf_page':21,'unit':'fraction','values':values,
            'text_claims_separate':{'average_fraction':.045,'maximum':{'dataset':'AM','fraction':.108},'minimum':{'dataset':'SOA','fraction':.00002}},
            'inconsistency':'Published bars disagree with Exp-7 text, including a TAS bar around 0.217. Both sources are retained separately.'})
        values=[]
        for dataset,left,increment in [('AMZ',70.191,100),('TAS',169.294,2),('SOA',268.397,500),('AM',367.5,5)]:
            ys=ticks(page,left,450,500,.78,.79);assert len(ys)>=5
            step=statistics.mean(a-b for a,b in zip(ys,ys[1:]))
            curves=[c for c in page.curves if left<c['x0']<left+10 and c['x1']<left+72 and 450<c['top']<500 and len(c['pts'])==5]
            assert len(curves)==1
            for fraction,(x,y) in zip([.2,.4,.6,.8,1.0],curves[0]['pts']):
                values.append({'dataset':dataset,'fraction':fraction,'estimate_s':rounded((ys[0]-y)/step*increment),'x_pt':x,'top_pt':y})
        result['panels'].append({'figure':10,'pdf_page':21,'unit':'seconds','values':values})
        page=pdf.pages[21];values=[]
        labels={'AMZ':[1,1.8,3.6,6.9,13.5,23.7,35.9],'SOA':[1,1.7,3.4,6.7,13.4,25.7,37.2],'POW-L':[1,1.6,3.6,6.8,10.8,18.2,35.6]}
        for dataset,left,exponent in [('AMZ',71.093,2),('SOA',199.777,2),('POW-L',328.485,3)]:
            ys=ticks(page,left,115,168,.87,.89)
            if dataset=='AMZ':
                assert len(ys)==1
                minor=ticks(page,left,115,ys[0]-.001,.49,.51)
                step=(ys[0]-minor[0])/__import__('math').log10(2)
            else:
                assert len(ys)==2,(dataset,ys)
                step=ys[0]-ys[1]
            bars=sorted([r for r in page.rects if left<r['x0']<left+90 and 115<r['top']<168 and 9<r['width']<10 and r['height']>1000 and r['stroke']],key=lambda r:r['x0'])
            assert len(bars)==7
            for threads,bar,speedup in zip([1,2,4,8,16,32,64],bars,labels[dataset]):
                values.append({'dataset':dataset,'threads':threads,'estimate_s':rounded(10**(exponent+(ys[0]-bar['top'])/step)),
                    'labeled_speedup':speedup,'bar_top_pt':bar['top']})
        result['panels'].append({'figure':11,'pdf_page':22,'unit':'seconds and speedup','values':values})
    result['table5']={'pdf_page':23,'unit_note':'Published rounded values converted to seconds; GB base unspecified.',
        'values':[{'dataset':'POW-S','init_s':600,'execution_s':78,'total_s':720,'memory_GB':10.9,'baseline_status':'OOM'},
                  {'dataset':'POW-L','init_s':18000,'execution_s':1920,'total_s':19800,'memory_GB':227,'baseline_status':'OOM'}]}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({str(p['figure']):len(p['values']) for p in result['panels']}))

if __name__=='__main__':main()
