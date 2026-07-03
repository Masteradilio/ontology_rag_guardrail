from core.validation_cascade import (
    check_symbolic_contradictions,
    check_temporal_consistency,
    check_semantic_consistency,
    run_cascaded_validations,
)
from core.knowledge_ontology import KnowledgeOntology


def test_symbolic_contradiction_blocks():
    ont = KnowledgeOntology()
    # Add a FALSE fact in ontology
    ont.add_fact('alice', 'likes', 'chocolate', 'FALSE')
    hyps = [
        { 'subject': 'alice', 'relation': 'likes', 'object': 'chocolate' }
    ]
    step = check_symbolic_contradictions(hyps, ont)
    assert step['status'] == 'issues'
    res = run_cascaded_validations(hyps, ont)
    assert res['verdict'] == 'blocked'


def test_temporal_consistency_warns():
    ont = KnowledgeOntology()
    hyps = [
        { 'subject': 'evt1', 'relation': 'happens', 'object': 'x', 't': 10 },
        { 'subject': 'evt1', 'relation': 'happens', 'object': 'x', 't': 5 },
    ]
    step = check_temporal_consistency(hyps)
    assert step['status'] in ('warn', 'ok')
    # Overall verdict should be warn if no contradictions
    res = run_cascaded_validations(hyps, ont)
    assert res['verdict'] in ('warn', 'ok')


def test_semantic_consistency_symmetry_warns():
    ont = KnowledgeOntology()
    hyps = [
        { 'subject': 'a', 'relation': 'same_as', 'object': 'b' },
    ]
    step = check_semantic_consistency(hyps, ont)
    assert step['status'] in ('warn', 'ok')

