import pytest
from answer import parse_answer


def test_valid_response_is_accepted():
    result = parse_answer('{"answer": "Write the case model", "reason": "It has a deadline"}')
    assert result.answer == "Write the case model"


def test_missing_field_fails():
    with pytest.raises(ValueError):
        parse_answer('{"answer": "Write the case model"}')


def test_plain_text_fails():
    with pytest.raises(ValueError):
        parse_answer("Sure! You should write the case model first.")
