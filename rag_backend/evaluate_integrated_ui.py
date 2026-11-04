"""Actual React-facing Spring/job/LLM contract regression, retaining every failure."""
import json
from pathlib import Path
import time
import uuid

import httpx

from .store import ROOT
from .canvas import REGISTRY


def run():
    base='http://127.0.0.1:8088/api/canvas/v2';output=ROOT/'reports'/'integrated-ui-v1.json'
    report={'scope':'Actual local neural models through Spring async job API; developer-authored regression, not independent benchmark.',
            'requests':[],'checks':[]}
    with httpx.Client(timeout=30) as client:
        for attempt in range(60):
            try:
                ready=client.get('http://127.0.0.1:8767/health')
                if ready.status_code==200 and ready.json().get('canvas_configured'):break
            except httpx.HTTPError:pass
            time.sleep(.5)
        else:raise RuntimeError('Local AI server is not ready')
        def submit(message,screen=None,calculation=None):
            request={'message':message,'expected_revision':screen['revision'] if screen else 0,
                     'supported_widgets':list(REGISTRY),'as_of':'2026-11-03'}
            if screen:request['session_id']=screen['session_id']
            if calculation:request['calculation']=calculation
            body={'request':request,'client_request_id':str(uuid.uuid4())};start=time.perf_counter()
            response=client.post(base+'/jobs',json=body);response.raise_for_status();job=response.json()
            duplicate=client.post(base+'/jobs',json=body);duplicate.raise_for_status()
            same_id=duplicate.json()['job_id']==job['job_id']
            stages=[]
            while time.perf_counter()-start<240:
                response=client.get(base+'/jobs/'+job['job_id']);response.raise_for_status();status=response.json()
                if not stages or stages[-1]!=status['stage']:stages.append(status['stage'])
                if status['status'] in ('completed','failed'):break
                time.sleep(.5)
            if status['status']!='completed':raise RuntimeError(str(status))
            result=status['result']
            report['requests'].append({'message':message,'response':result,'observed_stages':stages,
                                       'duplicate_job_reused':same_id,'wall_ms':round((time.perf_counter()-start)*1000,1)})
            output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
            print(json.dumps({'message':message,'status':result['status'],'widgets':[w['type'] for w in result.get('widgets',[])],
                              'context':result.get('context',{}),'stages':stages},ensure_ascii=False),flush=True)
            return result
        def check(label,condition):report['checks'].append({'name':label,'passed':bool(condition)})
        first=submit('일본 여행 갈 거야')
        check('destination_initial',first.get('context',{}).get('destination',{}).get('value')=='일본')
        if first['status']=='composed':
            second=submit('3박4일이야. 보험은 빼줘',first)
            kinds={w['type'] for w in second.get('widgets',[])}
            check('duration_merged',second.get('context',{}).get('trip_days',{}).get('value')==4)
            check('destination_preserved',second.get('context',{}).get('destination',{}).get('value')=='일본')
            check('insurance_removed','travel_insurance_widget' not in kinds)
            if second['status']=='composed':
                third=submit('2만엔으로 환전 금액을 바꿔줘',second)
                check('amount_currency',third.get('context',{}).get('amount',{}).get('value')=={'value':'20000','currency':'JPY'})
                check('duration_still_preserved',third.get('context',{}).get('trip_days',{}).get('value')==4)
        recovered=submit('분실 신고한 국민카드를 찾았어. 정지 해제 절차를 보여줘')
        check('recovery_not_freeze',{w['type'] for w in recovered.get('widgets',[])}=={'card_recovery_widget'})
        finance=submit('예금 중도해지와 담보대출 비용을 비교하고 예금보호 기준도 같이 보여줘')
        if finance['status']=='composed':
            calculated=submit('현재 화면은 유지하면서 입력 조건으로 예금 유지·해지 비용을 계산해줘',finance,
                {'kind':'funding_comparison','maturity_interest_net_won':'1000000','early_interest_net_won':'300000',
                 'loan_principal_won':'10000000','annual_loan_rate_percent':'3.65','loan_days':100,'extra_loan_cost_won':'10000'})
            node=next((w for w in calculated.get('widgets',[]) if w['type']=='funding_comparison_widget'),{})
            check('server_calculation',node.get('data',{}).get('values',{}).get('interest_difference_won')=='590000')
            check('evidence_widget_preserved',any(w['type']=='deposit_protection_widget' for w in calculated.get('widgets',[])))
        check('all_submissions_idempotent',all(r['duplicate_job_reused'] for r in report['requests']))
    report['summary']={'checks':len(report['checks']),'passed':sum(x['passed'] for x in report['checks']),
                       'requests':len(report['requests'])}
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report['summary']),flush=True)


if __name__=='__main__':run()
