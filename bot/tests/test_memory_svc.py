from unittest.mock import MagicMock, patch

with patch('supabase_svc.create_client'):
    import memory_svc


# ---- helpers ----------------------------------------------------------------

def _write_client():
    """MagicMock supabase client whose insert returns a fresh id; update/select no-op."""
    c = MagicMock()
    ins = MagicMock(); ins.data = [{"id": "new-id"}]
    c.table.return_value.insert.return_value.execute.return_value = ins
    (c.table.return_value.update.return_value.eq.return_value.eq.return_value
     .execute.return_value) = MagicMock()
    return c


# ---- pure helpers -----------------------------------------------------------

def test_norm_collapses_whitespace_and_case():
    assert memory_svc._norm("  Hello   World ") == "hello world"


def test_pillar_defaults_invalid_to_general():
    assert memory_svc._pillar("addiction") == "addiction"
    assert memory_svc._pillar("MOTIVATION") == "motivation"
    assert memory_svc._pillar("nonsense") == "general"
    assert memory_svc._pillar(None) == "general"


# ---- apply_extraction: new facts + dedup ------------------------------------

def test_apply_adds_new_facts_and_skips_dupes():
    data = {"facts_add": [
        {"text": "quitting vaping", "pillar": "addiction"},
        {"text": "Quitting Vaping", "pillar": "addiction"},  # dupe (normalized)
        {"text": "exam on the 25th", "pillar": "productivity"},
    ]}
    with patch('memory_svc.load_facts', return_value=[]), \
         patch('memory_svc.get_client', return_value=_write_client()):
        ch = memory_svc.apply_extraction(1, data)
    assert ch["facts_added"] == 2  # dupe skipped


def test_apply_skips_fact_already_known():
    with patch('memory_svc.load_facts', return_value=[{"id": "x", "text": "likes coffee"}]), \
         patch('memory_svc.get_client', return_value=_write_client()):
        ch = memory_svc.apply_extraction(1, {"facts_add": [{"text": "likes coffee"}]})
    assert ch["facts_added"] == 0


# ---- apply_extraction: fact-update / supersede (our fix) --------------------

def test_fact_update_supersedes_old():
    client = _write_client()
    existing = [{"id": "old-1", "text": "has an exam next week"}]
    data = {"fact_updates": [
        {"old": "has an exam next week", "new": "has an exam on the 25th", "pillar": "productivity"}
    ]}
    with patch('memory_svc.load_facts', return_value=existing), \
         patch('memory_svc.get_client', return_value=client):
        ch = memory_svc.apply_extraction(1, data)
    assert ch["facts_updated"] == 1
    # the old fact must be marked superseded (update path hit)
    client.table.return_value.update.assert_called()
    upd_arg = client.table.return_value.update.call_args[0][0]
    assert upd_arg["status"] == "superseded"
    assert upd_arg["superseded_by"] == "new-id"


def test_fact_update_fuzzy_matches_old():
    existing = [{"id": "old-2", "text": "vaping for 2 years on 30mg pods"}]
    client = _write_client()
    data = {"fact_updates": [{"old": "vaping for 2 years", "new": "quit vaping 3 days ago"}]}
    with patch('memory_svc.load_facts', return_value=existing), \
         patch('memory_svc.get_client', return_value=client):
        ch = memory_svc.apply_extraction(1, data)
    assert ch["facts_updated"] == 1
    client.table.return_value.update.assert_called()  # fuzzy-matched the old fact


def test_fact_update_without_match_still_inserts_new():
    with patch('memory_svc.load_facts', return_value=[]), \
         patch('memory_svc.get_client', return_value=_write_client()):
        ch = memory_svc.apply_extraction(1, {"fact_updates": [{"old": "nope", "new": "fresh fact"}]})
    assert ch["facts_updated"] == 1  # new inserted even if no old to supersede


# ---- apply_extraction: events + clamping ------------------------------------

def test_event_inserted_with_clamped_sentiment_and_valid_type():
    client = _write_client()
    data = {"events": [
        {"type": "progress", "summary": "quit vaping", "sentiment": 5.0, "intensity": -2},
        {"type": "weird", "summary": "something", "sentiment": "x"},  # bad type+sentiment
        {"type": "mood", "summary": ""},  # empty summary -> skipped
    ]}
    with patch('memory_svc.load_facts', return_value=[]), \
         patch('memory_svc.get_client', return_value=client):
        ch = memory_svc.apply_extraction(1, data)
    assert ch["events"] == 2  # empty-summary one skipped
    payloads = [c.args[0] for c in client.table.return_value.insert.call_args_list]
    ev = [p for p in payloads if "summary" in p and p.get("type") in memory_svc.EVENT_TYPES]
    assert any(p["sentiment"] == 1.0 and p["intensity"] == 0.0 for p in ev)  # clamped
    assert any(p["type"] == "event" for p in ev)  # invalid type normalized


def test_apply_non_dict_is_safe():
    assert memory_svc.apply_extraction(1, None) == {"facts_added": 0, "facts_updated": 0, "events": 0}


# ---- memory_brief -----------------------------------------------------------

def test_memory_brief_empty_when_nothing():
    with patch('memory_svc.load_facts', return_value=[]), \
         patch('memory_svc.load_events', return_value=[]):
        assert memory_svc.memory_brief(1) == ""


def test_memory_brief_renders_facts_and_timeline():
    facts = [{"text": "quitting vaping", "pillar": "addiction"},
             {"text": "name is Gon", "pillar": "general"}]
    events = [{"type": "setback", "summary": "relapsed", "sentiment": -0.5}]
    with patch('memory_svc.load_facts', return_value=facts), \
         patch('memory_svc.load_events', return_value=events):
        out = memory_svc.memory_brief(1)
    assert "quitting vaping" in out and "[addiction]" in out
    assert "name is Gon" in out and "[general]" not in out  # general not tagged
    assert "(setback) relapsed" in out and "-0.5" in out


# ---- welcome_back -----------------------------------------------------------

def test_welcome_back_uses_open_thread():
    with patch('memory_svc.last_session', return_value={"open_threads": ["the exam", "vaping"], "summary": "x"}):
        assert "the exam" in memory_svc.welcome_back(1)


def test_welcome_back_falls_back_to_summary():
    with patch('memory_svc.last_session', return_value={"open_threads": [], "summary": "worked on Python"}):
        assert "worked on Python" in memory_svc.welcome_back(1)


def test_welcome_back_empty_when_no_session():
    with patch('memory_svc.last_session', return_value=None):
        assert memory_svc.welcome_back(1) == ""
