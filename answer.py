import json
from pydantic import BaseModel, ValidationError


class DaniAnswer(BaseModel):
    answer: str
    reason: str


def parse_answer(text):
    try:
        data = json.loads(text)
        return DaniAnswer.model_validate(data)
    except (json.JSONDecodeError, ValidationError, TypeError) as error:
        raise ValueError(f"Invalid model response: {error}")
