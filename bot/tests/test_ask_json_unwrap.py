"""_ask_json unwrap rules — blanket list-unwrapping once sent every intent to chat."""
from unittest.mock import MagicMock, patch

import claude_svc


def _resp(content):
    r = MagicMock()
    r.choices = [MagicMock()]
    r.choices[0].message.content = content
    return r


def _ask(content):
    with patch.object(claude_svc, "_get_client") as gc, \
         patch.object(claude_svc, "_with_retry", side_effect=lambda fn, **kw: fn()):
        gc.return_value.chat.completions.create.return_value = _resp(content)
        return claude_svc._ask_json("x")


def test_multikey_dict_with_list_field_stays_dict():
    # understand_message responses carry extra_tasks: [] — must NOT unwrap
    out = _ask('{"intent": "task", "task": null, "extra_tasks": [], "task_ref": ""}')
    assert isinstance(out, dict)
    assert out["intent"] == "task"


def test_single_key_array_wrapper_unwraps():
    # generate_quiz relies on {"items": [...]} → list
    out = _ask('{"items": [1, 2, 3]}')
    assert out == [1, 2, 3]


def test_plain_dict_passthrough():
    out = _ask('{"correct": true, "explanation": "yes"}')
    assert out == {"correct": True, "explanation": "yes"}
