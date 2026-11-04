import pytest

from scripts.collect_research_corpus import parse


def feed(*entries):
    return ('<feed xmlns="http://www.w3.org/2005/Atom">'+''.join(entries)+'</feed>').encode()


def entry(id='2109.00122v3',title='FinQA: Synthetic test title'):
    return f'<entry><id>http://arxiv.org/abs/{id}</id><title>{title}</title><summary>This is synthetic source text long enough to exercise metadata ingestion validation.</summary><published>2021-01-01T00:00:00Z</published><updated>2022-01-01T00:00:00Z</updated></entry>'


SPEC=[{'arxiv_id':'2109.00122','title_contains':'FinQA','topic':'finance'}]


def test_canonical_id_keeps_versioned_url_and_source_topic():
    record=parse(feed(entry()),SPEC)[0]
    assert record['id']=='arxiv:2109.00122'
    assert record['source_url']=='https://arxiv.org/abs/2109.00122v3'
    assert record['topic']=='finance'


@pytest.mark.parametrize('raw',[feed(),feed(entry(),entry()),feed(entry(id='9999.99999')),feed(entry(title='Unrelated physics paper'))])
def test_incomplete_duplicate_wrong_id_and_title_fail_closed(raw):
    with pytest.raises(ValueError):parse(raw,SPEC)
