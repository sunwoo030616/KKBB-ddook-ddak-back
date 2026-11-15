# coding: utf-8
"""User-approved situation references; never import this file from inference code."""
import json,itertools,re,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
catalog={m['id']:m for m in json.loads((ROOT/'src/main/resources/kb_starbanking_menu_structure_cleaned.json').read_text())['menus']}
ids=lambda ns:sorted(f'kb_menu_{n:04d}' for n in ns)
def optional_sets(required_options,optional=()):
 result=[]
 for choice in itertools.product(*required_options):
  for size in range(min(2,len(optional))+1):
   for extra in itertools.combinations(optional,size):result.append(ids(set(choice)|set(extra)))
 return sorted({tuple(x) for x in result})
definition={
 'S01':('해외여행',[[323],[413,608,603],[602]],[612],['환전 준비','해외 결제 준비','여행보험 검토']),
 'S02':('차 없는 국내 1박여행',[[384],[604]],[],['철도 이동 준비','숙박 준비']),
 'S03':('카페 창업',[[630],[17]],[629,626],['사업자 금융 기반','정책 지원 탐색']),
 'S04':('첫 주택 구매',[[588,594],[591]],[586,587],['주택 가격 확인','부동산 세금 검토']),
 'S05':('보유 차량 판매',[[597,595],[596]],[],['차량 가격 확인','판매 진입']),
 'S06':('은퇴 준비',[[173],[176]],[175,260],['기존 연금 정보 파악','은퇴 상담']),
 'S07':('국민 신용카드 분실·현금 필요',[[554],[210,211]],[],['분실 카드 사용 차단','카드 없는 현금 마련']),
 'S08':('준비 일부 완료한 해외 출장',[[385],[612]],[],['만료 여권 재발급','해외 통신 준비']),
 'S09':('가게 매출·지원 고민',[[18],[17,19]],[],['가게 매출·정산 파악','정책·세금·고용 지원 탐색']),
 'S10':('흩어진 금융 자산 파악',[[164],[260]],[],['다른 금융 연결','전체 자산 파악'])}
queries={
'S01':[
'이번 겨울에는 일본 여행을 한번 가보고 싶어. 은행 앱에서 준비를 도와줘.',
'다음 달에 처음 일본으로 놀러 가려는데 뭘 준비하면 좋을까?',
'휴가 때 오사카에 가볼 생각이야. 출발 전에 은행에서 챙길 걸 알려줘.',
'친구랑 도쿄 여행을 계획 중인데 금융 쪽 준비가 막막해.',
'일본에 며칠 다녀오려고 해. 스타뱅킹으로 준비할 수 있는 게 있을까?',
'부모님과 일본에 놀러 가기로 했어. 여행 전에 챙겨둘 걸 추천해 줘.',
'혼자 일본으로 첫 해외여행을 갈까 해. 은행 앱이 도와줄 수 있을까?',
'후쿠오카로 주말 여행을 떠나려는데 은행에서 미리 준비할 걸 보고 싶어.',
'연휴에 일본 가기로 했는데 아직 여행 준비를 시작도 못 했어.',
'일본행 비행기만 잡아뒀어. 이제 은행 앱에서 여행 준비를 시작하고 싶어.'],
'S02':[
'자가용은 없고 부모님 모시고 부산에서 하룻밤 쉬다 오려고 해.',
'차 없이 부산으로 가족 나들이를 가서 1박 하고 돌아올 생각이야.',
'부모님과 부산 여행을 계획 중이야. 운전할 차는 없고 하루 자고 올 거야.',
'이번 주말 부모님 모시고 부산에 다녀오려 해. 차는 없고 1박 일정이야.',
'우리 가족이 차 없이 부산에 가서 하루 머물다가 오려고 하는데 준비를 도와줘.',
'부산에서 부모님과 1박 2일 보내려고 해. 우리 집에는 자가용이 없어.',
'차 없이 부모님과 부산을 둘러보고 하루 자고 오는 일정을 잡고 싶어.',
'가족이랑 부산에서 하룻밤 보내려는데 차가 없어. 앱으로 준비할 걸 알려줘.',
'부모님 부산 구경을 시켜드리고 싶은데 차 없이 가서 하루 쉬다 올 예정이야.',
'부산으로 부모님과 짧게 여행 갈래. 자동차는 없고 하루 묵는 일정이야.'],
'S03':[
'작은 카페를 처음 열려고 하는데 은행에서 어떤 준비를 도와줄 수 있을까?',
'직장 그만두고 동네에 카페를 차려보려고 해. 처음이라 준비가 막막해.',
'생애 처음으로 카페 사장이 되려고 해. 은행 앱에서 챙겨볼 걸 알려줘.',
'조그만 커피 가게를 창업하려는 중이야. 금융 쪽 준비를 시작하고 싶어.',
'개인사업은 처음인데 카페 오픈을 앞두고 있어. 은행이 도와줄 일이 있을까?',
'회사원으로만 살다가 작은 카페를 시작하려니 은행 준비부터 모르겠어.',
'동네 커피숍을 새로 열 계획이야. 처음 창업하는 사람에게 필요한 걸 보여줘.',
'카페 창업을 준비 중인데 은행 앱에서 시작할 수 있는 일을 추천해 줘.',
'작은 카페를 차릴 예정이야. 초보 사장이라 돈과 은행 업무 준비가 걱정돼.',
'첫 장사를 카페로 시작하려고 해. 은행에서 미리 챙기면 좋을 게 뭐야?'],
'S04':[
'처음으로 집을 사려고 알아보는 중이야. 은행 앱에서 준비를 도와줘.',
'내 집을 처음 마련해 보려는데 어디서부터 살펴봐야 할지 모르겠어.',
'전세를 벗어나 생애 첫 집을 사려고 해. 은행에서 챙길 걸 알려줘.',
'첫 주택 구매를 고민하고 있어. 부동산 쪽으로 준비할 기능을 보여줘.',
'살 집을 처음 매수하려고 알아보는데 은행 앱이 도움을 줄 수 있을까?',
'무주택으로 지내다가 처음 집을 살 계획을 세우고 있어.',
'내 명의로 첫 집을 사려는데 준비 단계에서 볼 만한 걸 추천해 줘.',
'주택 매수를 한 번도 해본 적이 없어. 첫 집 마련 준비를 시작하려고 해.',
'처음 자가를 마련하려는 중이야. 은행 앱에서 무엇을 살펴보면 좋을까?',
'가족이 살 첫 집을 매수하려고 해. 준비를 도와줄 은행 기능이 필요해.'],
'S05':[
'몇 년 타던 차를 이제 팔려고 하는데 은행 앱에서 도와줄 수 있어?',
'내가 타던 자동차를 처분할 생각이야. 어디부터 알아보면 좋을까?',
'지금 가지고 있는 차를 중고로 내놓으려고 해. 준비를 도와줘.',
'오래 타던 자가용을 팔아보려는데 처음이라 잘 모르겠어.',
'내 차를 판매하려고 생각 중이야. 앱에서 챙겨볼 걸 알려줘.',
'차를 더는 안 타게 돼서 가지고 있던 차를 정리하려고 해.',
'보유 중인 자동차를 팔고 싶어. 은행 앱에도 관련 도움이 있을까?',
'내가 운전하던 차를 다른 사람에게 팔 계획이라 준비를 시작하려고 해.',
'자가용을 중고로 처분해 보려는데 스타뱅킹에서 시작할 수 있을까?',
'타고 다니던 차를 내놓고 싶어. 판매 준비에 도움 되는 기능을 찾아줘.'],
'S06':[
'은퇴가 가까워져서 노후 준비를 해보려고 해. 은행에서 도와줄 수 있을까?',
'몇 년 뒤면 직장을 그만둘 나이라 노후가 걱정돼. 준비를 시작하고 싶어.',
'정년이 얼마 안 남았는데 은퇴 이후를 어떻게 준비해야 할지 막막해.',
'퇴직할 날이 다가오니 노후 살림이 걱정돼. 은행 앱으로 준비할 걸 알려줘.',
'은퇴를 앞두고 있어. 앞으로의 생활 준비에 도움이 되는 기능을 보고 싶어.',
'곧 정년퇴직을 하게 돼서 노후 준비를 차근차근 시작하려고 해.',
'은퇴 이후 생활이 걱정되는데 스타뱅킹에서 먼저 살펴볼 걸 알려줘.',
'직장 생활이 끝나갈 때가 돼서 노후 대비를 점검하고 싶어.',
'퇴직 후를 제대로 준비했는지 자신이 없어. 은행에서 도움받을 곳이 있을까?',
'정년을 앞둔 사람에게 필요한 노후 준비를 은행 앱에서 시작해 보고 싶어.'],
'S07':[
'국민 신용카드 든 지갑을 잃어버렸어. 당장 집에 갈 현금도 없어.',
'지갑을 통째로 잃었는데 안에 국민 신용카드가 있었고 수중에 현금도 없어.',
'국민 신용카드를 넣어 둔 지갑이 없어졌어. 밖인데 집에 갈 돈도 없는 상황이야.',
'밖에서 지갑을 분실했어. 국민 신용카드도 같이 사라졌고 지금 현금이 한 푼도 없어.',
'국민 신용카드가 들어 있던 지갑을 도난당한 것 같아. 현금도 없이 밖에 있어.',
'국민 신용카드와 현금을 넣은 지갑이 사라져서 당장 귀가도 막막해.',
'집에 가려는데 지갑을 잃어버렸어. 국민 신용카드도 없고 현금도 없어.',
'국민 신용카드가 든 지갑을 어디서 잃었는지 모르겠어. 지금 쓸 현금도 없어.',
'지갑을 분실해서 국민 신용카드까지 없어졌고 당장 현금이 필요한 상태야.',
'국민 신용카드를 지갑째 잃었는데 밖에 나와 있고 현금이 없어서 난감해.'],
'S08':[
'다음 달 해외 출장인데 여권이 만료됐고 리브모바일을 쓰고 있어. 돈과 보험 준비는 끝났어.',
'해외 출장을 앞뒀는데 여권 유효기간이 지나버렸어. 리브모바일 이용 중이고 결제 수단과 보험은 준비했어.',
'외국으로 출장을 가야 하는데 여권이 만료된 걸 이제 봤어. 폰은 리브모바일이고 돈과 보험은 챙겨뒀어.',
'해외 출장 준비 중이야. 여권은 만료됐고 리브모바일을 써. 돈 쓸 준비와 여행보험은 이미 마쳤어.',
'회사 일로 출국해야 해. 만료된 여권을 갖고 있고 리브모바일 이용자야. 자금과 보험 준비는 끝냈어.',
'해외 출장 일정이 생겼어. 여권이 만료된 상태고 휴대폰은 리브모바일이야. 결제와 보험은 다 챙겼어.',
'리브모바일을 쓰는 중인데 해외 출장을 가게 됐어. 여권이 만료됐고 돈과 보험 쪽은 준비 완료야.',
'여권 기간이 지난 채로 해외 출장이 잡혔어. 리브모바일 고객이고 돈 쓸 수단과 보험은 준비했어.',
'외국 출장 전에 남은 준비를 챙겨줘. 여권이 만료됐고 리브모바일을 쓰며 자금과 보험 준비는 마쳤어.',
'해외로 업무 출장을 가려 해. 여권 만료 상태이고 폰은 리브모바일, 돈과 보험은 이미 준비했어.'],
'S09':[
'가게 카드 매출은 늘었는데 돈이 제대로 들어오는지 모르겠고 은행에서 받을 도움도 궁금해.',
'장사를 하면서 카드로는 많이 팔았는데 돈 흐름이 불안해. 사장님에게 주는 지원도 알고 싶어.',
'우리 가게 카드 매출이 늘었는데 정작 손에 들어오는 돈이 헷갈려. 받을 수 있는 지원은 없을까?',
'카드 손님이 늘어난 가게를 운영하고 있어. 돈 들어오는 게 불안하고 사업자 지원도 궁금해.',
'가게에서 카드 결제는 많이 나오는데 입금되는 돈이 맞는지 모르겠어. 사장님 지원도 찾아보고 싶어.',
'장사 매출은 카드로 꽤 나오는데 돈이 제때 들어오는지 걱정돼. 지원받을 길도 궁금하고.',
'가게 카드 매출과 실제 들어오는 돈이 잘 맞는지 불안해. 은행에서 사업자에게 주는 도움도 필요해.',
'작은 가게를 하는데 카드 매출이 늘어도 돈이 잘 들어오는지 모르겠어. 지원받을 건 없을까?',
'우리 매장은 카드 손님이 많아졌어. 실제 돈이 들어오는 상황이 궁금하고 사장님 지원도 알아보고 싶어.',
'가게 카드 매출이 커졌는데 현금 흐름이 헷갈려. 정부나 은행에서 도와줄 만한 것도 궁금해.'],
'S10':[
'돈이 여러 은행에 흩어져 있고 이 앱에 계좌들을 아직 모아둔 적이 없어. 내 재산이 얼마인지 감이 안 와.',
'은행마다 돈이 따로 있는데 스타뱅킹에는 아직 다른 은행 계좌가 안 들어와 있어. 전체 살림을 알고 싶어.',
'여러 금융기관에 돈을 나눠 뒀어. 이 앱에 연결한 적은 없고 내 자산 규모가 잘 모르겠어.',
'은행별로 돈이 흩어져 있어서 총재산이 헷갈려. 스타뱅킹에 다른 은행은 아직 연결하지 않았어.',
'내 돈이 여러 은행에 나뉘어 있어. 이 앱에는 한 번도 모아본 적 없어서 전체 규모를 모르겠어.',
'금융기관을 여러 곳 쓰는데 이 앱과는 아직 연결 안 했어. 내 재산을 한눈에 이해하고 싶어.',
'다른 은행에도 돈이 있지만 스타뱅킹에는 등록한 적 없어. 전부 합쳐 얼마나 있는지 알고 싶어.',
'여러 은행에 재산이 나뉘어 있어 감이 안 와. 이 앱에는 타행 계좌를 아직 가져오지 않았어.',
'은행 여기저기에 돈이 있고 이 앱에 연동한 적은 없어. 내 금융 자산 상황을 파악하고 싶어.',
'스타뱅킹에서 다른 은행 계좌를 연결한 적이 없고 돈이 여기저기 흩어져 있어. 전체 재산이 궁금해.']}
rows=[];reference={}
for family,(title,required,optional,labels) in definition.items():
 acceptable=optional_sets(required,optional)
 if family=='S01':
  # Approved payment alternatives; a travel card may accompany one QR/general channel.
  payment=[{413},{608},{603},{413,603},{608,603}]
  acceptable=sorted({tuple(ids({323,602}|pay|extra)) for pay in payment for extra in [set(),{612}]})
 if family=='S09':acceptable=sorted({tuple(ids(x)) for x in [{18,17},{18,19},{18,17,19}]})
 canonical=ids([group[0] for group in required])
 groups=[{'outcome':label,'acceptable_ids':ids(ns)} for label,ns in zip(labels,required)]
 reference[family]={'title':title,'required_groups':groups,'optional_ids':ids(optional),'acceptable_sets':[list(s) for s in acceptable],'canonical_ids':canonical}
 assert len(queries[family])==10
 for j,q in enumerate(queries[family],1):
  rows.append({'case_id':f'{family}_{j:02d}','family_id':family,'situation':title,'query':q,'expected_ids':canonical,'expected_status':'ready','acceptable_sets':[list(s) for s in acceptable],'required_groups':groups,'split':'goal_only' if family in ['S01','S03','S04','S05','S06'] else 'situation_constraints','label_source':'user-approved draft reference; concrete allowed sets frozen before API run; not independent expert validation'})
assert len(rows)==100
normalize=lambda s:re.sub(r'\s+','',s).casefold()
assert len({normalize(r['query']) for r in rows})==100
for row in rows:
 for s in row['acceptable_sets']:assert len(s)>=2 and len(s)<=8 and len(s)==len(set(s)) and set(s)<=set(catalog)
old=[]
for p in [ROOT/'scripts/semantic/situation_v3/holdout-100.json',ROOT/'scripts/semantic/situation_v3/regression-300.json']:
 old.extend(json.loads(p.read_text()))
assert not {normalize(r['query']) for r in rows}&{normalize(r['query']) for r in old}
for name,data in [('cases.json',rows),('accepted-reference.json',reference)]:
 p=HERE/name;assert not p.exists();p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
(HERE/'labels.tsv').write_text('case_id\tfamily\tinput\tcanonical\taccepted_set_count\n'+''.join('\t'.join([r['case_id'],r['family_id'],r['query'],','.join(r['expected_ids']),str(len(r['acceptable_sets']))])+'\n' for r in rows))
print('Frozen 100 new situation questions, 10 approved families x10 expressions; 50 goal-only +50 circumstances; no API calls')
