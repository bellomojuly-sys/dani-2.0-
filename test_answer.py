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


def test_non_string_input_fails():
    # A non-string (e.g. a number) makes json.loads raise TypeError, which must
    # be turned into the same explicit ValueError, never silently accepted.
    with pytest.raises(ValueError):
        parse_answer(123)


def test_both_fields_are_parsed():
    # Not only 'answer': 'reason' must be read back too, so a mutation that
    # drops a field is caught.
    result = parse_answer('{"answer": "Write the case model", "reason": "It has a deadline"}')
    assert result.answer == "Write the case model"
    assert result.reason == "It has a deadline"


def test_error_message_is_explicit():
    # The raised ValueError must carry an explaining message, not be empty.
    with pytest.raises(ValueError) as exc:
        parse_answer("not json at all")
    assert "Invalid model response" in str(exc.value)
