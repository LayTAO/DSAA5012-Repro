#!/usr/bin/env python3
"""Build scientific comparison figures and a Chinese report from small saved records."""
import argparse
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

METHODS=['vldb_OPTIV','sigmod_4','sigmod_3','sigmod_5','sigmod_0']
LABELS={'vldb_OPTIV':'LocalCore-OPT','sigmod_4':'HyperCD','sigmod_3':'HyperCD+',
        'sigmod_5':'HyperCD++','sigmod_0':'HyperCD*','sigmod_1':'RUC only','sigmod_2':'LB only'}
COLORS={'vldb_OPTIV':'#bf6516','sigmod_4':'#7c8898','sigmod_3':'#4879a3',
        'sigmod_5':'#8d72ac','sigmod_0':'#008577','sigmod_1':'#4879a3','sigmod_2':'#b59a53'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    args=parser.parse_args(); root=args.directory
    registry=json.loads((root/'paper-batch.json').read_text()); datasets=list(registry)
    measured={d:{m['method']:m for m in json.loads((root/d/'summary.json').read_text())['methods']} for d in datasets}
    paper=json.loads((root/'paper-digitized.json').read_text())
    estimates={p['figure']:{(v['dataset'],v['method']):v['estimate'] for v in p['values']} for p in paper['panels']}
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.spines.top':False,'axes.spines.right':False})
    metrics=[(4,'reported_total_s',1,'Total algorithm time (s)'),
             (5,'reported_execution_s',1,'Execution excluding initialization (s)'),
             (6,'peak_rss_kib',1024,'Peak memory (paper MB; measured MiB)')]
    fig,axes=plt.subplots(2,3,figsize=(14,8.1),sharex=True)
    x=np.arange(len(datasets)); width=.145
    for column,(number,metric,divisor,title) in enumerate(metrics):
        all_values=[]
        for row in range(2):
            ax=axes[row,column]
            for index,method in enumerate(METHODS):
                values=[estimates[number][(d,method)] if row==0 else measured[d][method][metric]['mean']/divisor for d in datasets]
                all_values+=values
                kwargs={}
                if row==1:
                    kwargs['yerr']=[[v-measured[d][method][metric]['min']/divisor for d,v in zip(datasets,values)],
                                    [measured[d][method][metric]['max']/divisor-v for d,v in zip(datasets,values)]]
                    kwargs['error_kw']={'elinewidth':.7,'capsize':1.4}
                ax.bar(x+(index-2)*width,values,width,color=COLORS[method],label=LABELS[method],**kwargs)
            ax.set_yscale('log'); ax.set_axisbelow(True); ax.grid(axis='y',alpha=.2)
            ax.set_xticks(x,datasets)
            if row==0: ax.set_title('Figure '+str(number)+': '+title,fontsize=10,pad=12)
            if column==0: ax.set_ylabel('Paper: estimates' if row==0 else 'Reproduction: mean of 3')
        for row in range(2): axes[row,column].set_ylim(min(all_values)/1.7,max(all_values)*2.8)
    handles,labels=axes[0,0].get_legend_handles_labels()
    fig.legend(handles,labels,loc='lower center',ncol=5,bbox_to_anchor=(.5,.055),frameon=False)
    fig.suptitle('SIGMOD 2025: core performance comparison',x=.04,ha='left',fontsize=17,weight='bold')
    fig.text(.04,.925,'Four published-source datasets | Single CPU | GCC -O3 | Paper bars digitized to two significant figures',fontsize=10,color='#475569')
    fig.text(.04,.02,'CO, DB and AM retain documented vertex-statistics differences from Table 4. Hardware and timer boundaries are recorded in the report.\nMeasured error bars show min-max across three fresh processes. These are not all ten paper datasets.',fontsize=9,color='#475569')
    fig.subplots_adjust(left=.07,right=.98,top=.84,bottom=.17,hspace=.19,wspace=.28)
    for extension in ['png','svg']: fig.savefig(root/('core-comparison.'+extension),dpi=180,facecolor='white')
    plt.close(fig)

    ablation=['vldb_OPTIV','sigmod_2','sigmod_1','sigmod_0']
    fig,axes=plt.subplots(1,2,figsize=(12,4.9),sharey=True)
    for index,ax in enumerate(axes):
        for order,method in enumerate(ablation):
            values=[estimates[8][(d,method)] if index==0 else measured[d][method]['reported_execution_s']['mean'] for d in datasets]
            kwargs={}
            if index==1:
                kwargs['yerr']=[[v-measured[d][method]['reported_execution_s']['min'] for d,v in zip(datasets,values)],
                                [measured[d][method]['reported_execution_s']['max']-v for d,v in zip(datasets,values)]]
                kwargs['error_kw']={'elinewidth':.7,'capsize':1.4}
            ax.bar(x+(order-1.5)*.18,values,.18,color=COLORS[method],label=LABELS[method],**kwargs)
        ax.set_yscale('log');ax.set_xticks(x,datasets);ax.set_axisbelow(True);ax.grid(axis='y',alpha=.2)
        ax.set_title('Paper Figure 8: estimates' if index==0 else 'Reproduction: mean of 3')
    axes[0].set_ylabel('Execution time (seconds, log scale)')
    handles,labels=axes[0].get_legend_handles_labels()
    fig.legend(handles,labels,loc='lower center',ncol=4,bbox_to_anchor=(.5,.075),frameon=False)
    fig.suptitle('Filtering efficiency: lower bound (LB), RUC, and LB + RUC',x=.04,ha='left',fontsize=15,weight='bold')
    fig.text(.04,.025,'HyperCD* combines LB and RUC. Baseline uses its original CPU timer; SIGMOD methods use their original wall timer.',fontsize=9,color='#475569')
    fig.subplots_adjust(left=.08,right=.98,top=.82,bottom=.24,wspace=.16)
    for extension in ['png','svg']:fig.savefig(root/('filter-ablation.'+extension),dpi=180,facecolor='white')
    plt.close(fig)

    comparisons=[]
    paragraphs=[]
    filter_paragraphs=[]
    wall_speedups=[]
    for dataset in datasets:
        a,b=measured[dataset]['sigmod_0'],measured[dataset]['vldb_OPTIV']
        total=b['reported_total_s']['mean']/a['reported_total_s']['mean']
        execution=b['reported_execution_s']['mean']/a['reported_execution_s']['mean']
        memory=b['peak_rss_kib']['mean']/a['peak_rss_kib']['mean']
        wall=b['total_before_export_wall_s']['mean']/a['total_before_export_wall_s']['mean']
        wall_speedups.append(f'{dataset} {wall:.2f}×')
        reference={str(f):estimates[f][(dataset,'vldb_OPTIV')]/estimates[f][(dataset,'sigmod_0')] for f in [4,5,6]}
        filter_paragraphs.append(f"- **{dataset}**：相对无过滤配置，LB+RUC 的执行阶段加速为 **{measured[dataset]['sigmod_3']['reported_execution_s']['mean']/a['reported_execution_s']['mean']:.2f}×**；仅 LB、仅 RUC 相对 LB+RUC 的耗时比分别为 **{measured[dataset]['sigmod_2']['reported_execution_s']['mean']/a['reported_execution_s']['mean']:.2f}× / {measured[dataset]['sigmod_1']['reported_execution_s']['mean']/a['reported_execution_s']['mean']:.2f}×**。")
        comparisons.append({'dataset':dataset,'measured_total_speedup':total,'paper_total_speedup_estimate':reference['4'],
                            'measured_execution_speedup':execution,'paper_execution_speedup_estimate':reference['5'],
                            'measured_memory_ratio':memory,'paper_memory_ratio_estimate':reference['6'],
                            'measured_total_before_export_wall_speedup':wall,
                            'execution_ablation_s':{m:measured[dataset][m]['reported_execution_s']['mean'] for m in ['sigmod_3','sigmod_2','sigmod_1','sigmod_0']}})
        paragraphs.append(f"- **{dataset}**：主方法 / baseline 平均总算法时间为 **{a['reported_total_s']['mean']:.4f} / {b['reported_total_s']['mean']:.4f} 秒**，加速 **{total:.2f}×**（论文图估计 **{reference['4']:.2f}×**）；执行阶段加速 **{execution:.2f}×**（论文约 **{reference['5']:.2f}×**）；baseline/主方法内存比为 **{memory:.2f}×**（论文约 **{reference['6']:.2f}×**）。")
    (root/'comparison.json').write_text(json.dumps(comparisons,indent=2)+'\n')
    all_faster=all(row['measured_total_speedup']>1 and row['measured_execution_speedup']>1 and row['measured_memory_ratio']>1 for row in comparisons)
    claim='这四个数据集上，主方法的总算法时间、执行时间和峰值内存均优于 baseline，复现了论文核心性能结论的方向。' if all_faster else '部分指标未呈现论文所述优势，应按下列逐项数据报告差异，不能笼统宣称复现全部性能结论。'
    text=f'''# SIGMOD 2025 核心性能与过滤消融复现

## 范围与结论

本项目复现 [Accelerating Core Decomposition in Billion-Scale Hypergraphs](https://doi.org/10.1145/3709656)，以 [VLDB 2023 原作者实现](https://github.com/toggled/vldbsubmission) 为 baseline。\n\n本轮完成 **HI、CO、DB、AM 四个数据集 × 七种配置 × 三次运行，共 84 次正式计时**；每组计时前另行执行一次全量 core number 校验。全部计时成功，四组数据均通过七种实现配置的逐节点一致性检查。小图独立 oracle 共 864 次检查通过。

覆盖论文图 4–6 的五种主算法对比，以及图 8 的 LB / RUC / LB+RUC 消融。{claim}这里的复现范围是四个公开来源数据集；全论文十个真实数据集的平均倍数、十亿级与并行实验不在本轮完成范围内。

## 与论文结果逐项对照

下列复现实测均为三次运行的算术平均值。论文数值来自第 21 页矢量柱图，保留两位有效数字，属于估计值。

'''+ '\n\n'.join(paragraphs)+'''

![核心性能比较](core-comparison.png)

每组柱顺序与论文图例一致。上排为论文估计值，下排为实验服务器测量均值；误差线为三次运行的最小值至最大值。完整数值和比例见 [comparison.json](comparison.json)、各数据集子目录的 `summary.json` 与 `runs.jsonl`。

## 过滤策略消融

![过滤策略比较](filter-ablation.png)

配置 2 仅启用 LB，配置 1 仅启用 RUC，配置 0 同时启用 LB 与 RUC，即 HyperCD*。图 8 对照保存了 baseline 与三种过滤组合；无过滤的配置 3 也在核心对比中测量。图 5 与图 8 中论文对同一方法给出的柱高并非处处相同，本项目分别使用各图的估计值，不强行合并。

## 数据来源与对齐边界

HI 使用 Cornell 官方链接的完整 History 原始数据。先按原始有序节点列表去重，再按作者 `org` 和 `sortEV desc asc` 处理。采用作者程序的数组长度统计时，可得到表 4 的 1,034,877 个节点槽位及 896,293 个超边槽位；预处理后的实际节点数为 503,868、超边数为 252,935。正式输入保留作者流程产生的编号空缺。

CO、DB、AM 使用 VLDB 作者 README 链接的数据包。它们的超边数分别为 83,105、2,170,260、17,120,546，加上作者加载器的两个偏移/EOF 槽位，与论文表 4 精确一致；平均超边大小也一致。节点数及最大 ID 与表 4 有差异，原论文未提供原始输入校验值或编号映射，因此本项目**不能证明它们只是同一超图的重新编号**。本轮属于对作者公开版本的复现，保留此数据差异，不人为补节点凑数。

当前 Cornell 下载的 CO、GE、DF 候选连超边数也未对齐，已排除出本轮计时，审计结果保存在 `excluded-cornell-*.json`。每份实际输入的来源、SHA-256、统计和预处理命令见各数据集的 `data-manifest.json`。

## 环境与测量口径

服务器：双路 AMD EPYC 7543，Ubuntu 22.04，GCC 11.4.0；共同编译选项为 `-O3 -DNDEBUG -std=c++20 -fopenmp -fstack-protector-strong`。单线程绑定 CPU 0，按固定种子 5012 打乱计时顺序。数据验证也起到预热作用，因此采用温缓存条件。每次运行独立进程，超时阈值为 6 小时。

总算法时间取作者内部初始化与执行时间之和，执行时间取原内部执行计时。SIGMOD 使用墙钟，VLDB 使用 `clock()` CPU 时间；baseline 还会在内部计时结束后构造最终 core map。统一驱动的完整墙钟时间另外保存在日志汇总中，不与上述字段混用。正式计时不导出 core CSV。

内存为 GNU time 的进程峰值 RSS，原始单位 KiB，本项目图中转换为 MiB；论文图轴仅写 MB，单位基数未明确。CO、DB、HI 的虚拟地址空间上限为 32 GiB，AM 为 128 GiB；这些限制与论文 500 GB 物理内存不同。所有本轮记录成功完成，未将本地限制导致的失败标作论文 OOM。

原作者脚本在同一进程中重复调用算法，本轮每次使用新进程。源码检查发现 baseline 的 `local_core_OPTIV` 中 CSR 数组由 `malloc` 分配，函数内未释放，重复调用可能累积分配；这属于源码层面的差异，尚未单独测量其对论文内存比值的贡献。

论文服务器为双路 Xeon Gold 6342、500 GB RAM，代码版本与精确计时范围未全部给出。硬件、编译器版本、输入编号布局、重复运行方式和日志开关都可能影响绝对耗时与 RSS；本报告记录这些可能原因，不把它们作为已经验证的因果解释。

## 验证与可重复执行

上游算法正文未修改。驱动增加计时、导出和输入真实节点筛选，以避免把编号空缺当作真实节点。独立小图验证覆盖强诱导子超图语义、重复边、单节点边与稀疏编号。

配置、运行入口和详细步骤见 [运行说明](../../docs/reproduction-runbook.md)、[全文核对](../../docs/paper-audit.md)。论文配置与矢量提取依据分别为 [paper-profile.json](paper-profile.json)、[paper-digitized.json](paper-digitized.json)。作者代码 commit 见 [upstream.lock.json](upstream.lock.json)。本目录仅保存小型摘要与科学图表；大数据和完整 core 输出保留在服务器 home 项目中。

## 未覆盖实验

本轮未完成其余六个真实数据集、图 7 的逐轮计算数量、图 9 的过滤阶段时间占比、图 10 的数据规模扩展、图 11 的并行扩展和表 5 的十亿级实验。POW-L 原始大小约 187 GB，已超过当前 home 分区可用空间；论文也未给出完整的合成生成参数和随机种子。已有结果不用于声称复现全论文的 7× / 36× 全数据平均值。
'''
    hi=measured['HI'];co=measured['CO']
    differences=(f"\n\n消融差异需要保留：HI 上仅 LB / 仅 RUC 的均值分别为 {hi['sigmod_2']['reported_execution_s']['mean']:.5f} / {hi['sigmod_1']['reported_execution_s']['mean']:.5f} 秒，论文图 8 的对应估计为 {estimates[8][('HI','sigmod_2')]:.3f} / {estimates[8][('HI','sigmod_1')]:.3f} 秒，本轮两者的顺序与论文不同。CO 上加入 LB 后的执行时间变化很小，不能据三次重复断言具有统计显著性；其总算法时间（含初始化）甚至略高于仅 RUC。过滤组合的收益与数据有关。\n\n"
                 f"核心对比也保留了 HyperCD++ 在 CO 上开销较大的现象：本轮总算法时间为 {co['sigmod_5']['reported_total_s']['mean']:.2f} 秒，论文图 4 约 {estimates[4][('CO','sigmod_5')]:.0f} 秒。整体优势方向一致，不代表绝对数值或每个配置的排序完全一致。\n\n")
    text=text.replace('## 数据来源与对齐边界', '\n\n'.join(filter_paragraphs)+differences+'## 数据来源与对齐边界')
    text=text.replace('正式计时不导出 core CSV。', '正式计时不导出 core CSV。作为统一墙钟口径的补充，包含读取、构造和完整分解调用的 baseline/主方法比值为：'+ '、'.join(wall_speedups)+'；这些值不用于替代论文图 4 的作者内部计时。')
    text=text.replace('单线程绑定 CPU 0，', '单线程绑定 CPU 0，未独占整台服务器；各批次 metadata / summary 保存了运行前后的系统负载。')
    (root/'README.md').write_text(text)
    print(json.dumps(comparisons,indent=2))


if __name__=='__main__':
    main()
