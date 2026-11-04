"""Standalone publication-style exploratory result figure, using saved run data."""
import json
from pathlib import Path

from .store import ROOT


def render():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    report=json.loads((ROOT/'reports'/'research-test-v1.json').read_text())
    names=list(report['summary']);labels=['Lexical','Cross-encoder','LLM split','Split + CE','Split + CE\n+ score gate']
    r2=[report['summary'][n]['mean_recall_at_2'] for n in names]
    r4=[report['summary'][n]['mean_recall_at_4'] for n in names]
    times=[report['summary'][n]['retrieval_plus_plan_p50_ms'] for n in names]
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    fig,(left,right)=plt.subplots(1,2,figsize=(13,5),gridspec_kw={'width_ratios':[1.4,1]})
    x=np.arange(len(names));w=.36
    left.bar(x-w/2,r2,w,label='Mean Recall@2',color='#2563eb');left.bar(x+w/2,r4,w,label='Mean Recall@4',color='#93c5fd')
    left.set_ylim(0,1.13);left.set_xticks(x,labels,fontsize=9);left.set_ylabel('Evidence recall');left.set_title('Required-evidence retrieval (12 answerable questions)')
    left.legend(frameon=False,loc='lower left')
    for i,value in enumerate(r2):left.text(i-w/2,value+.02,f'{value:.2f}',ha='center',fontsize=8)
    for i,value in enumerate(r4):left.text(i+w/2,value+.02,f'{value:.2f}',ha='center',fontsize=8)
    right.bar(x,times,color=['#94a3b8','#0f766e','#0f766e','#0f766e','#d97706'])
    right.set_yscale('log');right.set_xticks(x,labels,fontsize=9);right.set_ylabel('Median milliseconds (log scale)');right.set_title('Retrieval + planning latency; answer generation excluded')
    for i,value in enumerate(times):right.text(i,value*1.15,f'{value:,.0f}',ha='center',fontsize=8)
    right.set_ylim(.6,max(times)*3)
    fig.suptitle('Local neural RAG ablation: gains, regressions and compute cost',fontsize=15,x=.04,ha='left')
    fig.text(.04,.02,'Exploratory same-author dataset; 26 reviewed paraphrase chunks. One run, no uncertainty estimates. Not a general financial benchmark.',fontsize=9,color='#475569')
    fig.tight_layout(rect=(.02,.07,1,.91))
    dest=ROOT/'reports'/'research-ablation-v1.png';fig.savefig(dest,dpi=180);fig.savefig(dest.with_suffix('.pdf'));plt.close(fig)
    print(dest)


if __name__=='__main__':render()
