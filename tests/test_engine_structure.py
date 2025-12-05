import services.sync_engine as se

def test_engine_has_methods():
    assert hasattr(se.SyncEngine, "ensure_task_for_lead")
    assert hasattr(se.SyncEngine, "reconcile_tasks_to_leads")
