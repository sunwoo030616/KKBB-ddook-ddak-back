#!/usr/bin/env python3
"""Project real production E5 vectors; replay catalog-matched measured JEV traces."""
import argparse
import hashlib
import html
import importlib.util
import json
import os
from pathlib import Path
import platform
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def validate_trace(evidence, row, digest, ranked_ids, top_k):
    if evidence.get('mode') != 'e5_jev' or evidence.get('catalog_sha256') != digest:
        raise ValueError('JEV evidence mode/catalog mismatch')
    if row.get('error') or row.get('jev_calls') != 1:
        raise ValueError('Require a successful actual JEV call')
    if row.get('candidate_ids') != ranked_ids[:len(row['candidate_ids'])]:
        raise ValueError('Fresh E5 ranking differs from recorded JEV candidate order')
    if len(row['candidate_ids']) != top_k:
        raise ValueError('Top-K must match actual JEV evidence')
    selected = row.get('selected', [])
    if row.get('status') == 'selected':
        if len(selected) != 1 or not set(selected) <= set(row['candidate_ids']):
            raise ValueError('Final selection outside actual candidates')
    elif selected:
        raise ValueError('Non-selected status contains menus')
    return selected

def production_vectors(model_dir, catalog):
    """Use unchanged production closure. Empty temporary cache forces fresh encoding."""
    spec = importlib.util.spec_from_file_location('production_e5', ROOT/'scripts/semantic/server.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    captured = {}
    class CaptureServer:
        def __init__(self, address, handler):
            closure = dict(zip(handler.do_POST.__code__.co_freevars,
                               [cell.cell_contents for cell in handler.do_POST.__closure__]))
            captured.update(encode=closure['encode'], vectors=closure['vectors'])
        def serve_forever(self):
            pass
    original_argv = sys.argv[:]
    try:
        with tempfile.TemporaryDirectory(prefix='e5-umap-model-') as temporary:
            temporary = Path(temporary)
            manifest = json.loads((ROOT/'scripts/semantic/model_manifest.json').read_text())
            for name in manifest['files']:
                (temporary/name).symlink_to((model_dir/name).resolve())
            module.ThreadingHTTPServer = CaptureServer
            sys.argv = ['server.py', '--model-dir', str(temporary), '--catalog', str(catalog)]
            module.main()
    finally:
        sys.argv = original_argv
    return captured['vectors'], captured['encode'], module

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--model-dir', type=Path, required=True)
    p.add_argument('--catalog', type=Path, default=ROOT/'src/main/resources/kb_starbanking_menu_structure_cleaned.json')
    p.add_argument('--evidence', type=Path, default=ROOT/'docs/menu-e5-jev-evaluation.json')
    p.add_argument('--examples', type=int, nargs='+', default=[2, 0, 9])
    p.add_argument('--top-k', type=int, default=40)
    p.add_argument('--seed', type=int, default=42)
    p.add_argument('--neighbors', type=int, default=15)
    p.add_argument('--min-dist', type=float, default=.1)
    p.add_argument('--clusters', type=int, default=12)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    if args.output.exists() and any(args.output.iterdir()):
        raise ValueError('Refuse to overwrite output; choose an empty directory')
    os.environ.setdefault('NUMBA_NUM_THREADS', '1')
    os.environ.setdefault('TOKENIZERS_PARALLELISM', 'false')
    os.environ.setdefault('LOKY_MAX_CPU_COUNT', '1')
    os.environ.setdefault('MPLCONFIGDIR', str(Path(tempfile.gettempdir())/'kkbb-umap-mpl'))
    import numpy as np
    import umap
    from scipy.cluster.vq import kmeans2
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    import plotly.graph_objects as go
    fonts = {f.name for f in font_manager.fontManager.ttflist}
    for name in ['AppleGothic', 'NanumGothic', 'Noto Sans CJK KR']:
        if name in fonts:
            plt.rcParams['font.family'] = name
            break
    plt.rcParams['axes.unicode_minus'] = False
    raw = args.catalog.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    menus = json.loads(raw)['menus']
    ids = [m['id'] for m in menus]
    index = {mid: i for i, mid in enumerate(ids)}
    evidence = json.loads(args.evidence.read_text())
    vectors, encode, module = production_vectors(args.model_dir, args.catalog)
    if vectors.shape != (len(menus), 384) or not np.isfinite(vectors).all():
        raise ValueError('Invalid production vectors')
    if not np.allclose(np.linalg.norm(vectors, axis=1), 1, atol=1e-5):
        raise ValueError('Vectors are not normalized')
    examples = []
    for example_index in args.examples:
        row = evidence['results'][example_index]
        query_vector = encode(['query: '+row['query']])[0]
        scores = np.einsum('ij,j->i', vectors, query_vector, optimize=False)
        order = np.argsort(-scores, kind='stable')
        ranking = [ids[i] for i in order]
        selected = validate_trace(evidence, row, digest, ranking, args.top_k)
        examples.append({'query': row['query'], 'status': row['status'], 'selected_ids': selected,
                         'evidence_index': example_index,
                         'candidates':[{'id':ids[i], 'rank':rank, 'cosine':float(scores[i]), 'name':menus[i]['name']} for rank,i in enumerate(order[:args.top_k],1)]})
        print('Verified fresh E5 candidates against actual JEV trace:', example_index, flush=True)
    coordinates = umap.UMAP(n_neighbors=args.neighbors, min_dist=args.min_dist, metric='cosine',
                            n_components=2, random_state=args.seed, transform_seed=args.seed, n_jobs=1).fit_transform(vectors)
    with np.errstate(all='raise'):
        centers, labels = kmeans2(vectors.astype(np.float64), args.clusters, iter=100, minit='points', seed=args.seed, missing='raise')
    if not np.isfinite(centers).all() or not np.isfinite(coordinates).all():
        raise ValueError('Non-finite cluster centers or UMAP coordinates')
    args.output.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(args.output/'embeddings.npz', ids=np.array(ids), vectors=vectors)
    points = [{'id':m['id'], 'name':m['name'], 'x':float(coordinates[i,0]), 'y':float(coordinates[i,1]), 'cluster':int(labels[i])} for i,m in enumerate(menus)]
    payload = {'catalog_sha256':digest, 'points':points, 'examples':examples}
    (args.output/'data.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2)+'\n')
    def base_plot(ax):
        ax.scatter(coordinates[:,0], coordinates[:,1], c=labels, cmap='tab20', s=22, alpha=.65, linewidths=0)
        ax.set(xticks=[], yticks=[], xlabel='UMAP 1', ylabel='UMAP 2')
        ax.spines[['top','right']].set_visible(False)
    fig, ax = plt.subplots(figsize=(12,8))
    base_plot(ax)
    ax.set_title(f'E5 금융 메뉴 {len(menus)}개 · 전체 분포', fontsize=19, loc='left', pad=20)
    fig.text(.08,.025, 'Colors: KMeans on original 384D E5 vectors (12 groups). 2D distance is not cosine similarity.',fontsize=10)
    fig.savefig(args.output/'overview.png', dpi=180, bbox_inches='tight')
    plt.close(fig)
    traces=[]
    for i in range(args.clusters):
        subset=[j for j,x in enumerate(labels) if x==i]
        traces.append(go.Scatter(x=coordinates[subset,0], y=coordinates[subset,1], mode='markers', name=f'Cluster {i+1}',
            marker={'size':7,'opacity':.55}, text=[html.escape(menus[j]['name'])+'<br>'+ids[j] for j in subset], hovertemplate='%{text}<extra></extra>'))
    for n, example in enumerate(examples):
        selected=example['selected_ids']
        candidate_indices=[index[c['id']] for c in example['candidates']]
        selected_indices=[index[x] for x in selected]
        fig, axes=plt.subplots(1,2,figsize=(16,8),gridspec_kw={'width_ratios':[1.6,1]})
        ax, side=axes
        base_plot(ax)
        ax.scatter(coordinates[candidate_indices,0],coordinates[candidate_indices,1],s=100,facecolors='none',edgecolors='#125cdb',linewidths=1.5,label=f'E5 Top-{args.top_k}')
        ax.scatter(coordinates[selected_indices,0],coordinates[selected_indices,1],s=350,c='#ef482f',marker='*',edgecolors='#471409',label='JEV selected (recorded)')
        for rank,j in enumerate(candidate_indices[:10],1):
            ax.annotate(str(rank),coordinates[j],xytext=(4,4),textcoords='offset points',fontsize=9)
        ax.legend(loc='lower left')
        side.axis('off')
        details=['실제 E5 Top-10 / cosine','']+[f"{c['rank']:2}. {c['name'][:23]}  {c['cosine']:.4f}" for c in example['candidates'][:10]]
        details+=['','JEV 최종 선택 (기존 실측 재생)']+[menus[index[x]]['name'] for x in selected]
        side.text(0,.92,'\n'.join(details),va='top',fontsize=11,linespacing=1.7)
        fig.suptitle(example['query'],fontsize=17,x=.06,ha='left')
        fig.text(.06,.025,'Blue: fresh E5 candidates. Star: actual JEV result recorded '+evidence['started_at'][:10]+'. UMAP distance ≠ cosine.',fontsize=10)
        fig.savefig(args.output/f'example-{n+1}.png',dpi=180,bbox_inches='tight')
        plt.close(fig)
        traces.extend([
            go.Scatter(x=coordinates[candidate_indices,0],y=coordinates[candidate_indices,1],mode='markers',name=f'E5 Top-{args.top_k}',visible=n==0,
                marker={'size':13,'color':'#1265ea','symbol':'circle-open','line':{'width':2}},
                text=[f"{c['rank']}. {html.escape(c['name'])}<br>{c['id']}<br>cosine {c['cosine']:.6f}" for c in example['candidates']],hovertemplate='%{text}<extra></extra>'),
            go.Scatter(x=coordinates[selected_indices,0],y=coordinates[selected_indices,1],mode='markers',name='Actual JEV (recorded)',visible=n==0,
                marker={'size':22,'color':'#ef482f','symbol':'star'},text=[html.escape(menus[j]['name']) for j in selected_indices],hovertemplate='%{text}<extra></extra>')])
    buttons=[]
    for n,example in enumerate(examples):
        visible=[True]*args.clusters + [j//2==n for j in range(len(examples)*2)]
        buttons.append({'label':example['query'],'method':'update','args':[{'visible':visible},{'title':{'text':html.escape(example['query'])}}]})
    figure=go.Figure(traces)
    figure.update_layout(title=examples[0]['query'],template='plotly_white',height=850,
        xaxis={'title':'UMAP 1','showticklabels':False},yaxis={'title':'UMAP 2','showticklabels':False},
        updatemenus=[{'buttons':buttons,'x':0,'y':1.17,'xanchor':'left'}],margin={'t':170,'b':100},
        annotations=[{'text':'585 real E5 vectors · colors: 384D KMeans · blue: fresh Top-40 · star: recorded JEV<br>2D distance is not cosine. Hover shows original cosine and rank. JEV date: '+evidence['started_at'][:10], 'xref':'paper','yref':'paper','x':0,'y':-0.09,'showarrow':False,'xanchor':'left'}])
    figure.write_html(args.output/'e5_umap.html',include_plotlyjs=True,full_html=True)
    metadata={'model':module.MODEL,'revision':module.REVISION,'catalog_sha256':digest,
        'model_manifest':json.loads((ROOT/'scripts/semantic/model_manifest.json').read_text()),
        'server_sha256':sha(ROOT/'scripts/semantic/server.py'),'evidence_sha256':sha(args.evidence),
        'evidence_started_at':evidence['started_at'],'evidence_model':evidence['requested_model'],
        'jev_mode':'replay of recorded actual E5→JEV evaluation, no new JEV calls',
        'embedding_mode':'fresh inference through unchanged production encoder; no preexisting cache used',
        'umap':{'seed':args.seed,'neighbors':args.neighbors,'min_dist':args.min_dist,'metric':'cosine','n_jobs':1},
        'clusters':{'algorithm':'KMeans on 384D normalized vectors','count':args.clusters,'seed':args.seed,'iterations':100,'initialization':'sampled actual points','implementation':'scipy.cluster.vq.kmeans2'},
        'python':platform.python_version(),'platform':platform.platform(),
        'outputs':{f.name:sha(f) for f in args.output.iterdir() if f.is_file()}}
    (args.output/'metadata.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n')
    print(f'Generated {len(points)} real E5 points, {len(examples)} validated E5/JEV examples',flush=True)

if __name__ == '__main__':
    main()
