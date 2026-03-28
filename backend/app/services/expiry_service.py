"""
Expiry Alert Processing Service.

Responsible for:
- Scanning for expiring / expired documents via DB RPC functions.
- Creating `document_expiry_alerts` records for alert thresholds.
- Sending in-app notifications and emails via NotificationService.
- Flagging suppliers with expired documents as COMPLIANCE_REQUIRED.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID

from ..db.supabase import Database, get_db
from ..services.notifications import NotificationService
from ..models.expiry import PendingAlert
from ..core.config import settings

logger = logging.getLogger(__name__)

# Thresholds (days before expiry) at which we send one alert per document.
ALERT_THRESHOLDS = [90, 30, 7, 1]

# Human-readable labels for document types (backend copy – kept in sync with frontend).
DOCUMENT_TYPE_LABELS: dict[str, str] = {
    "TAX_CLEARANCE": "Tax Clearance Certificate",
    "ZIMRA_BP_NUMBER": "ZIMRA BP Number",
    "FDMS_COMPLIANCE": "FDMS Compliance Certificate",
    "VAT_CERTIFICATE": "VAT Certificate",
    "NSSA_CLEARANCE": "NSSA Clearance Certificate",
    "PRAZB_LICENSE": "PRAZB License",
    "VENDOR_FORM": "Vendor Registration Form",
    "BANK_DETAILS": "Bank Details",
    "COMPANY_PROFILE": "Company Profile",
    "CERTIFICATE_OF_INCORPORATION": "Certificate of Incorporation",
    "CR14_OR_CR6": "CR14 or CR6 Document",
    "EVALUATION_FORM": "Evaluation Form",
    "HEALTH_CERTIFICATE": "Health & Safety Certificate",
    "ISO_9001": "ISO 9001 Certificate",
    "ISO_45001": "ISO 45001 Certificate",
    "ISO_14000": "ISO 14000 Certificate",
    "INTERNAL_QMS": "Internal QMS Document",
    "SHEQ_POLICY": "SHEQ Policy",
    "FOOD_SAFETY_CERTIFICATION": "Food Safety Certification",
    "GOOD_AGRICULTURAL_PRACTICES": "Good Agricultural Practices Certificate",
    "ISO_45000": "ISO 45000 Certificate",
    "INDUSTRY_CERTIFICATION": "Industry Certification",
}


def _label(document_type: str) -> str:
    """Return a human-readable label for a document type key."""
    return DOCUMENT_TYPE_LABELS.get(document_type, document_type.replace("_", " ").title())


def _alert_type_for_days(days: int) -> str:
    """Map days-until-expiry to the standard alert_type key used in the DB."""
    if days <= 0:
        return "expired"
    if days <= 1:
        return "1_day"
    if days <= 7:
        return "7_days"
    if days <= 30:
        return "30_days"
    if days <= 60:
        return "60_days"
    return "90_days"


class ExpiryAlertService:
    """Processes document expiry alerts and dispatches notifications."""

    def __init__(self, db: Database):
        self.db = db
        self.notification_service = NotificationService(db)

    # ------------------------------------------------------------------
    # Public entry points
    # ------------------------------------------------------------------

    async def run_daily_expiry_job(self) -> dict[str, Any]:
        """
        Main job invoked by the scheduler (and the admin trigger endpoint).

        Steps:
        1. Flag expired documents → sets COMPLIANCE_REQUIRED on suppliers.
        2. Process pending alert records created by the DB trigger.
        3. Create new alert records for threshold crossings.
        4. Return a summary dict.
        """
        summary: dict[str, Any] = {
            "run_at": datetime.now(timezone.utc).isoformat(),
            "flagged_suppliers": 0,
            "suspended_suppliers": 0,
            "pending_alerts_processed": 0,
            "new_alerts_created": 0,
            "notifications_sent": 0,
            "errors": [],
        }

        # 1. Flag expired documents / update supplier statuses.
        try:
            flagged = await self._flag_expired_documents()
            summary["flagged_suppliers"] = flagged
        except Exception as exc:
            logger.error("Error flagging expired documents: %s", exc)
            summary["errors"].append(f"flag_expired: {exc}")

        # 2. Recompute supplier portfolio status with scoped enforcement:
        #    - global/statutory gaps can suspend the supplier,
        #    - category-specific gaps move supplier to COMPLIANCE_REQUIRED.
        try:
            suspended = await self._recompute_portfolio_statuses()
            summary["suspended_suppliers"] = suspended
        except Exception as exc:
            logger.error("Error recomputing portfolio status: %s", exc)
            summary["errors"].append(f"portfolio_status: {exc}")

        # 3. Process any pending alerts that the DB trigger already created.
        try:
            sent = await self.process_pending_alerts()
            summary["pending_alerts_processed"] = sent
            summary["notifications_sent"] += sent
        except Exception as exc:
            logger.error("Error processing pending alerts: %s", exc)
            summary["errors"].append(f"process_pending: {exc}")

        # 4. Check threshold crossings and create new alerts where needed.
        try:
            created, notified = await self.create_alerts()
            summary["new_alerts_created"] = created
            summary["notifications_sent"] += notified
        except Exception as exc:
            logger.error("Error creating expiry alerts: %s", exc)
            summary["errors"].append(f"create_alerts: {exc}")

        logger.info("Expiry job finished: %s", summary)
        return summary

    async def create_alerts(self) -> tuple[int, int]:
        """
        Scan expiring documents and create alert records for crossed thresholds.

        Returns:
            Tuple of (alerts_created, notifications_sent).
        """
        created = 0
        notified = 0

        # Query all documents expiring within the next 90 days.
        result = self.db.client.rpc(
            "get_expiring_documents", {"p_days_threshold": 90}
        ).execute()
        docs = result.data or []

        for doc in docs:
            try:
                new_c, new_n = await self._process_expiring_document(doc)
                created += new_c
                notified += new_n
            except Exception as exc:
                logger.error(
                    "Error processing expiring doc %s: %s", doc.get("document_id"), exc
                )

        # Also handle already-expired documents.
        expired_result = self.db.client.rpc("get_expired_documents").execute()
        expired_docs = expired_result.data or []

        for doc in expired_docs:
            try:
                new_c, new_n = await self._process_expired_document(doc)
                created += new_c
                notified += new_n
            except Exception as exc:
                logger.error(
                    "Error processing expired doc %s: %s", doc.get("document_id"), exc
                )

        return created, notified

    async def process_pending_alerts(self) -> int:
        """
        Send notifications for pending alert records in `document_expiry_alerts`.

        Returns:
            Number of alerts processed.
        """
        result = self.db.client.rpc("get_pending_alerts").execute()
        pending = result.data or []

        sent = 0
        for alert_data in pending:
            try:
                await self._send_alert_notification(PendingAlert(**alert_data))
                # Mark as sent in DB.
                self.db.client.rpc(
                    "mark_alert_sent",
                    {"p_alert_id": str(alert_data["alert_id"])}
                ).execute()
                sent += 1
            except Exception as exc:
                logger.error(
                    "Error sending pending alert %s: %s", alert_data.get("alert_id"), exc
                )

        return sent

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _flag_expired_documents(self) -> int:
        """Call DB function to set COMPLIANCE_REQUIRED on suppliers with expired docs."""
        result = self.db.client.rpc("check_and_flag_expired_documents").execute()
        if isinstance(result.data, list):
            return len(result.data)
        # Fallback for unexpected DB return shapes.
        if isinstance(result.data, int):
            return result.data
        return 0

    async def _recompute_portfolio_statuses(self) -> int:
        """Recompute category + supplier portfolio status and notify on key transitions."""
        from ..models.enums import SupplierStatus

        managed_statuses = [
            SupplierStatus.APPROVED.value,
            SupplierStatus.COMPLIANCE_REQUIRED.value,
            SupplierStatus.SUSPENDED.value,
        ]

        # Ensure category rows are fresh before deriving supplier-level status.
        await self.db.recompute_category_compliance_for_suppliers(statuses=managed_statuses)
        transitions = await self.db.recompute_portfolio_status_for_suppliers(statuses=managed_statuses)

        suspended_count = 0

        for transition in transitions:
            if not transition.get("changed"):
                continue

            supplier_id = str(transition.get("supplier_id", ""))
            previous_status = transition.get("previous_status", "")
            new_status = transition.get("new_status", "")

            try:
                supplier_result = (
                    self.db.client.table("suppliers")
                    .select("company_name,email,contact_person_name,suspension_reason")
                    .eq("id", supplier_id)
                    .maybe_single()
                    .execute()
                )
                supplier = supplier_result.data or {}
            except Exception:
                supplier = {}

            company_name = supplier.get("company_name", "Supplier")
            supplier_email = supplier.get("email", "")
            contact_person = supplier.get("contact_person_name", company_name)

            if new_status == SupplierStatus.SUSPENDED.value:
                suspended_count += 1
                reason = supplier.get("suspension_reason") or transition.get("reason", "Statutory compliance missing")

                if supplier_email:
                    try:
                        from ..core.email import email_service, EmailTemplate
                        await email_service.send_template_email(
                            to_email=supplier_email,
                            template=EmailTemplate.SUPPLIER_SUSPENDED,
                            data={
                                "supplier_name": company_name,
                                "contact_person": contact_person,
                                "suspension_reason": reason,
                                "portal_url": settings.FRONTEND_URL,
                            },
                            to_name=contact_person,
                        )
                    except Exception as exc:
                        logger.error("Failed to send suspension email to %s: %s", supplier_email, exc)

                try:
                    from ..core.email import email_service, EmailTemplate
                    await email_service.send_template_email(
                        to_email=settings.ADMIN_EMAIL,
                        template=EmailTemplate.ADMIN_SUPPLIER_SUSPENDED,
                        data={
                            "supplier_name": company_name,
                            "supplier_id": supplier_id,
                            "suspension_reason": reason,
                            "review_link": f"{settings.FRONTEND_URL}/admin/suspended",
                        },
                    )
                except Exception as exc:
                    logger.error("Failed to send admin suspension email: %s", exc)

            if (
                previous_status in (SupplierStatus.SUSPENDED.value, SupplierStatus.COMPLIANCE_REQUIRED.value)
                and new_status == SupplierStatus.APPROVED.value
                and supplier_email
            ):
                try:
                    from ..core.email import email_service, EmailTemplate
                    await email_service.send_template_email(
                        to_email=supplier_email,
                        template=EmailTemplate.SUPPLIER_RESTORED,
                        data={
                            "supplier_name": company_name,
                            "contact_person": contact_person,
                            "portal_url": settings.FRONTEND_URL,
                        },
                        to_name=contact_person,
                    )
                except Exception as exc:
                    logger.error("Failed to send restoration email to %s: %s", supplier_email, exc)

        return suspended_count

    def _alert_already_sent(self, document_id: str, alert_type: str) -> bool:
        """Check whether an alert of this type has already been created for the document."""
        result = (
            self.db.client.table("document_expiry_alerts")
            .select("id")
            .eq("document_id", document_id)
            .eq("alert_type", alert_type)
            .limit(1)
            .execute()
        )
        return bool(result.data)

    def _upsert_alert_record(
        self,
        document_id: str,
        supplier_id: str,
        alert_type: str,
        expiry_date: str,
    ) -> str | None:
        """Insert an alert record, returning the new alert ID or None if it already existed."""
        if self._alert_already_sent(document_id, alert_type):
            return None

        result = (
            self.db.client.table("document_expiry_alerts")
            .insert(
                {
                    "document_id": document_id,
                    "supplier_id": supplier_id,
                    "alert_type": alert_type,
                    "expiry_date": expiry_date,
                    "alert_date": datetime.now(timezone.utc).isoformat(),
                    "email_sent": False,
                    "acknowledged": False,
                    "reminder_count": 0,
                }
            )
            .execute()
        )
        if result.data:
            return result.data[0]["id"]
        return None

    async def _process_expiring_document(self, doc: dict) -> tuple[int, int]:
        """Handle one row from get_expiring_documents."""
        days: int = doc.get("days_until_expiry", 999)
        document_id = str(doc["document_id"])
        supplier_id = str(doc["supplier_id"])
        expiry_date_val = doc.get("expiry_date", "")
        if isinstance(expiry_date_val, date):
            expiry_date_str = expiry_date_val.isoformat()
        else:
            expiry_date_str = str(expiry_date_val)

        # Determine which thresholds have been crossed.
        triggered = [t for t in ALERT_THRESHOLDS if days <= t]
        if not triggered:
            return 0, 0

        # For each triggered threshold use the tightest (smallest) one for this
        # run so we don't spam the supplier with multiple emails at once.
        threshold = min(triggered)
        alert_type = _alert_type_for_days(threshold)

        alert_id = self._upsert_alert_record(
            document_id, supplier_id, alert_type, expiry_date_str
        )
        if alert_id is None:
            return 0, 0  # Already sent.

        # Send notification.
        await self.notification_service.notify_document_expiry(
            supplier_id=UUID(supplier_id),
            supplier_name=doc.get("company_name", ""),
            supplier_email=doc.get("email", ""),
            contact_person=doc.get("contact_person", doc.get("company_name", "")),
            document_type=doc.get("document_type", ""),
            document_type_label=_label(doc.get("document_type", "")),
            expiry_date=expiry_date_str,
            days_until_expiry=days,
        )

        # Mark the alert record email as sent.
        self.db.client.rpc(
            "mark_alert_sent", {"p_alert_id": alert_id}
        ).execute()

        return 1, 1

    async def _process_expired_document(self, doc: dict) -> tuple[int, int]:
        """Handle one row from get_expired_documents."""
        document_id = str(doc["document_id"])
        supplier_id = str(doc["supplier_id"])
        expiry_date_val = doc.get("expiry_date", "")
        if isinstance(expiry_date_val, date):
            expiry_date_str = expiry_date_val.isoformat()
        else:
            expiry_date_str = str(expiry_date_val)

        alert_id = self._upsert_alert_record(
            document_id, supplier_id, "expired", expiry_date_str
        )
        if alert_id is None:
            return 0, 0

        days_since = doc.get("days_since_expiry", 0)

        await self.notification_service.notify_document_expiry(
            supplier_id=UUID(supplier_id),
            supplier_name=doc.get("company_name", ""),
            supplier_email=doc.get("email", ""),
            contact_person=doc.get("contact_person", doc.get("company_name", "")),
            document_type=doc.get("document_type", ""),
            document_type_label=_label(doc.get("document_type", "")),
            expiry_date=expiry_date_str,
            days_until_expiry=-days_since,
        )

        self.db.client.rpc(
            "mark_alert_sent", {"p_alert_id": alert_id}
        ).execute()

        return 1, 1

    async def _send_alert_notification(self, alert: PendingAlert) -> None:
        """Send notification for a PendingAlert row from get_pending_alerts()."""
        days = alert.days_until_expiry

        await self.notification_service.notify_document_expiry(
            supplier_id=alert.supplier_id,
            supplier_name=alert.company_name,
            supplier_email=alert.email,
            contact_person=alert.company_name,
            document_type=alert.document_type,
            document_type_label=_label(alert.document_type),
            expiry_date=alert.expiry_date.isoformat(),
            days_until_expiry=days,
        )


def get_expiry_service(db: Database | None = None) -> ExpiryAlertService:
    """Return an ExpiryAlertService instance."""
    if db is None:
        db = get_db()
    return ExpiryAlertService(db)
