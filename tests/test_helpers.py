from jira_mcp.helpers import (
    clean,
    format_user,
    is_adf,
    pick,
    text_to_adf,
)


def test_clean_strips_noise_keys_recursively():
    raw = {
        "self": "http://x",
        "key": "PROJ-1",
        "fields": {"avatarUrls": {"48x48": "..."}, "summary": "hi"},
    }
    out = clean(raw)
    assert "self" not in out
    assert out["key"] == "PROJ-1"
    assert "avatarUrls" not in out["fields"]
    assert out["fields"]["summary"] == "hi"


def test_clean_recurses_into_lists():
    raw = [{"self": "x", "a": 1}, {"_links": {}, "b": 2}]
    assert clean(raw) == [{"a": 1}, {"b": 2}]


def test_text_to_adf_shape_and_detection():
    adf = text_to_adf("hello")
    assert adf["type"] == "doc"
    assert adf["version"] == 1
    assert adf["content"][0]["content"][0]["text"] == "hello"
    assert is_adf(adf) is True
    assert is_adf({"type": "paragraph"}) is False
    assert is_adf("plain") is False


def test_format_user_projects_key_fields():
    user = {
        "accountId": "123",
        "displayName": "Jane",
        "emailAddress": "jane@example.com",
        "active": True,
        "self": "http://noise",
    }
    assert format_user(user) == {
        "account_id": "123",
        "display_name": "Jane",
        "email": "jane@example.com",
        "active": True,
    }


def test_pick_supports_dotted_paths():
    obj = {"fields": {"summary": "S"}, "key": "K", "ignored": 1}
    out = pick(obj, ["key", "fields.summary"])
    assert out["key"] == "K"
    assert out["fields_summary"] == "S"
    assert "ignored" not in out
