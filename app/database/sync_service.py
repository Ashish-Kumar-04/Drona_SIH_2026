"""
Offline-First Synchronization Service.
Implements Section 18 of SIH 25073 specification (Offline Storage -> Pending Sync -> Automatic Sync -> Cloud Server).
"""

from sqlalchemy.orm import Session
from app.models.db_models import Assessment
from typing import List, Dict, Any

class OfflineSyncService:
    @staticmethod
    def get_pending_sync(db: Session) -> List[Assessment]:
        """Fetch all assessments that were performed offline and are pending sync."""
        return db.query(Assessment).filter(Assessment.sync_status == "PENDING").all()

    @staticmethod
    def mark_as_synced(db: Session, assessment_ids: List[str]) -> int:
        """Update assessments sync status to SYNCED upon successful server acknowledgement."""
        updated = db.query(Assessment).filter(Assessment.assessment_id.in_(assessment_ids)).update(
            {"sync_status": "SYNCED"}, synchronize_session=False
        )
        db.commit()
        return updated

    @staticmethod
    def sync_incoming_assessments(db: Session, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Process incoming offline assessments from client devices."""
        synced_ids = []
        for item in items:
            existing = db.query(Assessment).filter(Assessment.assessment_id == item["assessment_id"]).first()
            if not existing:
                assessment = Assessment(
                    assessment_id=item["assessment_id"],
                    athlete_id=item["athlete_id"],
                    test_type=item["test_type"],
                    raw_score=item["raw_score"],
                    normalized_score=item["normalized_score"],
                    confidence=item["confidence"],
                    validation_score=item["validation_score"],
                    timestamp=item.get("timestamp"),
                    status=item.get("status", "VALID"),
                    sync_status="SYNCED",
                    details_json=item.get("details_json")
                )
                db.add(assessment)
                synced_ids.append(item["assessment_id"])
            else:
                existing.sync_status = "SYNCED"
                synced_ids.append(existing.assessment_id)
        db.commit()
        return {"status": "SUCCESS", "synced_count": len(synced_ids), "synced_ids": synced_ids}
