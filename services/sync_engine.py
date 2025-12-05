from typing import Dict, Optional
import logging
from services.airtable_service import AirtableService
from services.clickup_service import ClickUpService
import config

logger = logging.getLogger(__name__)

LEAD_TO_CLICKUP_STATUS = {
    "NEW": "TO DO",
    "CONTACTED": "IN PROGRESS",
    "QUALIFIED": "DONE",
    "LOST": "CLOSED"
}

CLICKUP_STATUS_TO_LEAD = {
    "to do": "NEW",
    "in progress": "CONTACTED",
    "done": "QUALIFIED",
    "closed": "LOST"
}

def _normalize_status(raw):
    if not raw:
        return ""
    if isinstance(raw, dict):
        if "status" in raw and isinstance(raw["status"], dict):
            val = raw["status"].get("status") or raw["status"].get("name") or ""
        else:
            val = raw.get("status") or raw.get("name") or ""
    else:
        val = raw
    return str(val).strip().lower()

class SyncEngine:
    def __init__(self, airtable: AirtableService, clickup: ClickUpService):
        self.airtable = airtable
        self.clickup = clickup

    def ensure_task_for_lead(self, lead_record: Dict) -> None:
        rec_id = lead_record.get("id")
        fields = lead_record.get("fields", {}) or {}
        name = fields.get("Name") or "Unnamed"
        email = fields.get("Email") or ""
        status = (fields.get("Status") or "NEW").upper()
        clickup_task_id = fields.get("clickup_task_id")

        logger.info("ensure_task_for_lead: %s", rec_id)

        # Skip LOST leads creation, attempt to close existing task
        if status == "LOST":
            if clickup_task_id:
                try:
                    self.clickup.update_task(clickup_task_id, {"status": "CLOSED"})
                except Exception:
                    logger.exception("Failed closing ClickUp task %s", clickup_task_id)
            return

# continuing SyncEngine.ensure_task_for_lead and reconcile implementation

        # Update existing task
        if clickup_task_id:
            try:
                target_status = LEAD_TO_CLICKUP_STATUS.get(status, "TO DO")
                payload = {"status": target_status, "name": f"{name} - {email}"}
                self.clickup.update_task(clickup_task_id, payload)
            except Exception:
                logger.exception("Failed updating ClickUp task %s", clickup_task_id)
            return

        # Discover existing tasks in list
        list_id = config.CLICKUP_LIST_ID
        found_task = None
        try:
            payload = self.clickup.get_tasks_in_list(list_id)
            tasks = payload.get("tasks", [])
            for t in tasks:
                for cf in t.get("custom_fields", []):
                    if cf.get("id") == config.CLICKUP_CUSTOM_FIELD_AIRTABLE_ID and cf.get("value"):
                        if str(cf.get("value")) == str(rec_id):
                            found_task = t
                            break
                if found_task:
                    break
                if f"AirtableID: {rec_id}" in (t.get("description") or ""):
                    found_task = t
                    break
        except Exception:
            logger.exception("Failed listing ClickUp tasks")

        if found_task:
            try:
                self.airtable.update_lead(rec_id, {"clickup_task_id": found_task["id"]})
            except Exception:
                logger.exception("Failed writing discovered clickup_task_id back to Airtable")
            return

        # Create task
        try:
            target_status = LEAD_TO_CLICKUP_STATUS.get(status, "TO DO")
            description = f"AirtableID: {rec_id}\nEmail: {email}\nSource: {fields.get('Source','')}"
            custom_fields = []
            if config.CLICKUP_CUSTOM_FIELD_AIRTABLE_ID:
                custom_fields = [{"id": config.CLICKUP_CUSTOM_FIELD_AIRTABLE_ID, "value": rec_id}]
            created = self.clickup.create_task(list_id, name=f"{name} - {email}", status=target_status, description=description, custom_fields=custom_fields)
            task_id = created.get("id")
            if task_id:
                try:
                    self.airtable.update_lead(rec_id, {"clickup_task_id": task_id})
                except Exception:
                    logger.exception("Failed writing clickup_task_id back to Airtable")
        except Exception:
            logger.exception("Failed creating ClickUp task for lead %s", rec_id)

    def reconcile_tasks_to_leads(self) -> None:
        list_id = config.CLICKUP_LIST_ID
        try:
            payload = self.clickup.get_tasks_in_list(list_id)
            tasks = payload.get("tasks", [])
        except Exception:
            logger.exception("Failed to list ClickUp tasks")
            return

        for t in tasks:
            try:
                airtable_id = None
                for cf in t.get("custom_fields", []):
                    if cf.get("id") == config.CLICKUP_CUSTOM_FIELD_AIRTABLE_ID and cf.get("value"):
                        airtable_id = str(cf.get("value"))
                        break
                if not airtable_id and t.get("description") and "AirtableID:" in t.get("description"):
                    for line in t["description"].splitlines():
                        if line.startswith("AirtableID:"):
                            airtable_id = line.split(":", 1)[1].strip()
                            break
                if not airtable_id:
                    continue
                task_status_name = _normalize_status(t.get("status"))
                desired_lead_status = CLICKUP_STATUS_TO_LEAD.get(task_status_name)
                if desired_lead_status:
                    try:
                        self.airtable.update_lead(airtable_id, {"Status": desired_lead_status})
                    except Exception:
                        logger.exception("Failed writing status to Airtable lead %s", airtable_id)
                if t.get("archived") or task_status_name == "closed":
                    try:
                        self.airtable.update_lead(airtable_id, {"Status": "LOST"})
                    except Exception:
                        logger.exception("Failed marking lead %s LOST", airtable_id)
            except Exception:
                logger.exception("Error reconciling task %s", t.get("id"))
