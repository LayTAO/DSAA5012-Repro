#!/usr/bin/env python3
"""Render scientific comparison figures from audited, bounded full-paper records."""
import argparse
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ORDER=['HI','CO','GE','DB','DF','THS','AM','TAS','AMZ','SOA','POW-S-approx','POW-L-approx']
LABELS={'OPTIV':'LocalCore-OPT','4':'HyperCD','3':'HyperCD+','5':'HyperCD++','0':'HyperCD*','1':'RUC','2':'LB'}
COLORS={'OPTIV':'#bb6418','4':'#8a929c','3':'#4476a3','5':'#9573aa','0':'#008474','1':'#4476a3','2':'#b49b4b'}

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('summary',type=Path);parser.add_argument('--input',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    report=json.loads(args.summary.read_text());out=args.output;out.mkdir(parents=True,exist_ok=True)
    paper=json.loads((args.input/'configs/paper-extended-reference.json').read_text());panels={p['figure']:p for p in paper['panels']}
    groups={(r['dataset'],r['family'],r['argument']):r for r in report['groups']}
    terminal=report['coverage']['all_trials_recorded']
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.spines.top':False,'axes.spines.right':False})
    def metric(d,f,a,m):
        row=groups.get((d,f,a),{})
        return row.get(m,{}).get('mean',np.nan) if row.get('status')=='complete' else np.nan
    def finish(fig,name,title,note):
        if not report['coverage']['all_trials_recorded']:title+=' (in progress)'
        fig.suptitle(title,x=.04,ha='left',fontsize=16,weight='bold')
        fig.text(.04,.025,note,fontsize=8.5,color='#475569')
        fig.subplots_adjust(left=.07,right=.98,top=.86,bottom=.16,wspace=.30,hspace=.42)
        for ext in ['png','svg']:fig.savefig(out/(name+'.'+ext),dpi=180,facecolor='white')
        plt.close(fig)
    for number,field,unit in [(4,'reported_total_s','Total algorithm time (s)'),(5,'reported_execution_s','Execution time (s)'),(6,'peak_rss_kib','Peak RSS (measured MiB; paper MB)'),(8,'reported_execution_s','Execution time (s)')]:
        methods=['OPTIV','4','3','5','0'] if number!=8 else ['OPTIV','2','1','0']
        datasets=ORDER if number==8 else ORDER[:10];x=np.arange(len(datasets));width=.78/len(methods)
        lookup={(p['dataset'],p['argument']):p for p in report['paper_comparisons'] if p['figure']==number}
        fig,axes=plt.subplots(2,1,figsize=(14,7.2),sharex=True,sharey=True)
        for ri,ax in enumerate(axes):
            for j,a in enumerate(methods):
                points=[lookup.get((d,a),{}).get('paper_estimate') if ri==0 else metric(d,'core',a,field)/(1024 if number==6 else 1) for d in datasets]
                points=[v if v is not None and v>0 else np.nan for v in points]
                positions=x+(j-(len(methods)-1)/2)*width
                ax.bar(positions,points,width,color=COLORS[a],label=LABELS[a])
                if ri:
                    for pos,d,v in zip(positions,datasets,points):
                        if np.isfinite(v):
                            item=groups[(d,'core',a)][field];div=1024 if number==6 else 1
                            ax.errorbar(pos,v,yerr=[[v-item['min']/div],[item['max']/div-v]],fmt='none',ecolor='#334155',capsize=1.2,elinewidth=.7)
                        elif terminal:
                            counts=groups.get((d,'core',a),{}).get('trial_status_counts',{})
                            code='ML' if 'memory_limit' in counts else ('TO' if 'timeout' in counts else 'FAIL')
                            ax.text(pos,.025,code,transform=ax.get_xaxis_transform(),rotation=90,ha='center',va='bottom',fontsize=6,color='#7f1d1d')
            ax.set_yscale('log');ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
            ax.set_ylabel(('Paper estimates\n' if ri==0 else 'Validated mean of 3\n')+unit)
        axes[-1].set_xticks(x,[d.replace('-approx','~') for d in datasets],rotation=25)
        handles,labels=axes[0].get_legend_handles_labels();fig.legend(handles,labels,loc='upper center',bbox_to_anchor=(.53,.94),ncol=len(methods),frameon=False)
        finish(fig,'figure-'+str(number),'Figure '+str(number)+': paper and reproduction',
               ('ML = address-space limit; TO = timeout in at least one repeat; FAIL = other failure. No successful-only means. ' if terminal else 'Missing bars are pending/failed/unvalidated, not zero. ')+
               '~ = synthetic approximation.\nPublished data versions, hardware, clock boundaries and memory limits differ; paper values are graph estimates.')
    fig,axes=plt.subplots(2,4,figsize=(15,7.3))
    for col,d in enumerate(['DF','THS','TAS','AMZ']):
        for a in ['2','1','0','5']:
            points=next(p['points'] for p in panels[7]['values'] if p['dataset']==d and p['argument']==a)
            axes[0,col].plot([p['iteration'] for p in points],[p['computed_estimate'] for p in points],color=COLORS[a],label=LABELS[a],linewidth=1.4)
            group=groups.get((d,'stats',a),{})
            if group.get('status')=='complete':
                trace=group['iteration_trace']
                axes[1,col].plot([p['iteration'] for p in trace],[p['computed'] if p['computed']>0 else np.nan for p in trace],color=COLORS[a],label=LABELS[a],linewidth=1.4)
        axes[0,col].set_title(d)
        if not axes[1,col].lines:
            axes[1,col].text(.5,.5,'Measured results pending',ha='center',va='center',transform=axes[1,col].transAxes,color='#64748b')
            axes[1,col].set_xlim(axes[0,col].get_xlim())
        for row in range(2):
            axes[row,col].set_yscale('log');axes[row,col].grid(alpha=.2);axes[row,col].set_xlabel('Iteration')
        if col==0:
            axes[0,col].set_ylabel('Paper: unfiltered vertices');axes[1,col].set_ylabel('Measured: unfiltered vertices')
    handles,labels=axes[0,0].get_legend_handles_labels();fig.legend(handles,labels,loc='upper center',bbox_to_anchor=(.53,.94),ncol=4,frameon=False)
    finish(fig,'figure-7','Figure 7: filtering by iteration','Paper polylines are digitized estimates. Reproduction uses observed counters; zero computations are omitted on the log axis.\nThe SUC information implementation adds observation counters only; these timings are not used for Figures 4-6/8.')
    fig,ax=plt.subplots(figsize=(14,4.9));x=np.arange(len(ORDER))
    estimates={v['dataset']:v['estimate'] for v in panels[9]['values']}
    ax.bar(x-.18,[estimates[d.replace('-approx','')] for d in ORDER],.36,label='Paper figure estimate',color='#94a3b8')
    ax.bar(x+.18,[metric(d,'stats','0','ruc_fraction_of_execution') for d in ORDER],.36,label='Measured mean of 3',color=COLORS['0'])
    if terminal:
        for i,d in enumerate(ORDER):
            if not np.isfinite(metric(d,'stats','0','ruc_fraction_of_execution')):
                ax.text(i+.18,.015,'TO',transform=ax.get_xaxis_transform(),ha='center',va='bottom',fontsize=8,color='#7f1d1d')
    ax.set_xticks(x,[d.replace('-approx','~') for d in ORDER],rotation=25);ax.set_ylabel('RUC decision time / execution time');ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True);ax.legend(frameon=False)
    finish(fig,'figure-9','Figure 9: RUC filtering cost','The paper figure and Exp-7 prose disagree. Bars use the figure; prose claims (mean 4.5%, max 10.8%) remain separate.\n'+('TO: POW-L statistics timed out in all 3 attempts; the ratio is unmeasured. Synthetic inputs are approximate.' if terminal else 'Blank measured bars are pending/failed/unvalidated. Synthetic inputs are approximate.'))
    fig,axes=plt.subplots(1,4,figsize=(15,4.9))
    for ax,d in zip(axes,['AMZ','TAS','SOA','AM']):
        ref=[v for v in panels[10]['values'] if v['dataset']==d]
        ax.plot([v['fraction'] for v in ref],[v['estimate_s'] for v in ref],'s--',color='#94a3b8',label='Paper estimate')
        values=[metric(d+'-E'+f,'scale','0','reported_total_s') for f in ['0p2','0p4','0p6','0p8','1p0']]
        ax.plot([.2,.4,.6,.8,1],values,'o-',color=COLORS['0'],label='Measured mean of 3')
        ax.set_title(d);ax.set_xlabel('Fraction of hyperedges');ax.set_xticks([.2,.4,.6,.8,1]);ax.grid(alpha=.2)
    axes[0].set_ylabel('Total algorithm time (s)');axes[-1].legend(frameon=False,fontsize=8)
    finish(fig,'figure-10','Figure 10: hypergraph size','Original author sampling with seed 5012, followed by author preprocessing; actual sample counts are saved in manifests.\nDifferent public dataset versions and hardware prevent identical absolute runtime comparisons.')
    fig,axes=plt.subplots(2,3,figsize=(13,7.5));threads=[1,2,4,8,16,32,64]
    for col,d in enumerate(['AMZ','SOA','POW-L-approx']):
        ref=[v for v in panels[11]['values'] if v['dataset']==d.replace('-approx','')]
        measured=[metric(d,'parallel',str(t),'reported_total_s') for t in threads]
        axes[0,col].plot(threads,[v['estimate_s'] for v in ref],'s--',color='#94a3b8',label='Paper estimate')
        axes[0,col].plot(threads,measured,'o-',color=COLORS['0'],label='Measured mean of 3')
        axes[1,col].plot(threads,[v['labeled_speedup'] for v in ref],'s--',color='#94a3b8',label='Paper labeled speedup')
        axes[1,col].plot(threads,[measured[0]/v if np.isfinite(v) else np.nan for v in measured],'o-',color=COLORS['0'],label='Measured speedup')
        if terminal and not np.isfinite(measured[0]):
            axes[1,col].text(.05,.92,'Measured speedup unavailable:\n1-thread runs timed out (3/3).',transform=axes[1,col].transAxes,va='top',fontsize=8,color='#7f1d1d')
        axes[0,col].set_title(d);axes[0,col].set_yscale('log')
        for row in range(2):
            axes[row,col].set_xscale('log',base=2);axes[row,col].set_xticks(threads,threads);axes[row,col].set_xlabel('CPU threads');axes[row,col].grid(alpha=.2)
    axes[0,0].set_ylabel('Total algorithm time (s)');axes[1,0].set_ylabel('Speedup vs 1 thread');axes[0,-1].legend(frameon=False,fontsize=8)
    finish(fig,'figure-11','Figure 11: parallel scaling','Every successful repeat matches a full core reference. Reproduction pins distinct physical cores; paper hardware has 48 physical cores.\nPOW-L is approximate; without a successful parallel 1-thread group, its speedup is undefined. No sequential-method substitute is used.')
    comparisons=[]
    for ref in paper['table5']['values']:
        d=ref['dataset']+'-approx';g=groups[(d,'core','0')];baseline=groups[(d,'core','OPTIV')]
        manifest=report['datasets'].get(d,{}).get('manifest',{})
        comparisons.append({'dataset':d,'paper':ref,'measured_status':g['status'],'baseline_status':baseline['status'],
            'baseline_trial_status_counts':baseline['trial_status_counts'],
            'actual_processed_input':manifest.get('processed'),
            'paper_table4':manifest.get('paper_table4'),
            'input_claim':manifest.get('claim'),
            'measured':{k:g[k] for k in ['reported_init_s','reported_execution_s','reported_total_s','peak_rss_kib'] if k in g}})
    (out/'table-5-comparison.json').write_text(json.dumps(comparisons,indent=2)+'\n')
    coverage=report['coverage'];details=[]
    for d in ORDER:
        star=groups.get((d,'core','0'),{});base=groups.get((d,'core','OPTIV'),{})
        if star.get('status')=='complete' and base.get('status')=='complete':
            total=base['reported_total_s']['mean']/star['reported_total_s']['mean'];mem=base['peak_rss_kib']['mean']/star['peak_rss_kib']['mean']
            details.append(f'- {d}：总算法时间加速 {total:.3g} 倍，baseline / 主方法峰值 RSS 比为 {mem:.3g}。')
    report_text=f'''# 全论文实验对照

记录更新时间：{report['generated_at_utc']}。

预期 {coverage['expected_trial_records']} 条正式运行或计数观察记录，已有 {coverage['recorded_trial_records']} 条；尚缺 {coverage['pending_trial_records']} 条。{coverage['complete_validated_groups']} / {coverage['expected_groups']} 组已完成并通过全量 core 检查。逐项状态、计时、校验和输入来源见 summary.json；未完成和失败组不计算“仅成功运行的平均值”。

'''+'\n'.join(details)+'''

## 论文对照

figure-4、5、6 分别比较总算法时间、执行时间和峰值 RSS；figure-8 比较 LB、RUC 与组合过滤。figure-7 使用逐轮计数，figure-9 使用 RUC 判定耗时 / 总执行耗时，figure-10 使用五个超边比例，figure-11 使用 1–64 个物理线程。完整数值见 summary.json 和 table-5-comparison.json，图表同时提供 PNG 与 SVG。

## 解释边界

- POW-S / POW-L 使用作者生成器和固定种子 5012，是用户批准的同规模近似复现，不是论文原始合成图。
- 多个真实数据集的当前公开版本与论文表 4 不一致；不能把节点和超边差异当作已证明无影响的重新编号。每个 manifest 保存原始及预处理统计。
- 论文服务器与本次服务器不同。SIGMOD 内部计时使用墙钟，VLDB baseline 内部计时使用 CPU clock；完整进程墙钟另存，不混用。
- 新实验以 500 GiB 虚拟地址空间上限控制单进程；它不同于论文的 500 GB 物理 RAM。memory_limit 只描述本实验限制，不能直接声称与论文 OOM 完全相同。旧四数据集成功结果沿用其原记录的限制。
- 峰值内存保存 KiB；绘图为 MiB，论文只标 MB。并行与计数运行的 CSV 导出发生在算法计时后，其 RSS 不用于核心内存比较。
- 图 9 的论文柱图与正文均值、极值不一致；分别保留。论文图 5 与图 8 的同方法数值也分别提取。
- 论文数据点来自矢量图估计或明确文本标签，不是作者原始测量日志。三次重复的误差范围只描述本次运行波动。

只有所有预期配置均有终态记录、正确性和失败情况均已核对，才可称为本项目实验范围已执行完毕。它不等于论文所有数值完全一致。
'''
    synthetic_lines=[]
    for name in ['POW-S-approx','POW-L-approx']:
        manifest=report['datasets'].get(name,{}).get('manifest')
        if manifest:
            actual=manifest['processed'];reference=manifest['paper_table4']
            synthetic_lines.append(f"- {name}：本次预处理后实际为 {actual['vertices']:,} 个节点、{actual['edges']:,} 条超边；论文表 4 报告 {reference['reported_n']:,} 个节点、{reference['reported_m']:,} 条超边。")
    if synthetic_lines:
        report_text+='\n## 合成输入的实际规模\n\n'+'\n'.join(synthetic_lines)+'\n\n论文表 4 与本次预处理后统计的口径并非完全一致，以上不表示输入相同。当前 POW-L 近似输入超过十亿个节点，但超边数不足十亿；本轮不能作为论文“超边超过十亿”这一具体规模点的严格复现。生成输入和所有运行都是真实执行，近似范围须与性能结论同时保留。\n'
    failed=[g for g in report['groups'] if any(status!='ok' and count>0 for status,count in g['trial_status_counts'].items())]
    if failed:
        failure_lines=[]
        records=report.get('failure_evidence',{}).get('records',[])
        for group in failed:
            matching=[r for r in records if r['dataset']==group['dataset'] and str(r['argument'])==group['argument'] and r['label'].startswith(group['family']+'-')]
            codes=sorted({r['exit_code'] for r in matching if r['exit_code'] is not None})
            status=', '.join(f'{k}: {v}' for k,v in group['trial_status_counts'].items())
            detail='；观察到 SIGSEGV（信号 11），根因尚未确定，不能直接标为论文 OOM' if 139 in codes else ''
            remaining=group['expected_trials']-group['recorded_trials']
            progress=f'；另有 {remaining} 次尚未形成终态记录' if remaining else ''
            label=f"{group['argument']} 线程" if group['family']=='parallel' else LABELS.get(group['argument'],group['argument'])
            failure_lines.append(f"- {group['dataset']} / {group['family']} / {label}：{status}；退出码 {codes}{detail}{progress}。")
        progress_note='所有配置均已形成终态记录。' if terminal else '包含尚未完成全部重复的配置。'
        report_text+='\n## 已观察到的失败与超时\n\n'+'\n'.join(failure_lines)+'\n\n'+progress_note+'每条失败或超时均予以保留。原始退出码、峰值 RSS、内存限制及日志尾部保存在 input/results/failure-evidence.json；含失败记录的配置不发布仅成功样本的均值。\n'
    if terminal:
        report_text+='\n完整实验解释与交付审计见 [最终报告](final-report.md) 和 [结构化比较](final-comparison.json)。其中记录了 POW-L 图 9、单线程加速比分母以及过滤消融缺失的具体原因。\n'
    (out/'comparison-report.md').write_text(report_text)
    print('Saved Figures 4-11, Table 5 comparison and report in',out)

if __name__=='__main__':main()
