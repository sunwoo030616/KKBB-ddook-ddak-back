import json,time
from pathlib import Path
import httpx
cases=[
 ('finance','예금 중도해지와 담보대출의 비용을 비교하고 예금보호 기준도 같이 보여줘',{'funding_inputs_widget','funding_comparison_widget','deposit_protection_widget'}),
 ('loan','대출 원금과 금리를 입력해서 매달 납입액과 남은 잔액을 표로 보고 싶어',{'loan_inputs_widget','loan_repayment_schedule_widget'}),
 ('travel_mix','일본 여행 환전과 모임 회비 수납 현황을 같이 보여줘. 보험은 빼줘',{'travel_card_charge_widget','group_account_status'}),
 ('recovered','분실 신고했던 KB국민카드를 찾았어. 정지 해제 절차를 보여줘',{'card_recovery_widget'}),
 ('only_fx','미국 달러 환전 화면만 필요해. 다른 것은 넣지 마',{'travel_card_charge_widget'}),
 ('domestic','부산 국내여행인데 해외 환전이나 해외 QR결제는 필요 없어',set()),
 ('lost_cash','카드를 잃어버렸고 당장 현금도 필요해. 카드 정지와 카드 없는 출금 화면을 보여줘',{'card_freeze_all','atm_smart_withdrawal'}),
 ('group','동아리 회비 수납과 지출 리포트를 같이 보고 싶어',{'group_account_status','expense_report_widget'}),
]
report={'scope':'Actual local MLX model through localhost HTTP. Small developer-authored UI composition checks, not external benchmark.','cases':[]}
from .store import ROOT
output=ROOT/'reports'/'canvas-local-v3.json'
with httpx.Client(timeout=180) as client:
 health=client.get('http://127.0.0.1:8767/health');health.raise_for_status();report['health']=health.json()
 for id,message,gold in cases:
  response=client.post('http://127.0.0.1:8767/canvas/compose',json={'message':message,'as_of':'2026-11-02'})
  response.raise_for_status();result=response.json();selected={n['type'] for n in result['widgets']}
  report['cases'].append({'id':id,'message':message,'expected_widgets':sorted(gold),'actual_widgets':sorted(selected),
                          'exact_match':selected==gold,'response':result})
  output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
  print(json.dumps({'id':id,'status':result['status'],'selected':sorted(selected),'exact_match':selected==gold},ensure_ascii=False),flush=True)
 first=report['cases'][0]['response']
 if first['status']=='composed':
  revision=first['revision'];sid=first['session_id']
  response=client.post('http://127.0.0.1:8767/canvas/compose',json={'message':'기존 화면은 유지하고 대출 월 상환표도 추가해줘','session_id':sid,'expected_revision':revision,'as_of':'2026-11-02'})
  response.raise_for_status();second=response.json();report['followup_add']=second
  conflict=client.post('http://127.0.0.1:8767/canvas/compose',json={'message':'화면 수정','session_id':sid,'expected_revision':revision})
  assert conflict.status_code==409;report['stale_revision_http_status']=409
  if second['status']=='composed':
   response=client.post('http://127.0.0.1:8767/canvas/compose',json={'message':'기존 화면을 유지하면서 입력한 조건으로 예금 유지 해지 비용을 계산해줘', 'session_id':sid,'expected_revision':second['revision'],'as_of':'2026-11-02','calculation':{'kind':'funding_comparison','maturity_interest_net_won':'1000000','early_interest_net_won':'300000','loan_principal_won':'10000000','annual_loan_rate_percent':'3.65','loan_days':100,'extra_loan_cost_won':'10000'}})
   response.raise_for_status();report['followup_calculation']=response.json()
 report['summary']={'n':len(cases),'exact_match':sum(c['exact_match'] for c in report['cases'])}
 output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(report['summary']),flush=True)
