from services.sync_engine import LEAD_TO_CLICKUP_STATUS, CLICKUP_STATUS_TO_LEAD

def test_forward_map():
    assert LEAD_TO_CLICKUP_STATUS["NEW"] == "TO DO"
    assert LEAD_TO_CLICKUP_STATUS["QUALIFIED"] == "DONE"

def test_reverse_map():
    assert CLICKUP_STATUS_TO_LEAD["to do"] == "NEW"
