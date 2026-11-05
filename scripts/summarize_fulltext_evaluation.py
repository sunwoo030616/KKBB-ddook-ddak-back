"""Summarize only complete, source-matched local evaluation artifacts."""
import hashlib
import json
from pathlib import Path
import statistics

ROOT=Path(__file__).resolve().parents[1]


def main():
    names={'regression':'fulltext-regression.json','preregistered':'fulltext-preregistered.json','external':'scifact-external-subset.json'}
    reports={key:json.loads((ROOT/'reports'/name).read_text()) for key,name in names.items()}
    transition=json.loads((ROOT/'reports/fulltext-scope-guard-transition.json').read_text())
    live=json.loads((ROOT/'reports/fulltext-platform-api.json').read_text())
    financial=json.loads((ROOT/'reports/fulltext-financial-service.json').read_text())
    if not all(financial['checks'].values()):raise ValueError('financial_service_check_failed')
    if not transition.get('complete') or not all(transition['checks'].values()) or not all(live['checks'].values()):
        raise ValueError('post_holdout_guard_not_verified')
    for label,report in reports.items():
        if report.get('complete') is not True:raise ValueError('incomplete_evaluation')
        for path,digest in report['backend_sha256'].items():
            current=hashlib.sha256((ROOT/path).read_bytes()).hexdigest()
            if current==digest:continue
            # Explicitly audited functional scope repair after the first holdout.
            # Never relabel that first-pass score as current/blind accuracy.
            if (label in ('regression','preregistered') and path==transition['source_path']
                and digest==transition['before_sha256'] and current==transition['after_sha256']
                and live['backend_sha256'].get(path)==current):continue
            raise ValueError('evaluated_source_changed:'+path)
    for label,report in reports.items():
        for name,digest in report.get('datasets',{}).items():
            if hashlib.sha256((ROOT/'data'/name).read_bytes()).hexdigest()!=digest:raise ValueError('evaluated_dataset_changed')
        for row in report['rows']:
            for step in row.get('graph',{}).get('trace',row.get('trace',[])):
                if step.get('prompt_sha256') and step.get('prompt_version'):
                    path=ROOT/'data/prompts'/('literature_adjudication.v'+step['prompt_version']+'.json')
                    if hashlib.sha256(path.read_bytes()).hexdigest()!=step['prompt_sha256']:raise ValueError('evaluated_prompt_changed')
    if reports['external']['protocol_sha256']!=hashlib.sha256((ROOT/'data/scifact_external_protocol.json').read_bytes()).hexdigest():
        raise ValueError('external_protocol_changed')
    r=reports['regression'];p=reports['preregistered'];x=reports['external'];core=[row for row in r['rows'] if row['dataset']!='literature_guard_cases.json']
    guard=[row for row in r['rows'] if row['dataset']=='literature_guard_cases.json']
    rows='\n'.join(f"| {row['id']} | {row['exact']} | {row['seconds']:.2f}초 | {row['citation_count']} |" for row in core if row['id'] in ('g3','v4'))
    failures='\n'.join(f"- {row['id']}: 누락 {row['missing_sources']}, 예상 밖 출처 {row['unexpected_sources']}" for row in r['rows']+p['rows'] if not row['exact']) or '- 해당 문항의 출처 집합 불일치 없음.'
    text=f'''# 본문·복수 인용 확장과 분리 평가 결과

제품은 채팅으로 금융 위젯 화면을 구성하는 서비스다. 이 문헌 검색 기능은 내부 연구·검토 도구이며 실제 금융 판단을 자동 승인하지 않는다.

## 개선 내용

- RAG·Speculative Decoding 공식 PDF의 첫 3페이지를 정규화해 버전별 지식 문서에 연결했다. 전체 논문 수집이 아니다.
- PDF SHA256, 추출기 버전, 페이지별 추출 텍스트 SHA256, 문서 전체 버전 hash와 정확한 시작/끝 위치를 보존한다. 위치는 PDF 바이트가 아니라 **정규화된 추출 텍스트 기준**이다.
- 초록으로 문서 후보를 좁힌 뒤, 본문을 다국어 임베딩 최대 8개와 영어 어휘 최대 2개 후보의 합집합으로 압축해 재순위한다. 입력 후보 문서 밖의 본문을 완전 탐색하는 구조는 아니다.
- 한 요청 절당 최대 한 문헌·두 인용, 요청당 최대 세 문헌·여섯 인용을 반환한다. 모델은 인용 슬롯만 고르고 ID·URL·hash·quote는 서버가 작성한다. 서로 다른 구간을 하나의 원문 인용으로 이어 붙이지 않는다.
- MCP 재조회에서도 각 인용의 현재 버전·텍스트·PDF 페이지 링크를 확인한다. 새 본문 후보가 선택되는 경우 생성 모델 검증을 생략하지 않는다.
- 긴 저자 주장 문장이 여러 구간으로 잘려도 뒤쪽의 제약 조건을 잃지 않도록 보완했다.

## 실제 결과

| 평가 | 결과 | 해석 |
| --- | --- | --- |
| 기존 핵심 문항 | {sum(row['exact'] for row in core)}/{len(core)} 출처 집합 일치 | 관찰·수정에 사용한 개발 회귀 검사 |
| 기존 추가 검사 | {sum(row['exact'] for row in guard)}/{len(guard)} | 개발자 작성 가드 문항 |
| 구현 전 확정한 별도 문항 | {p['summary']['exact']}/{p['summary']['n']} | 개발자 작성, 사전 고정한 분리 평가. 외부 사람이 새로 평가한 결과는 아님 |
| 외부 주석 SciFact 표본 | {x['summary']['document_hits']}/{x['summary']['n']} 문헌 일치 | 외부 연구자의 주석 사용; 200문서·10개 SUPPORT 주장 표본 |
| SciFact 근거 문장 전체 포함 | {x['summary']['any_gold_sentence_fully_covered']}/{x['summary']['n']} | 최소 한 정답 근거 문장을 인용 구간의 합집합이 완전히 포함 |
| SciFact 완전 근거 집합 포함 | {x['summary']['complete_gold_rationale_covered']}/{x['summary']['n']} | 허용된 대안 근거 집합 중 하나를 모두 포함 |

이전 초록 전용 결과는 핵심 22/24였다. 이번에는 두 문헌에 본문을 추가했으므로 **동일 자료 조건에서 모델만 개선한 성능 비교가 아니다.**

두 기존 누락 문항의 현재 측정:

| 문항 | 출처 집합 일치 | 지연 | 인용 수 |
| --- | --- | --- | --- |
{rows}

핵심 24문항 중앙값 {statistics.median(row['seconds'] for row in core):.2f}초. 가드 포함 기존 36문항 중앙값 {r['summary']['median_seconds']:.2f}초, 최댓값 {r['summary']['max_seconds']:.2f}초. 별도 12문항 중앙값 {p['summary']['median_seconds']:.2f}초. SciFact 표본 중앙값 {x['summary']['median_seconds']:.2f}초. 한 프로세스에서 순차 측정했으며 생성 결과 캐시는 껐다. 순위·임베딩·시스템 prefix 캐시는 사용할 수 있다. 이 값은 다수의 새 프로세스 반복 측정이나 서비스 SLA가 아니다.

각 평가의 exact offset·hash 검사: 회귀 {r['summary']['all_quotes_valid']}, 별도 문항 {p['summary']['all_quotes_valid']}, SciFact {x['summary']['all_quotes_valid']}. 원문 일치는 의미적 지지의 증명이 아니다.

## 사전 고정 평가에서 드러난 불일치

{failures}

`i11`은 최초 평가 후 승인·게시의 연속 명령을 범위 밖으로 분류하도록 수정했다. 최초 10/12 결과를 유지하며 이 문항은 이제 관찰한 회귀 사례다. 수정 파일은 scope guard 하나이며, 이전 36문항의 라우팅이 동일함을 별도로 확인했다. RAG의 새 표현인 `i01`은 아직 오답이며 결과를 본 뒤 검색 모델을 재튜닝하지 않았다.

실제 최종 API/MCP에서는 두 누락 사례의 문헌을 요청 절별로 확인하고 PDF 페이지·원문 위치를 재조회했다. 새 서버 첫 g3 HTTP 요청은 {live['rows'][0]['seconds']:.2f}초, 동일 요청 반복은 {live['rows'][1]['seconds']:.2f}초(생성 호출 0회), v4는 {live['rows'][2]['seconds']:.2f}초였다. 오프라인 7.86초·5.31초를 실제 API의 첫 요청 지연으로 쓰지 않는다. 서비스 프로세스는 화면 구성용 모델 자원도 함께 보유하므로 부하 조건이 다르다. 이 차이의 단일 원인을 추가 측정 없이 확정하지 않는다. 캐시 적중 trace에 남은 원래 생성 단계 정보는 새 추론 시간으로 해석하지 않는다. 승인 연속 명령은 `out_of_scope`, 생성 호출 0회로 확인했다. 최종 API·MCP 검사 {len(live['checks'])}개와 금융 화면 연동 검사 {len(financial['checks'])}개가 모두 통과했다.

SciFact에서는 실제 반환 문헌과 연구자가 주석한 근거 문장 포함률을 분리했다. 단순히 문헌을 맞혔다고 해당 주장 근거도 찾았다고 계산하지 않는다. 자세한 실패·지연·추적 정보는 보고서에 그대로 남겼다.

## 평가 분리와 한계

- 별도 12문항은 구현 전 커밋한 파일 SHA256을 검사하고 실행했다. 결과를 본 뒤 정답을 바꾸거나 재튜닝하지 않았다.
- [SciFact](https://github.com/allenai/scifact)의 dev 주석을 사용했다. 외부 정답 주석이지만 공개 데이터이며 사전학습 모델의 학습 데이터 포함 가능성을 배제하지 않는다.
- SciFact는 정답 문헌을 포함하도록 구성한 200문서 표본이다. 10개 단일 정답 SUPPORT 주장과 고정 seed의 무작위 방해 문서를 사용했다. 전체 5,183문서·전체 dev·공식 리더보드 점수가 아니며 CONTRADICT/NEI 분류를 평가하지 않았다. 한국어·금융 분야 일반화 수치도 아니다.
- 제품 문헌 30개 중 두 편만 본문을 확장했고, 참고문헌·전체 PDF를 구조적으로 분류한 상태는 아니다. 인용 지원 판단은 여전히 오류 가능성이 있다.
- v4 중첩 후보 프롬프트는 기존 h1을 깨뜨려 폐기했다. 실패 보고서를 보존하고, 검증된 v3 문구와 평면 후보 형식을 사용하는 v5 슬롯 계약으로 복구했다. v5는 각 슬롯이 개별 인용이며 같은 문헌의 슬롯이 둘일 수 있다.
- 모델은 지원 슬롯을 과다 선택할 수 있다. 서버 순위·후보 제한과 출처 검증은 보조 장치이며 자연어 함의 판별을 해결했다고 주장하지 않는다.
- Qwen3-4B와 로컬 임베딩·재순위 모델만 사용했으며 유료 API를 활성화하지 않았다. 외부 표본은 별도 DB에서 실행했다.

## 재현과 자료

- 실행: [본문·분리 평가 실행 안내](본문검색_평가_실행.md)
- 내부 회귀: [fulltext-regression.json](../reports/fulltext-regression.json)
- 사전 고정 문항: [fulltext-preregistered.json](../reports/fulltext-preregistered.json)
- 외부 주석 표본: [scifact-external-subset.json](../reports/scifact-external-subset.json)
- 실패한 v4: [fulltext-regression-v4-failed.json](../reports/fulltext-regression-v4-failed.json)
- 라이브 API·MCP: [fulltext-platform-api.json](../reports/fulltext-platform-api.json)
- 금융 화면 연동: [fulltext-financial-service.json](../reports/fulltext-financial-service.json)
- 평가 후 범위 수정 감사: [fulltext-scope-guard-transition.json](../reports/fulltext-scope-guard-transition.json)
- 새 추출 자료: [fulltext-ingestion.json](../reports/fulltext-ingestion.json)

SciFact 출처: Wadden et al., *Fact or Fiction: Verifying Scientific Claims*. Claims·evidence annotations: CC BY 4.0, corpus(S2ORC): ODC-By 1.0. 원본은 공식 배포처에서 내려받고 재배포 원문은 Git에 넣지 않았다.
'''
    (ROOT/'docs/본문_복수인용_분리평가_결과.md').write_text(text)
    print('source-matched summary written')

if __name__=='__main__':main()
