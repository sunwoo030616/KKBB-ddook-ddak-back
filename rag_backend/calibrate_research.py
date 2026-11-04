"""Select a relevance-abstention threshold from dev only; never reads test outputs."""
import hashlib,json
from pathlib import Path
from .store import ROOT


def calibrate():
    source=ROOT/'reports'/'research-dev-v1.json';raw=source.read_bytes();report=json.loads(raw)
    if report['split']!='dev':raise ValueError('Calibration requires development split')
    rows=[{'id':c['id'],'answerable':bool(c['gold_ids']),
           'max_relevance':max(c['variants']['decompose_rerank']['scores'],default=0)} for c in report['cases']]
    grid=[0.01,0.05,0.1,0.2,0.3,0.5]
    scores=[{'threshold':t,'correct':sum((r['max_relevance']>=t)==r['answerable'] for r in rows)} for t in grid]
    chosen=max(scores,key=lambda r:(r['correct'],-r['threshold']))['threshold']
    result={'threshold':chosen,'selection':'maximize dev answerability, smallest threshold on ties',
            'dev_report_sha256':hashlib.sha256(raw).hexdigest(),'dataset_sha256':report['dataset_sha256'],
            'dev_cases':rows,'grid':scores,
            'limits':'Only six development cases and one negative. Exploratory calibration, not a calibrated correctness probability.'}
    (ROOT/'data'/'research_calibration.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
    return result

if __name__=='__main__':calibrate()
