# services/sync_engine.py
from typing import Dict, Optional
import logging
from services.airtable_service import AirtableService
from services.clickup_service import ClickUpService
import config

logger = logging.getLogger(__name__)

# Mapping rules
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

def _normalize_clickup_status(raw) -> str:
    if not raw:
        return ""
    if isinstance(raw, dict):
        # ClickUp sometimes returns { "id": "...", "status": "to do" } or nested
        return str(raw.get("status") or raw.get("name") or "").strip().lower()
    return str(raw).strip().lower()

class SyncEngine:
    def __init__(self, airtable: AirtableService, clickup: ClickUpService):
        self.airtable = airtable
        self.clickup = clickup

    def ensure_task_for_lead(self, lead_record: Dict) -> None:
        """
        Ensure a ClickUp task exists for the given Airtable lead. Writes back clickup_task_id to Airtable to guarantee idempotency.
        """
        rec_id = lead_record.get("id")
        fields = lead_record.get("fields", {}) or {}
        name = fields.get("Name") or "Unnamed"
        email = fields.get("Email") or ""
        status = (fields.get("Status") or "NEW").upper()
        clickup_task_id = fields.get("clickup_task_id")

        logger.info("ensure_task_for_lead: %s", rec_id)

        # If LOST -> close corresponding ClickUp task if present
        if status == "LOST":
            if clickup_task_id:
                try:
                    self.clickup.update_task(clickup_task_id, {"status": "CLOSED"})
                    logger.info("Closed ClickUp task %s for lost lead %s", clickup_task_id, rec_id)
                except Exception:
                    logger.exception("Failed closing ClickUp task %s", clickup_task_id)
            return

        # If we have mapped task id -> update its status
        if clickup_task_id:
            try:
                target_status = LEAD_TO_CLICKUP_STATUS.get(status, "TO DO")
                payload = {"status": target_status, "name": f"{name} — {email}"}
                self.clickup.update_task(clickup_task_id, payload)
                logger.info("Updated ClickUp task %s for lead %s -> %s", clickup_task_id, rec_id, target_status)
            except Exception:
                logger.exception("Failed updating ClickUp task %s for lead %s", clickup_task_id, rec_id)
            return

        # Try to discover an existing task that links to this Airtable ID
        list_id = config.CLICKUP_LIST_ID
        try:
            payload = self.clickup.get_tasks_in_list(list_id)
            tasks = payload.get("tasks", [])
        except Exception:
            logger.exception("Failed listing ClickUp tasks for discovery")
            tasks = []

        found_task = None
        for t in tasks:
            # Check custom_fields match (if configured)
            for cf in t.get("custom_fields", []):
                if cf.get("id") == config.CLICKUP_CUSTOM_FIELD_AIRTABLE_ID and cf.get("value"):
                    if str(cf.get("value")) == str(rec_id):
                        found_task = t
                        break
            if found_task:
                break
            # Fallback: look in description for AirtableID:
            if f"AirtableID: {rec_id}" in (t.get("description") or ""):
                found_task = t
                break

        if found_task:
            try:
                self.airtable.update_lead(rec_id, {"clickup_task_id": found_task["id"]})
                logger.info("Discovered task %s and wrote back to Airtable for %s", found_task["id"], rec_id)
            except Exception:
                logger.exception("Failed writing discovered clickup_task_id back to Airtable")
            return

        # Create new ClickUp task and write back mapping
        try:
            target_status = LEAD_TO_CLICKUP_STATUS.get(status, "TO DO")
            description = f"AirtableID: {rec_id}\nEmail: {email}\nSource: {fields.get('Source','')}"
            custom_fields = []
            if config.CLICKUP_CUSTOM_FIELD_AIRTABLE_ID:
                custom_fields = [{"id": config.CLICKUP_CUSTOM_FIELD_AIRTABLE_ID, "value": rec_id}]
            created = self.clickup.create_task(list_id, name=f"{name} — {email}", status=target_status, description=description, custom_fields=custom_fields)
            task_id = created.get("id")
            if task_id:
                try:
                    self.airtable.update_lead(rec_id, {"clickup_task_id": task_id})
                    logger.info("Created ClickUp task %s and wrote back to Airtable lead %s", task_id, rec_id)
                except Exception:
                    logger.exception("Failed writing clickup_task_id back to Airtable")
        except Exception:
            logger.exception("Failed creating ClickUp task for lead %s", rec_id)

    def reconcile_tasks_to_leads(self) -> None:
        """
        Reverse-sync: Read tasks in ClickUp and update Airtable leads when task statuses change.
        Finds Airtable id in either a configured custom field or in the task description (AirtableID: <id>).
        """
        logger.info("[Reverse] reconcile_tasks_to_leads called")
        list_id = config.CLICKUP_LIST_ID
        try:
            payload = self.clickup.get_tasks_in_list(list_id)
            tasks = payload.get("tasks", [])
        except Exception:
            logger.exception("[Reverse] Failed to list ClickUp tasks")
            return

        for t in tasks:
            try:
                airtable_id: Optional[str] = None
                # check custom fields first
                for cf in t.get("custom_fields", []):
                    if cf.get("id") == config.CLICKUP_CUSTOM_FIELD_AIRTABLE_ID and cf.get("value"):
                        airtable_id = str(cf.get("value"))
                        break
                # fallback to description
                if not airtable_id and t.get("description") and "AirtableID:" in t.get("description"):
                    for line in t["description"].splitlines():
                        if line.strip().startswith("AirtableID:"):
                            airtable_id = line.split(":", 1)[1].strip()
                            break
                if not airtable_id:
                    continue

                current_task_status_norm = _normalize_clickup_status(t.get("status"))
                desired_lead_status = CLICKUP_STATUS_TO_LEAD.get(current_task_status_norm)
                if desired_lead_status:
                    # Read current Airtable status to avoid unnecessary writes
                    try:
                        lead = self.airtable.get_lead(airtable_id)
                        lead_fields = lead.get("fields", {})
                        existing_status = lead_fields.get("Status")
                    except Exception:
                        existing_status = None

                    if existing_status != desired_lead_status:
                        try:
                            self.airtable.update_lead(airtable_id, {"Status": desired_lead_status})
                            logger.info("[Reverse] Updated Airtable %s -> %s based on task %s", airtable_id, desired_lead_status, t.get("id"))
                        except Exception:
                            logger.exception("[Reverse] Failed writing status to Airtable lead %s", airtable_id)

                # treat archived/closed as LOST
                if t.get("archived") or current_task_status_norm == "closed":
                    try:
                        # fetch current to avoid rewrite
                        lead = self.airtable.get_lead(airtable_id)
                        if lead.get("fields", {}).get("Status") != "LOST":
                            self.airtable.update_lead(airtable_id, {"Status": "LOST"})
                            logger.info("[Reverse] Marked lead %s LOST because task %s is closed/archived", airtable_id, t.get("id"))
                    except Exception:
                        logger.exception("[Reverse] Failed marking lead %s LOST", airtable_id)

            except Exception:
                logger.exception("[Reverse] Error reconciling task %s", t.get("id"))
