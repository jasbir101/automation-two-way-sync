"""Entry point: runs a one-shot sync between Airtable and ClickUp."""
from services.airtable_service import AirtableService
from services.clickup_service import ClickUpService
from services.sync_engine import SyncEngine
from utils.logger import get_logger

logger = get_logger()

def main():
    logger.info("=== SYNC START ===")
    airtable = AirtableService()
    clickup = ClickUpService()
    engine = SyncEngine(airtable, clickup)
    leads = airtable.list_leads()
    logger.info(f"Fetched {len(leads)} leads from Airtable")
    for lead in leads:
        try:
            engine.ensure_task_for_lead(lead)
        except Exception as e:
            logger.exception("Failed to sync lead %s: %s", lead.get('id'), e)
    try:
        engine.reconcile_tasks_to_leads()
    except Exception:
        logger.exception("Reverse sync failed")
    logger.info("=== SYNC END ===")

if __name__ == '__main__':
    main()
