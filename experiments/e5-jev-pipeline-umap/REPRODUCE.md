# 실제 E5→JEV 단계 UMAP 재현

`python -m pip install -r experiments/e5-jev-pipeline-umap/requirements.txt`

`MPLCONFIGDIR=/tmp/kkbb-mplconfig python experiments/e5-jev-pipeline-umap/render.py`

저장된실제585개E5 UMAP좌표(points.json)와실제S01_03 JEV응답(trace.json)을재생한다. 새API호출이나가상벡터생성없음. 동일좌표의전체585개→E5 Top80+어휘보완1개→MMR10개→최종3개를나타낸다. 개별적합도컷.30,최종Choiceconfidence하한없음.

원래임베딩·UMAP투영부터생성하려면기본브랜치에서기존PR#26으로병합된visualization/generate_umap.py를사용한다. 이PR의render.py는그때생성한실제고정좌표를검증후재사용한다. 당시아티팩트의모델revision·카탈로그hash·원본datahash는embedding-provenance.json에보존된다. PNG는설명용투영이며UMAP에서검색하는구조가아니다.

한국어폰트는macOS의Apple SD Gothic Neo를사용한다. 다른환경에서는matplotlib에설치된한국어폰트로지정하면된다. HTML은브라우저에서직접열수있고네트워크없이메뉴이름·E5순위·JEV점수를확인한다. 같은데이터로Figma에그린편집형도형링크: https://www.figma.com/design/hW2FEx2HREkWZSIQR4qJqf/2026-KB-AI-Challenge?node-id=879-11
