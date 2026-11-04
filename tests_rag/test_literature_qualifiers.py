from rag_backend.knowledge_lab import KnowledgeStore
from rag_backend.literature_qualifiers import QualifierPolicy
from rag_backend.adaptive_literature import AdaptiveLiteratureAgent


class Positive:
    def score_pairs(self,pairs):return [8.]*len(pairs)


def test_financial_domain_can_be_established_by_document_context():
    policy=QualifierPolicy();rules=policy.constraints('Find a financial dataset')
    assert policy.matches('A financial dataset',rules)
    assert policy.span_constraints(rules)==[]


def test_background_interleaving_is_not_attributed_to_a_separating_method(tmp_path):
    store=KnowledgeStore(tmp_path/'knowledge.db');store.ingest([{'id':'synthetic:paper','title':'A synthetic separating method',
        'text':'Previous methods interleave reasoning and actions. We propose a method that separates reasoning from observations.',
        'kind':'abstract','source_url':'https://example.com/synthetic'}])
    result=AdaptiveLiteratureAgent(store,Positive(),None).build('Find a method interleaving reasoning and actions')
    assert result['status']=='not_found' and result['edges']==[]


def test_title_alone_does_not_supply_a_named_entity_in_the_quote(tmp_path):
    store=KnowledgeStore(tmp_path/'knowledge.db');store.ingest([{'id':'synthetic:paper','title':'Synthetic Wikipedia paper',
        'text':'A generic source sentence without a named corpus or sufficient method description.',
        'kind':'abstract','source_url':'https://example.com/synthetic'}])
    result=AdaptiveLiteratureAgent(store,Positive(),None).build('Find Wikipedia external memory')
    assert result['status']=='not_found' and result['edges']==[]
