#!/usr/bin/env python3
"""Produce the final comparison narrative/JSON only after terminal audit passes."""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import statistics

REAL = ['HI','CO','GE','DB','DF','THS','AM','TAS','AMZ','SOA']
LABELS = {'0':'HyperCD*（LB+RUC）','1':'RUC','2':'LB','3':'HyperCD+','4':'HyperCD','5':'HyperCD++（SUC）','OPTIV':'LocalCore-OPT'}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path);args=p.parse_args();out=args.directory
    read=lambda p:json.loads(p.read_text())
    s=read(out/'summary.json');audit=read(out/'final-audit.json');paper=read(out/'input/configs/paper-extended-reference.json')
    if not s['coverage']['all_trials_recorded'] or s['workflow']['status']!='complete':raise RuntimeError('Experiment workflow is incomplete')
    if audit['issues'] or audit['status']!='passed_with_recorded_experimental_failures':raise RuntimeError('Final integrity audit has not passed')
    if audit['trial_status_counts']!=s['coverage']['status_counts']:raise RuntimeError('Audit and summary counts differ')
    g={(x['dataset'],x['family'],x['argument']):x for x in s['groups']}
    def mean(d,f,a,k='reported_total_s'):
        return g[d,f,a].get(k,{}).get('mean')
    families=[]
    for f in ['core','stats','scale','parallel']:
        rows=[x for x in s['groups'] if x['family']==f]
        families.append({'family':f,'records':sum(x['recorded_trials'] for x in rows),'groups':len(rows),'successful_validated_groups':sum(x['status']=='complete' for x in rows)})
    performance=[];ablation=[]
    for d in REAL:
        star=mean(d,'core','0');base=mean(d,'core','OPTIV')
        performance.append({'dataset':d,'star_total_s':star,'baseline_total_s':base,'speedup':base/star if base else None,
            'star_execution_s':mean(d,'core','0','reported_execution_s'),'star_peak_RSS_MiB':mean(d,'core','0','peak_rss_kib')/1024,
            'baseline_over_star_RSS':mean(d,'core','OPTIV','peak_rss_kib')/mean(d,'core','0','peak_rss_kib') if base else None})
    for d in REAL+['POW-S-approx','POW-L-approx']:
        ablation.append({'dataset':d,'execution_s':{a:mean(d,'core',a,'reported_execution_s') for a in ['0','1','2']},
            'statuses':{a:g[d,'core',a]['status'] for a in ['0','1','2']}})
    iterations=[]
    for d in ['DF','THS','TAS','AMZ']:
        for a in ['0','1','2','5']:
            row=g[d,'stats',a];trace=row['iteration_trace']
            iterations.append({'dataset':d,'argument':a,'iterations':len(trace),'computed_total':sum(t['computed'] for t in trace),
                'changed_total':sum(t['changed'] for t in trace),'observations':row['expected_trials'],'identical_repeated_traces':row['identical_iteration_traces']})
    filtering=[{'dataset':d,'fraction':mean(d,'stats','0','ruc_fraction_of_execution'),'status':g[d,'stats','0']['status']} for d in REAL+['POW-S-approx','POW-L-approx']]
    scaling=[{'dataset':d,'fractions':[.2,.4,.6,.8,1.0],'mean_total_s':[mean(d+'-E'+f,'scale','0') for f in ['0p2','0p4','0p6','0p8','1p0']]} for d in ['AMZ','TAS','SOA','AM']]
    parallel=[]
    for d in ['AMZ','SOA','POW-L-approx']:
        ts=[1,2,4,8,16,32,64];values=[mean(d,'parallel',str(t)) for t in ts]
        parallel.append({'dataset':d,'threads':ts,'mean_total_s':values,'speedup_vs_1':[values[0]/v if values[0] and v else None for v in values],
            'missing_reason':'1-thread configuration timed out in all three attempts' if not values[0] else None})
    comparison={'coverage':s['coverage'],'record_definition':{'formal_repeated_attempts':393,'deterministic_counter_observations':12},
        'families':families,'main_performance':performance,'filter_ablation':ablation,'iteration_computations':iterations,
        'filtering_cost':filtering,'size_scaling':scaling,'parallel_scaling':parallel,'table5':read(out/'table-5-comparison.json'),
        'paper_points':s['paper_comparisons'],'paper_extended_reference':paper,
        'integrity_audit_sha256':hashlib.sha256((out/'final-audit.json').read_bytes()).hexdigest(),
        'interpretation':'Complete execution coverage with explicit unsuccessful configurations and approximate/public-version inputs; not an exact reproduction of all paper numbers.'}
    (out/'final-comparison.json').write_text(json.dumps(comparison,ensure_ascii=False,indent=2)+'\n')
    lines=['# SIGMOD 2025 复现实验最终报告','',
        '主论文：*Accelerating Core Decomposition in Billion-Scale Hypergraphs*（SIGMOD 2025，DOI 10.1145/3709656）。Baseline：*Neighborhood-based Hypergraph Core Decomposition*（VLDB 2023）。',
        '', '## 完成范围与结论','',
        '本次约定的实验队列已结束，405/405 条记录均有终态，最终文件与记录审计通过。382 条成功，9 条达到虚拟内存限制，3 条发生 SIGSEGV，11 条超时。143 组配置中，135 组具有完整的成功结果和全量 core 校验；8 组保留失败状态。这里的“完成”指计划已执行、失败已记录、结果已核查和整理，不表示原论文每个数据点均被成功复现。',
        '', '405 条由 393 次正式计时尝试和 12 次确定性逐轮计数观察组成。前者按每组 3 次安排；12 次计数观察是 DF/THS/TAS/AMZ 上 LB、RUC、SUC 各一次，不应称为 405 次全部重复三次的计时实验。独立正确性检查、参考输出生成与验证运行另计。',
        '', '真实数据上的主要趋势得到支持：在 baseline 成功的 9 个数据集上，HyperCD* 的总算法时间更短、峰值 RSS 更低。但组合过滤并非在每个数据集都最快，过滤时间占比明显高于论文正文，SOA 的规模曲线也未呈现严格线性。本轮未获得原论文的 POW-L 输入，本次替代输入的超边数不足十亿；相关结果只支持这一明确输入上的观察。',
        '', '## 实验清单','',
        '- 图 4–6：十个真实数据集、5 个主对比方法的总时间、执行时间与峰值 RSS；共享同一批核心运行。SOA 的 HyperCD 与 baseline 各三次内存限制，其他主对比配置成功。',
        '- 表 5：POW-S/POW-L 替代输入上的 HyperCD* 与 baseline。两种输入的主方法均完成三次；baseline 分别发生三次 SIGSEGV、三次内存限制。',
        '- 图 7：DF/THS/TAS/AMZ 上 LB、RUC、LB+RUC、SUC 的逐轮实际计算节点数，16 条曲线全部取得并校验。',
        '- 图 8：12 个输入的过滤消融，复用核心计时。POW-L 的 RUC 一次成功、两次超时；LB 三次超时，均不公布成功样本均值。',
        '- 图 9：12 个输入各三次过滤耗时统计；11 个输入成功，POW-L 三次超时，保留缺失点。',
        '- 图 10：AMZ/TAS/SOA/AM 各 20%、40%、60%、80%、100% 超边规模，20 组共 60 次，全部成功并校验。',
        '- 图 11：AMZ/SOA/POW-L 各 1、2、4、8、16、32、64 线程，21 组共 63 次。POW-L 的 1 线程三次超时，其余 60 次成功且每次均核对全量 core。',
        '', '## 环境、来源与计量','',
        '论文使用双路 Intel Xeon Gold 6342（48 物理核、96 逻辑线程）、500 GB RAM、Ubuntu 22.04.1。本次使用双路 AMD EPYC 7543（64 物理核、128 逻辑线程）、约 1 TiB RAM、Ubuntu 22.04、GCC 11.4，编译使用 -O3。算法运行使用 CPU；未使用 GPU。并行实验优先选择不同物理核并记录 taskset 和 OpenMP 亲和性。服务器并非经证明完全独占，运行时负载记录保留；不能把所有耗时差异单独归因于算法。',
        '', '固定作者代码版本：SIGMOD `db709d81c3da8fff410c6b4f4aa2932883a227ee`；VLDB baseline `ea540958c176058b44830960753d854017719be2`。上游目录未修改，生成器固定随机种子和 SUC 观测计数在生成副本中完成，改动说明见 input/results/setup/extended-adaptations.json。',
        '', '新批次使用每进程 500 GiB RLIMIT_AS（虚拟地址空间），并非 RSS 上限，也不等同于论文的 500 GB 物理内存。旧 HI/CO/DB 成功批次为 32 GiB，AM 为 128 GiB。所有计时配置限制为 21600 秒；超时覆盖进程读取、初始化、计算以及该运行所需的输出，清理可能多出约 15 秒。论文虽规定 6 小时，但未明确给出同样的进程硬限制口径。',
        '', '图中的总算法时间为作者内部 init + execution，排除文件读取；SIGMOD 使用墙钟，VLDB baseline 使用 CPU clock。完整进程墙钟和 driver 分段计时另行保留，不混作同一指标。每次正式计时启动新进程，成功完整配置取三次算术均值；核心图的误差线表示最小至最大值，不是置信区间。RSS 记录单位为 KiB，图 6 使用 MiB；论文仅标 MB/GB，进制未明确。核心计时与输出校验分开；并行和统计运行的 CSV 在算法计时后导出，其 RSS 不用于图 6。',
        '', '## 输入数据与可比性','',
        'HI/GE/DF/THS/TAS/SOA/AMZ 来自 Cornell 对应公开数据；CO/DB/AM 来自 VLDB 作者公开数据归档。采用记录在 manifest 中的 author org 和 sort 预处理，保留原始文件及校验值。论文表 4、原始真实节点数、作者数组长度与预处理后节点数属于不同口径，不能直接等同；HI 仅原始作者数组计数吻合，其余公开版本仍存在差异。下面同时列出本次实际预处理规模与论文表 4，差异不能视作已证明无影响的重新编号。','']
    for d in REAL+['POW-S-approx','POW-L-approx']:
        manifest=s['datasets'][d]['manifest'];actual=manifest['processed'];ref=manifest['paper_table4']
        lines.append(f"- {d}：本次 {actual['vertices']:,} 节点 / {actual['edges']:,} 超边；论文 {ref['reported_n']:,} / {ref['reported_m']:,}。")
    lines += ['', 'SIGMOD 论文 PDF 第 20 页（页码 6:20），第 8 节 Datasets 段明确说明 POW-S 和 POW-L 是依据幂律分布生成的合成数据。作者公开材料未提供本次可取得的原始 POW 文件、完整参数与种子；本项目按用户批准的作者生成器 `generateHypergraph_nbr_PowerLaw`、种子 5012 生成替代输入。请求的 6000 万和 11 亿参数不是实际输出超边数的保证。POW-L 原始生成文件已只有 821,411,625 条超边，并非预处理删除至此。其节点超过十亿，但超边不足十亿，因此不构成论文“超边超过十亿”规模点的严格复现。', '', '## 图 4–6：核心性能','']
    for x in performance:
        base=f"；相对 baseline 总时间加速 {x['speedup']:.3g} 倍，baseline / HyperCD* RSS 比 {x['baseline_over_star_RSS']:.3g}" if x['speedup'] else '；baseline 三次内存限制，不能给出加速比'
        lines.append(f"- {x['dataset']}：HyperCD* 总时间 {x['star_total_s']:.6g} s，执行时间 {x['star_execution_s']:.6g} s，RSS {x['star_peak_RSS_MiB']:.6g} MiB{base}。")
    lines += ['', '这支持主方法在本次公开输入上的时间与空间优势，但绝对耗时不能直接视为对论文数值的吻合度。逐点的论文图估计、本次均值及比值已保存在 final-comparison.json 的 paper_points 中。AMZ 的 RSS 比较特别大，应结合公开输入和 baseline 显式邻居结构理解，不能外推为所有数据集的统一收益。TAS 的 SUC 在本次环境完成，而论文报告超时，属于实际观察到的不一致。',
        '', '![图 4](figure-4.png)', '![图 5](figure-5.png)', '![图 6](figure-6.png)', '', '## 表 5：大规模输入','']
    for x in comparison['table5']:
        d=x['dataset'];m=x['measured'];ref=x['paper'];rss=m['peak_rss_kib']['mean']/1024**2
        lines.append(f"- {d}：本次 init {m['reported_init_s']['mean']:.3f} s，execution {m['reported_execution_s']['mean']:.3f} s，总计 {m['reported_total_s']['mean']:.3f} s，RSS {rss:.3f} GiB。论文对应值为 {ref['init_s']} / {ref['execution_s']} / {ref['total_s']} s、{ref['memory_GB']} GB；总时间比值为 {m['reported_total_s']['mean']/ref['total_s']:.3f}。")
    lines += ['', '这些比值仅为对应标签下的描述性对照，输入规模与硬件不同，不能据此宣称复现误差很小。POW-S baseline 的退出信号为 SIGSEGV（139），根因未确定，不能把它改写为论文 OOM；POW-L baseline 在本项目虚拟内存上限下失败。论文表 5 的时间值有独立舍入，init 与 execution 相加不一定等于印刷的 total，报告保留原值。',
        '', '![表 5 对照](table-5.png)', '', '## 图 7–8：过滤效果与消融','']
    for d in ['DF','THS','TAS','AMZ']:
        rows={x['argument']:x for x in iterations if x['dataset']==d}
        lines.append(f"- {d}：总计算节点次数 LB {rows['2']['computed_total']:,}、RUC {rows['1']['computed_total']:,}、组合 {rows['0']['computed_total']:,}、SUC {rows['5']['computed_total']:,}。")
    lines += ['', '这里统计的是跨轮次计算次数，同一节点可能重复计数。组合过滤相对 LB 减少计算次数的趋势成立；SUC 的计算次数更少不代表总运行时间一定更短。组合方法的三次计数轨迹一致；另外三种过滤各一次观测，不能把一次观测描述为重复稳定性证据。',
        '', '在执行时间消融中，组合过滤在 10 个真实输入中的 8 个快于 RUC 与 LB 两者；DF 上 RUC 略快，SOA 上 LB 和 RUC 均略快。这些小差异仅是三次均值，未进行显著性检验。POW-S 组合执行时间为 132.323 s，而 RUC 为 80.737 s、LB 为 102.701 s，未得到组合始终最快的结果。POW-L RUC 虽有一次成功计时且独立全量校验通过，但另外两次超时，LB 三次超时；图 8 不为这两组绘制成功样本均值。',
        '', '![图 7](figure-7.png)', '![图 8](figure-8.png)', '', '## 图 9：过滤时间占比','']
    fractions=[x['fraction'] for x in filtering if x['dataset'] in REAL]
    lines += [f"本次十个真实输入的 RUC 判定耗时 / execution 比例在 {min(fractions):.2%}–{max(fractions):.2%}，跨数据集等权平均 {statistics.mean(fractions):.2%}。这是十个真实输入的均值，不是论文全部数据集均值的同口径估计。论文正文声称平均 4.5%、最大 10.8%、SOA 最小 0.002%；在本次公开计数器口径下未观察到同样低的占比。",'',
        '使用作者带统计版本输出的 decide_time / exc_Time。核对 Final_nbrCoreDecomposition.cpp 后确认，decide_time 在节点 core 下降后开始计时，包含遍历关联超边、更新超边 core 和设置邻居 changed 标记，并非只计算一个布尔条件的耗时。统计计时本身也有观测开销，不能替代无统计版本的主性能计时。不同输入、硬件及计量实现可能影响比例，目前没有证据将差异归于某一个单独原因。论文图中 TAS 约 21.7%，又与正文“最大 10.8%”冲突；图 9 按图形提取值对照，正文声明单独保留。POW-L 统计版本三次超时，无有效比例，不能填 0。',
        '', '![图 9](figure-9.png)', '', '## 图 10：规模实验','']
    for x in scaling:
        lines.append(f"- {x['dataset']}：20% 至 100% 的平均总时间依次为 "+'、'.join(f'{v:.3f}' for v in x['mean_total_s'])+f" s；100% / 20% 为 {x['mean_total_s'][-1]/x['mean_total_s'][0]:.2f} 倍。")
    lines += ['', '所有曲线随规模增大而上升，AMZ/TAS/AM 的总体趋势与论文相近。SOA 从 20% 到 100% 的增长明显超过 5 倍，不能把本次所有曲线概括成近似线性。采样遵循作者方法、固定种子及嵌套前缀，再执行作者预处理；实际节点数和超边数在各采样 manifest 中，名义百分比不保证预处理后所有结构统计同比例变化。',
        '', '![图 10](figure-10.png)', '', '## 图 11：CPU 并行扩展','']
    for x in parallel[:2]:
        d=x['dataset'];paper64=next(v['labeled_speedup'] for panel in paper['panels'] if panel['figure']==11 for v in panel['values'] if v['dataset']==d and v['threads']==64)
        lines.append(f"- {d}：1 线程 {x['mean_total_s'][0]:.3f} s，64 线程 {x['mean_total_s'][-1]:.3f} s，加速 {x['speedup_vs_1'][-1]:.2f} 倍；论文标签为 {paper64:.1f} 倍。")
    x=parallel[-1]
    lines += ['- POW-L-approx：2、4、8、16、32、64 线程平均总算法时间依次为 '+ '、'.join(f'{v:.3f}' for v in x['mean_total_s'][1:])+' s。', '',
        'AMZ/SOA 的多线程加速趋势成立，但本次 64 个线程使用 64 个物理核，论文机器只有 48 个物理核，64 线程硬件含义不同。POW-L 的并行实现 1 线程三次超时，无法计算相对 1 线程的速度提升；不会用另一个顺序实现 HyperCD* 的时间代替分母。其 2–64 线程绝对时间仍有效，每次输出都与同输入的参考 core 一致。并行总算法时间排除文件加载，所以不能等同于端到端服务延迟。',
        '', '![图 11](figure-11.png)', '', '## 失败与正确性边界','']
    for row in s['groups']:
        if row['status']=='complete':continue
        label=row['argument']+' 线程' if row['family']=='parallel' else LABELS[row['argument']]
        lines.append(f"- {row['dataset']} / {row['family']} / {label}："+', '.join(f'{k}={v}' for k,v in row['trial_status_counts'].items())+'。')
    lines += ['', '失败记录与日志尾部见 input/results/failure-evidence.json；原始服务器日志与部分输出均保留。POW-L LB 首次验证尝试超时，明确关联为正式第 1 次失败记录，不是另造一个成功样本。所有失败组不报告仅成功运行的平均值，也未增加有利样本替换超时。', '',
        f"最终审计重新扫描 {len(audit['inputs'])} 个唯一输入文件和 {len(audit['binaries'])} 个正式二进制，SHA 与实验记录相符；核对 {len(audit['full_core_records'])} 条执行时全量 core 哈希记录，均匹配相应参考，并检查 CSV 仍存在。最终审计没有再次扫描所有 core CSV 的内容，执行时已做全量哈希校验。没有发现已完成输出的 core 不一致；失败组没有输出时应称为‘未取得校验结果’，不能称为‘校验错误’。", '',
        '真实/合成大输入的参考输出由同输入的已记录算法生成，方法间一致性不等于独立数学证明。另有小图独立 oracle 864 项通过；扩展统计/并行检查 1136 项通过、8 项明确标记为上游不支持的稀疏输入，未把这 8 项算作通过；数据工具 4 项检查通过。', '',
        '本轮没有获得 POW-L LB 的成功全量输出，也没有 POW-L 单线程并行基准和过滤成本比例。若课程要求这些点也必须成功，或要求论文原始 POW 图及严格超过十亿超边，仍需另行取得数据或定义新的资源协议；本报告没有声称解决这些限制。', '',
        '## 交付文件与复查','',
        '- 本报告：final-report.md；完整结构化比较：final-comparison.json；分组均值及全部来源索引：summary.json。',
        '- 图 4–11：figure-4 至 figure-11 的 PNG 与可缩放 SVG；表 5：table-5.png、table-5.svg、table-5-comparison.json。',
        '- 最终文件审计：final-audit.json；失败证据：input/results/failure-evidence.json；原始小型元数据和数据来源：input/。',
        '- 大型数据、完整 core CSV 和服务器完整日志留在指定 /data 项目目录；旧 /home 项目结果保持原状。未自动 commit 或 push。',
        '', '从仓库根目录重新生成小型报告：','',
        '```bash','PYTHONDONTWRITEBYTECODE=1 python3 scripts/summarize_full_results.py reports/full-comparison/input --output reports/full-comparison/summary.json',
        'MPLCONFIGDIR="$PWD/.runtime/matplotlib" python3 scripts/plot_full_results.py reports/full-comparison/summary.json --input reports/full-comparison/input --output reports/full-comparison',
        'MPLCONFIGDIR="$PWD/.runtime/matplotlib" python3 scripts/finalize_report.py reports/full-comparison','```','',
        '最后一条命令要求审计已通过；它不会启动新实验。论文数值来源包括用户提供的 PDF 第 20–24 页、图形估计及明确标签，不是作者原始测量日志。', '',
        '参考：[SIGMOD 论文](https://doi.org/10.1145/3709656)、[VLDB baseline 论文](https://arxiv.org/abs/2301.06426)、[SIGMOD 作者代码](https://github.com/unswdb/hyper-k-core)、[baseline 作者代码](https://github.com/toggled/vldbsubmission)、[Cornell 数据](https://www.cs.cornell.edu/~arb/data/)。','']
    (out/'final-report.md').write_text('\n'.join(lines))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    rows=[]
    for x in comparison['table5']:
        ref=x['paper'];m=x['measured'];d=ref['dataset']
        rows.append([d,'Paper',str(ref['init_s']),str(ref['execution_s']),str(ref['total_s']),f"{ref['memory_GB']} GB",'OOM'])
        rows.append([d+' approx','Reproduction',f"{m['reported_init_s']['mean']:.2f}",f"{m['reported_execution_s']['mean']:.2f}",f"{m['reported_total_s']['mean']:.2f}",f"{m['peak_rss_kib']['mean']/1024**2:.2f} GiB",'SIGSEGV x3' if d=='POW-S' else 'AS limit x3'])
    fig,ax=plt.subplots(figsize=(13,3.8));ax.axis('off')
    table=ax.table(cellText=rows,colLabels=['Input','Source','Init (s)','Execution (s)','Total (s)','Peak memory','Baseline outcome'],loc='center',cellLoc='center',colWidths=[.15,.16,.12,.14,.12,.14,.17])
    table.auto_set_font_size(False);table.set_fontsize(9);table.scale(1,2.0)
    for (rr,cc),cell in table.get_celld().items():
        cell.set_edgecolor('#cbd5e1')
        if rr==0:cell.set_facecolor('#e2e8f0');cell.set_text_props(weight='bold')
        elif rr in [2,4]:cell.set_facecolor('#e7f4ef')
    fig.suptitle('Table 5: large-input comparison',x=.04,ha='left',fontsize=16,weight='bold')
    fig.text(.04,.045,'Reproduction = mean of 3 successful HyperCD* runs. Inputs and hardware differ; POW-L approx has fewer than 1 billion edges.\nMeasured memory uses GiB; paper GB base is unspecified. AS limit = 500 GiB virtual address limit, not the paper RAM limit.',fontsize=8.5,color='#475569')
    fig.subplots_adjust(left=.035,right=.98,top=.85,bottom=.2)
    for ext in ['png','svg']:fig.savefig(out/('table-5.'+ext),dpi=180,facecolor='white')
    plt.close(fig)
    print('Final report, structured comparison and Table 5 generated')


if __name__=='__main__':main()
