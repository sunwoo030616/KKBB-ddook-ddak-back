from rag_backend.research_passages import contribution_passages


def test_previous_work_is_not_the_only_window_for_a_new_contribution():
    text=('Previous methods interleave reasoning and actions. '
          'This study addresses the issue, proposing a method that separates reasoning from observations. '
          'Our method reduces repeated execution while retaining useful task context.')
    spans=contribution_passages(text)
    assert all(s['evidence_role']=='author_claim_context' for s in spans.values())
    assert not any(s['start']==0 for s in spans.values())
    assert any('separates reasoning' in s['text'] for s in spans.values())
    assert all(text[s['start']:s['end']]==s['text'] for s in spans.values())


def test_no_author_claim_pattern_falls_back_with_an_explicit_role():
    text='A synthetic source describes a mechanism without a first-person contribution pattern.'
    spans=contribution_passages(text)
    assert spans and all(s['evidence_role']=='abstract_context' for s in spans.values())


def test_following_background_sentence_is_not_a_standalone_author_claim():
    text='We propose a method that separates observations from reasoning. Previous methods interleave tool calls and reasoning.'
    spans=contribution_passages(text)
    assert all(not s['text'].startswith('Previous') for s in spans.values())


def test_long_author_claim_retains_late_qualifier_without_requiring_repeated_we():
    text='We introduce a method with '+('controlled context '*24)+'and a dense index of Wikipedia. Previous work uses unrelated models.'
    spans=contribution_passages(text,max_chars=240)
    assert any('Wikipedia' in s['text'] for s in spans.values())
    assert all(s['start']<text.index('Previous') for s in spans.values())
