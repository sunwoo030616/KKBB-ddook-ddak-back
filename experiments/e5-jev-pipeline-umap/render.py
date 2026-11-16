"""Replay actual E5/JEV trace on verified, fixed UMAP coordinates. No API calls."""
import json, math, html
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parent
points=json.loads((ROOT/'points.json').read_text())
r=json.loads((ROOT/'trace.json').read_text())
assert points['catalog_sha256']==r['catalog_sha256']
p=points['points']; byid={x['id']:x for x in p}
assert len(p)==585 and len(byid)==585
original=r['original_candidate_ids']; candidates=r['candidate_ids']; short=r['shortlist']; final=r['selected_ids']
eligible=[i for i,v in r['candidate_probabilities'].items() if v>=.3]
assert set(final)<=set(short)<=set(eligible)<=set(candidates)<=set(byid)
assert set(original)<=set(candidates) and len(original)==80
assert len(short)==10 and len(final)==3
assert len(r['set_mapping'])==math.comb(len(short),3)
plt.rcParams.update({'font.family':'Apple SD Gothic Neo','axes.unicode_minus':False,'font.size':12})
colors=['#8995a5','#d58a12','#008c87','#3265d9']
sets=[list(byid),candidates,short,final]
titles=['전체 금융 메뉴 585개','E5 Top-80 + 보완 1개 = 81개','JEV 평가 → 조합 후보 10개','JEV 조합 선택 → 최종 3개']
subs=['실제 E5 메뉴 임베딩의 UMAP','원문 검색 80개 유지 · 키워드 보완 1개','적합도 ≥ 0.30: 18개 → 중복 완화 → 10개','120개 3종 조합 중 선택 · 별도 신뢰도 컷 없음']
xs=[v['x'] for v in p];ys=[v['y'] for v in p]
xlim=(min(xs)-1,max(xs)+1);ylim=(min(ys)-1,max(ys)+1)
def draw(ax,k):
 ax.scatter(xs,ys,c='#dce1e8',s=11,alpha=.7,linewidths=0)
 ids=sets[k];ax.scatter([byid[i]['x'] for i in ids],[byid[i]['y'] for i in ids],c=colors[k],s=17 if k<2 else 53,alpha=.9,edgecolors='white',linewidths=.5)
 if k==1:
  extra=set(candidates)-set(original)
  ax.scatter([byid[i]['x'] for i in extra],[byid[i]['y'] for i in extra],marker='s',s=40,c='#25b8c8',edgecolors='white')
 if k==3:
  for n,i in enumerate(final,1):
   q=byid[i];ax.annotate(str(n),(q['x'],q['y']),xytext=(7,7),textcoords='offset points',weight='bold',color=colors[k],fontsize=15)
 ax.set(xlim=xlim,ylim=ylim);ax.set_aspect('equal');ax.set_xticks([]);ax.set_yticks([])
 for spine in ax.spines.values():spine.set_visible(False)
 ax.set_title(titles[k],loc='left',fontweight='bold',fontsize=15,pad=18)
 ax.text(0,-.07,subs[k],transform=ax.transAxes,fontsize=10,color='#536174')
fig,axes=plt.subplots(1,4,figsize=(20,11.25),facecolor='white')
fig.subplots_adjust(top=.75,bottom=.32,left=.035,right=.98,wspace=.14)
for k,ax in enumerate(axes):draw(ax,k)
fig.text(.035,.92,'검색으로 후보를 좁히고, 판단으로 메뉴 조합을 결정',fontsize=28,weight='bold',color='#17263c')
fig.text(.035,.85,'입력: “'+r['query']+'”',fontsize=18,color='#34455d')
for n,i in enumerate(final):
 q=byid[i];rank=original.index(i)+1
 fig.text(.045,.22-n*.045,f'{n+1}  {q["name"]}     |     E5 {rank}위     |     JEV 개별 적합도 {r["candidate_probabilities"][i]:.2f}',fontsize=16,color='#234c91')
fig.text(.035,.045,'실제 실행 S01_03 · 개선판 검증 경로 · 동일 좌표 유지 · UMAP은 설명용 2D 투영이며 검색·판단에는 사용하지 않음',fontsize=11,color='#657185')
fig.savefig(ROOT/'pipeline-umap.png',dpi=180);plt.close(fig)
for k in range(4):
 fig,ax=plt.subplots(figsize=(12,6.75),facecolor='white');fig.subplots_adjust(left=.08,right=.92,top=.8,bottom=.22)
 draw(ax,k);fig.text(.08,.92,'“'+r['query']+'”',fontsize=14)
 fig.text(.08,.06,'동일한 실제 E5 UMAP 좌표 · 회색: 전체 585개 · 강조: 해당 단계 후보',fontsize=11,color='#536174')
 fig.savefig(ROOT/f'stage-{k+1}.png',dpi=180);plt.close(fig)
# Offline HTML uses the same recorded coordinates; no CDN or external calls.
xlo,xhi=xlim;ylo,yhi=ylim
svg=[]
for q in p:
 i=q['id'];rank=original.index(i)+1 if i in original else '-';prob=r['candidate_probabilities'].get(i,'-')
 label=f'{q["name"]} | {i} | E5 순위 {rank} | JEV 적합도 {prob}'
 svg.append(f'<circle cx="{40+920*(q["x"]-xlo)/(xhi-xlo):.3f}" cy="{470-420*(q["y"]-ylo)/(yhi-ylo):.3f}" r="3" data-id="{i}"><title>{html.escape(label)}</title></circle>')
buttons=''.join(f'<button onclick="stage({k})">{html.escape(t)}</button>' for k,t in enumerate(titles))
body='''<!doctype html><meta charset="utf-8"><title>E5 → JEV 실제 후보 축소</title><style>body{font-family:system-ui,sans-serif;margin:30px;color:#17263c}button{padding:12px;margin:4px;border:1px solid #ccd3dd;border-radius:8px;background:white;cursor:pointer}svg{max-width:1100px;width:100%;display:block}circle:hover{stroke:#000;stroke-width:2}td,th{padding:9px;text-align:left}#note{color:#536174}</style>'''
body+='<h1>E5 → JEV: 실제 후보 축소</h1><p>'+html.escape(r['query'])+'</p>'+buttons+'<p id="note"></p><svg viewBox="0 0 1000 520">'+''.join(svg)+'</svg>'
body+='<table><tr><th>최종 메뉴</th><th>E5 원문 순위</th><th>JEV 개별 적합도</th></tr>'+''.join(f'<tr><td>{html.escape(byid[i]["name"])}</td><td>{original.index(i)+1}</td><td>{r["candidate_probabilities"][i]:.2f}</td></tr>' for i in final)+'</table><p>조합 Choice confidence = 0.27 · 최종 선택 confidence 하한 없음. 이는 개별 적합도 및 실측 정확도와 다른 값입니다.</p><p>UMAP은 실제 E5 384차원 메뉴 임베딩을 2차원으로 투영한 설명용 지도입니다. 점에 마우스를 올리면 실제 메뉴명·E5 순위·JEV 적합도를 확인할 수 있습니다.</p>'
body+='<script>const sets='+json.dumps(sets)+';const colors='+json.dumps(colors)+';const notes='+json.dumps(subs,ensure_ascii=False)+''';function stage(k){const ids=new Set(sets[k]);document.querySelectorAll('circle').forEach(c=>{const on=ids.has(c.dataset.id);c.setAttribute('fill',on?colors[k]:'#dce1e8');c.setAttribute('r',on&&k>1?6:3);});document.getElementById('note').textContent=notes[k];}stage(0);</script>'''
(ROOT/'pipeline-umap.html').write_text(body)
print('PASS: catalog identity, 585 coordinates, trace membership, thresholds and 120 combinations verified')
print('Wrote pipeline-umap.png, stage-1..4.png and offline pipeline-umap.html')
