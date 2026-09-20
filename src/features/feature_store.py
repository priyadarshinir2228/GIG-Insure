import os
import json
import hmac
import hashlib
from typing import Dict, Any, Optional

class FeatureStoreAdapter:
    """Sub-millisecond Policy Snapshot & Online Feature Store Manager (Redis/Feast simulator)."""

    SALT_KEY = b"gigease_privacy_vault_salt_2026"

    @classmethod
    def generate_worker_token(cls, raw_worker_id: str) -> str:
        """Decouples PII from ML feature store via HMAC-SHA256 pseudonymization."""
        return hmac.new(cls.SALT_KEY, raw_worker_id.encode("utf-8"), hashlib.sha256).hexdigest()[:16]

    def __init__(self):
        self._store: Dict[str, Any] = {}
        self._preload_defaults()

    def _preload_defaults(self):
        """Preloads default zone risk scores and policy feature snapshots."""
        self._store["feast:zone_risk:ZONE_BLR_01"] = {"zone_risk_score": 0.42, "h3_hex_id": "89618924b23ffff"}
        self._store["feast:zone_risk:ZONE_DEL_01"] = {"zone_risk_score": 0.58, "h3_hex_id": "89618925c47ffff"}
        self._store["feast:zone_risk:ZONE_BOM_01"] = {"zone_risk_score": 0.65, "h3_hex_id": "89618926a11ffff"}
        self._store["feast:zone_risk:ZONE_MAA_01"] = {"zone_risk_score": 0.72, "h3_hex_id": "89618927d35ffff"}
        self._store["feast:zone_risk:ZONE_HYD_01"] = {"zone_risk_score": 0.35, "h3_hex_id": "89618928e59ffff"}

    def get_policy_snapshot(self, worker_id: str) -> Dict[str, Any]:
        """Reads rider policy snapshot with sub-10ms response time guarantee."""
        key = f"policy:{worker_id}"
        if key in self._store:
            return self._store[key]
        
        # Fallback default snapshot
        snapshot = {
            "worker_id": worker_id,
            "w_avg": 4500.0,
            "coverage_amount": 6750.0,
            "weekly_premium": 84.0,
            "ncd_pct": 0.0,
            "claim_loading_pct": 0.0,
            "status": "ACTIVE"
        }
        self._store[key] = snapshot
        return snapshot

    def get_zone_risk_feature(self, zone_id: str) -> float:
        """Reads 30-day rolling zone risk score."""
        key = f"feast:zone_risk:{zone_id}"
        if key in self._store:
            return self._store[key]["zone_risk_score"]
        return 0.40

    def update_policy_snapshot(self, worker_id: str, new_features: Dict[str, Any]):
        """Updates online feature store after claim settlement or premium calculation."""
        key = f"policy:{worker_id}"
        current = self.get_policy_snapshot(worker_id)
        current.update(new_features)
        self._store[key] = current

feature_store = FeatureStoreAdapter()
