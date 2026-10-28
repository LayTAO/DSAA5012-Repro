#!/usr/bin/env python3
"""Estimate Figures 4–6 and 8 from PDF vector bars and log-axis ticks (not raw author data)."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import pdfplumber

DATASETS = ['HI', 'CO', 'GE', 'DB', 'DF', 'THS', 'AM', 'TAS', 'AMZ', 'SOA']
METHODS = ['vldb_OPTIV', 'sigmod_4', 'sigmod_3', 'sigmod_5', 'sigmod_0']
PANELS = [(4, 77.0029, 174.7074, -1, 'seconds'),
          (5, 205.6899, 303.3914, -1, 'seconds'),
          (6, 334.2780, 432.0744, 1, 'MB as labeled in paper')]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pdf', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = {'doi': '10.1145/3709656', 'source_pdf_sha256': hashlib.sha256(args.pdf.read_bytes()).hexdigest(),
              'pdf_page': 21, 'kind': 'estimates_from_published_vector_graphics',
              'precision_note': 'Values are rounded to two significant figures. They are not author-supplied raw observations.',
              'method': 'Deduplicate stroked bar rectangles; sort by x; use the visually checked legend/group order; calibrate log10 y from major tick coordinates; mask OOM/OOT placeholders.',
              'panels': []}
    with pdfplumber.open(args.pdf) as document:
        page = document.pages[20]
        for figure, left, right, bottom_exponent, unit in PANELS:
            ticks = sorted({round(line['top'], 5) for line in page.lines
                            if abs(line['x1']-left) < .01 and .8 < line['width'] < .95
                            and 100 < line['top'] < 155 and line['height'] < .001}, reverse=True)
            expected = 5 if figure == 6 else 6
            if len(ticks) != expected:
                raise ValueError('Unexpected major ticks in Figure ' + str(figure))
            step = statistics.mean(a-b for a,b in zip(ticks, ticks[1:]))
            if max(abs((a-b)-step) for a,b in zip(ticks,ticks[1:])) > .001:
                raise ValueError('Tick spacing is not logarithmically uniform')
            bars = [r for r in page.rects if r['stroke'] and left<r['x0']<right
                    and .8<r['width']<2 and r['height']>1000 and r['top']<160]
            bars.sort(key=lambda r:r['x0'])
            if len(bars) != 50:
                raise ValueError('Expected 10 datasets x 5 bars in Figure ' + str(figure))
            values = []
            for index, rect in enumerate(bars):
                dataset, method = DATASETS[index//5], METHODS[index%5]
                status = 'ok'
                if dataset == 'SOA' and method in ['vldb_OPTIV','sigmod_4']:
                    status = 'OOM'
                if dataset == 'TAS' and method == 'sigmod_5' and figure in [4,5]:
                    status = 'OOT'
                estimate = 10 ** (bottom_exponent + (ticks[0]-rect['top'])/step)
                if status == 'ok' and rect['top'] < 102.45:
                    raise ValueError('Unclassified out-of-range bar')
                values.append({'dataset':dataset, 'method':method, 'status':status,
                               'estimate':float(format(estimate,'.2g')) if status=='ok' else None,
                               'bar_left_pt':rect['x0'], 'bar_top_pt':rect['top']})
            result['panels'].append({'figure':figure,'unit':unit,
                                     'major_ticks_top_pt':ticks,'bottom_tick_log10':bottom_exponent,
                                     'points_per_decade':step,'values':values})
        # Figure 8: four methods, twelve datasets, a separately calibrated axis.
        ticks = sorted({round(line['top'],5) for line in page.lines
                        if abs(line['x1']-69.3689)<.01 and .9<line['width']<.98
                        and 340<line['top']<390 and line['height']<.001}, reverse=True)
        if len(ticks)!=6:
            raise ValueError('Expected six major ticks in Figure 8')
        step=statistics.mean(a-b for a,b in zip(ticks,ticks[1:]))
        bars=sorted([r for r in page.rects if r['stroke'] and 69.3689<r['x0']<236.156
                     and 2<r['width']<3 and r['height']>1000 and 320<r['top']<400],key=lambda r:r['x0'])
        if len(bars)!=48:
            raise ValueError('Expected 48 bars in Figure 8')
        methods=['vldb_OPTIV','sigmod_2','sigmod_1','sigmod_0']
        datasets=DATASETS+['POW-S','POW-L']
        values=[]
        for index,rect in enumerate(bars):
            dataset,method=datasets[index//4],methods[index%4]
            status='ok'
            if method=='vldb_OPTIV' and dataset in ['SOA','POW-S','POW-L']:
                status='OOM'
            if method=='sigmod_2' and dataset=='POW-L':
                status='OOT'
            estimate=10**(-1+(ticks[0]-rect['top'])/step)
            if status=='ok' and rect['top']<340.76:
                raise ValueError('Unclassified out-of-range bar in Figure 8')
            values.append({'dataset':dataset,'method':method,'status':status,
                           'estimate':float(format(estimate,'.2g')) if status=='ok' else None,
                           'bar_left_pt':rect['x0'],'bar_top_pt':rect['top']})
        result['panels'].append({'figure':8,'unit':'seconds','major_ticks_top_pt':ticks,
                                 'bottom_tick_log10':-1,'points_per_decade':step,'values':values})
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    for panel in result['panels']:
        print('Figure',panel['figure'],[(x['method'],x['estimate']) for x in panel['values'] if x['dataset']=='HI'])


if __name__ == '__main__':
    main()
