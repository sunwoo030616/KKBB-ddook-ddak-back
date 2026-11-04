import json

import pytest

from rag_backend.prompt_registry import load_prompt


@pytest.mark.parametrize('name,version',[('../private','3'),('literature_adjudication','../3'),('literature_adjudication','3/../../private')])
def test_mcp_prompt_identifiers_cannot_escape_registry(name,version):
    with pytest.raises(ValueError,match='invalid_prompt_identifier'):load_prompt(name,version)


def test_wrong_embedded_prompt_identity_is_rejected(tmp_path,monkeypatch):
    folder=tmp_path/'data/prompts';folder.mkdir(parents=True)
    (folder/'literature_adjudication.v3.json').write_text(json.dumps({'name':'different','version':'3','text':'A sufficiently long synthetic prompt.'}))
    monkeypatch.setattr('rag_backend.prompt_registry.ROOT',tmp_path)
    with pytest.raises(ValueError,match='prompt_contract_mismatch'):load_prompt('literature_adjudication','3')
