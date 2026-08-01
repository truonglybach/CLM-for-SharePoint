"""The extraction schemas must constrain values, not merely describe them."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from clm import ai_schemas as S
from clm import azure_client
from clm.schema import ClauseChangeType, RelationshipType


def test_change_type_rejects_free_text():
    with pytest.raises(ValidationError):
        S.ModifiedClause(clause_id="TERM", change_type="Tweaked", note="", evidence_span="")
    assert S.ModifiedClause(clause_id="TERM", change_type="Modified", note="", evidence_span="").change_type is ClauseChangeType.MODIFIED

def test_relationship_rejects_free_text():
    kwargs = dict(canonical_requirement="", intensity_a=None, intensity_b=None, rationale="", evidence_a="", evidence_b="")
    with pytest.raises(ValidationError):
        S.ClauseDiffJudgment(relationship="sort of stricter", **kwargs)
    assert S.ClauseDiffJudgment(relationship="stricter", **kwargs).relationship is RelationshipType.STRICTER

@pytest.mark.parametrize("model,field,expected", [
    (S.ModifiedClausesExtraction, "change_type", [c.value for c in ClauseChangeType]),
    (S.ClauseDiffJudgment, "relationship", [r.value for r in RelationshipType]),
])
def test_enum_choices_reach_the_strict_schema(model, field, expected):
    # Structured Outputs must see the allowed values, otherwise the constraint is local-only.
    schema = azure_client.to_strict_schema(model)
    enums = [d.get("enum") for d in schema.get("$defs", {}).values() if d.get("enum")]
    assert expected in enums

def test_strict_schema_forbids_extra_properties():
    schema = azure_client.to_strict_schema(S.ModifiedClause)
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])
