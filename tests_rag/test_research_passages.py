import pytest

from rag_backend.research_passages import context_passages


def test_adjacent_sentences_preserve_original_whitespace_and_offsets():
    text='The model uses external memory.\n\nWikipedia is its indexed knowledge source. Another sentence follows.'
    spans=list(context_passages(text).values())
    assert spans[0]['text'].startswith('The model') and '\n\nWikipedia' in spans[0]['text']
    assert all(text[s['start']:s['end']]==s['text'] for s in spans)


@pytest.mark.parametrize('text',[' '.join('word'+str(i) for i in range(300)), 'X'*1001, 'Short. Yes.', '   '])
def test_bounded_passages_cover_every_non_whitespace_source_character(text):
    spans=context_passages(text,max_chars=100)
    covered=set()
    for span in spans.values():
        assert 0<len(span['text'])<=100
        assert text[span['start']:span['end']]==span['text']
        covered.update(range(span['start'],span['end']))
    assert all(i in covered for i,c in enumerate(text) if not c.isspace())
