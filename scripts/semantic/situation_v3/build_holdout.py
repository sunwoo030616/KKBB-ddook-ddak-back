# coding: utf-8
"""Freeze synthetic contextual multi-outcome cases; no model calls or result-derived labels."""
import json,random,hashlib,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
catalog={m['id']:m for m in json.loads((ROOT/'src/main/resources/kb_starbanking_menu_structure_cleaned.json').read_text())['menus']}
# Each contextual case expresses separate observable outcomes, avoiding an arbitrary universal situation bundle.
families=[
('employment_docs',[493,492],['새 회사가 월급 받을 계좌 증빙과 현재 예금 잔액을 입증하는 서류를 각각 제출하래요. 두 서류를 준비해 주세요.','입사 서류 마감이라 급여 받을 통장 사본과 돈이 얼마나 있는지 은행 증명서를 함께 떼야 해요.']),
('lost_card_cash',[554,210],['국민 신용카드를 밖에서 잃어버렸고 당장 현금도 필요해요. 잃은 카드는 막고 카드 없이 돈을 찾는 방법을 열어 주세요.','지갑 속 국민 신용카드가 사라졌어요. 먼저 사용을 막고 통장도 카드도 없이 은행 기계에서 현금을 꺼내야 해요.']),
('found_card',[555,552],['분실로 막아 둔 국민 신용카드를 찾았어요. 다시 쓸 수 있게 풀고 그 사이 결제된 게 있는지도 보고 싶어요.','어제 잃어버려 정지한 국민 신용카드가 집에 있었네요. 사용 정지를 풀고 카드 이용 기록도 확인할래요.']),
('moving',[214,205],['이사 잔금을 보내야 하는데 하루 송금 가능액이 모자라요. 그 한도를 올리고 계좌에서 보낸 돈의 결과도 살펴볼래요.','집 계약 잔금일이에요. 은행 이체 한도를 먼저 늘리고 이전에 계좌로 송금한 결과를 따로 확인하려 해요.']),
('standing_order',[206,207],['새집 집주인에게 매달 보낼 돈을 자동으로 설정하고 예전 집으로 가던 자동 송금은 끊어야 해요.','월세 받을 사람이 바뀌었어요. 옛 자동이체는 종료하고 새 자동이체를 등록할래요.']),
('wrong_transfer',[205,519],['오픈뱅킹으로 돈을 보낸 상대를 잘못 골랐어요. 은행 계좌 송금 결과를 확인한 뒤 착오송금 반환을 신청할래요.','오픈뱅킹 이체가 잘못된 사람에게 갔어요. 계좌 이체 결과 조회와 잘못 보낸 돈 반환 신청이 둘 다 필요해요.']),
('claim',[570,571],['KB손해보험 병원비 보상을 새로 접수하고 지난번에 접수한 보상 건은 어디까지 진행됐는지 확인할래요.','치료비 영수증이 생겨 KB손해보험에 청구하려 해요. 예전에 낸 보험금 청구 기록도 같이 보고 싶어요.']),
('forest',[472,383],['휴양림에 남은 자리가 있는지 먼저 보고 자리가 있으면 예약 신청까지 할 수 있는 곳을 각각 열어 주세요.','가족과 숲에서 잘 거라 휴양림별 빈자리 조회와 숙박 예약을 둘 다 준비할래요.']),
('domestic_trip',[384,604],['이번엔 국내로 가요. KTX 좌석을 잡고 잘 숙소도 예약할 수 있게 두 곳을 찾아 주세요.','부모님 모시고 국내 여행을 가려는데 SRT 승차권과 숙박 예약을 함께 준비해야 해요.']),
('passport_roaming',[385,612],['해외 출장은 환전과 결제 준비가 끝났어요. 유효기간이 끝난 여권을 다시 만들고 휴대폰 해외 로밍만 신청할래요.','보험과 돈 준비는 다 했고 출국 전에 만료된 여권 재발급 절차와 리브모바일 로밍 신청만 남았어요.']),
('fx_tracking',[316,317],['달러 값이 궁금해서 현재 환율을 보고 앞으로 찾기 쉽도록 그 통화를 관심 목록에 넣고 싶어요.','엔화 시세를 확인한 다음 자주 보는 통화로 등록할래요. 두 기능 모두 찾아 주세요.']),
('fx_collection',[324,329],['전에 신청한 환전 건을 관리하고 아직 은행에서 받아 가지 않은 외화가 있는지도 따로 확인할래요.','이미 바꿔 둔 외화가 있어요. 환전 신청 내역 관리와 미수령 외화 내역 조회가 필요해요.']),
('lost_security',[512,511],['가방에서 OTP 기계와 보안카드를 둘 다 잃어버렸어요. 각각 사고 접수할 수 있는 곳을 열어 주세요.','인증에 쓰던 OTP와 보안카드가 없어졌어요. 둘 다 분실 신고를 해야 해요.']),
('lost_book',[509,517],['통장과 도장을 잃어 사고 신고를 접수하고 예전에 신고된 통장·인감 사고 기록도 확인할래요.','인감과 통장이 없어졌어요. 새 분실 신고와 통장·인감 신고 이력 조회를 각각 진행할래요.']),
('business',[626,18],['가게 카드 매출이 입금될 은행 계좌를 바꾸고 실제 매출 입금 상황도 보고 싶어요.','매장 카드대금 받을 계좌가 달라져 변경해야 해요. 카드 매출 정산금이 들어왔는지도 별도로 확인할래요.']),
('business_support',[19,629],['가게에서 놓친 세금 환급이나 고용 지원금이 있는지 조회하고 사업 운영 문제는 소상공인컨설팅 전문가와 상담 예약을 하고 싶어요.','사장으로서 세금 환급·고용 지원금 예상액을 알아보고 소상공인컨설팅 상담 신청도 함께 할래요.']),
('business_setup',[630,619],['새 가게를 열어 사업자 통장과 기업뱅킹을 만들고 기존에 쓰는 사업용 계좌도 한곳에 모아 설정하고 싶어요.','창업 준비로 사업자용 통장·기업뱅킹 신규 개설과 사업용계좌 설정이 각각 필요해요.']),
('security_restore',[514,516],['찾은 보안카드와 현금·직불카드가 둘 다 분실 등록 상태예요. 각각 등록을 풀어야 해요.','분실 신고했던 보안카드랑 현금카드를 찾았어요. 보안카드 해제와 현금·직불카드 해제를 함께 처리할래요.']),
('car',[597,596],['타던 차를 팔 생각이에요. 현재 중고차 값을 조회하고 팔아줘 차차차로 판매 접수도 해 볼래요.','차를 처분하기 전에 내 차량 시세를 알아보고 내 차 판매 서비스도 열어 주세요.']),
('housing',[588,591],['집 매수를 고민 중인데 가격 시세와 부동산 세금을 계산하는 기능을 각각 보고 싶어요.','이사 갈 집의 부동산 시세를 조회하고 취득세 같은 부동산 세금도 계산할래요.']),
('taxes',[227,228],['고지서가 두 장 왔는데 하나는 국세이고 다른 하나는 지방세예요. 각각 납부할 곳을 찾아 주세요.','국세와 지방세를 모두 내야 해요. 두 세금 납부 기능을 나눠서 열어 주세요.']),
('receipts',[507,508],['은행 창구 거래 영수증은 전자로 받고 싶고 물건 산 카드·현금 영수증도 한곳에 모아 관리할래요.','창구 전자영수증 수신 설정과 결제 구매영수증 통합 관리 시작을 함께 할래요.']),
('stocks',[541,542],['KB증권으로 낸 주식 주문 기록을 확인하고 관심종목 목록도 열어 주세요.','증권 주문이 어떻게 들어갔는지 보고 내가 관심 등록한 종목들도 확인할래요.']),
('account_product',[5,3],['중간에 멈춘 상품 가입을 이어서 진행하고 다른 상품 하나는 이름으로 직접 검색해 보고 싶어요.','하던 금융상품 가입 절차를 다시 찾고 별도로 상품 키워드 직접 검색도 할래요.']),
('pension',[70,72],['개인형 IRP를 새로 가입하는 곳과 퇴직연금 투자성향을 분석해 운용상품을 보는 곳을 각각 열어 주세요.','노후 준비로 개인형 IRP 신규 가입을 하고 퇴직연금 투자성향 분석·상품 확인도 따로 진행할래요.'])]
rows=[]
for family,nums,queries in families:
 ids=[f'kb_menu_{n:04d}' for n in nums]
 for mid in ids:assert mid in catalog,mid
 for j,q in enumerate(queries):rows.append(dict(case_id=f'context_{family}_{j+1}',query=q,expected_ids=ids,expected_status='ready',split='contextual_multi',family_id=family,label_source='catalog-authored synthetic contextual multi-outcome; not independent human review'))
# New random cross-domain combinations include 2–5 outcomes. None are selected from results.
rng=random.Random(2026111503);pool=sorted({f'kb_menu_{n:04d}' for _,nums,_ in families for n in nums})
for i in range(50):
 ids=rng.sample(pool,2+i%4);names=[catalog[x]['name'] for x in ids]
 conjunction=[' 그리고 ','; ','도 필요하고 ','와 별도로 ',' / '][i%5]
 q=['다음 업무를 각각 처리해 줘: ','아래 기능을 빠짐없이 찾아줘. ','오늘 처리할 일이 여러 개야. ','한 화면에 필요한 메뉴를 모두 보여줘: ','하나만 고르지 말고 전부 찾아줘: '][i%5]+conjunction.join(names)
 rows.append(dict(case_id=f'explicit_{i+1:03d}',query=q,expected_ids=ids,expected_status='ready',split='explicit_multi',family_id='cross_domain_'+str(i+1),label_source='catalog-authored synthetic named multi-outcome; not independent human review'))
normalized=lambda q:re.sub(r'\s+','',q).lower()
old=[r for n in ['regression-300.json','fresh-100.json'] for r in json.loads((ROOT/'scripts/semantic/situation_v2'/n).read_text())]
assert len(rows)==100 and len({normalized(r['query']) for r in rows})==100
assert not {normalized(r['query']) for r in rows}&{normalized(r['query']) for r in old}
output=HERE/'holdout-100.json'
if output.exists():raise RuntimeError('Do not overwrite frozen labels')
output.write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
(HERE/'holdout-labels.tsv').write_text('case_id\tfamily_id\tsplit\tquery\texpected_ids\n'+''.join('\t'.join([r['case_id'],r['family_id'],r['split'],r['query'],','.join(r['expected_ids'])])+'\n' for r in rows))
print('Frozen 100 unique multi-outcome cases: explicit 50, contextual 50; 25 contextual families')
