"""
Core Banking System (CBS) Integration Adapters.

Mock/simulation adapters for India's four major CBS platforms.
Each adapter injects behavioral risk scores as custom parameters
into the bank's existing transaction processing pipeline.

Supported Platforms:
- Infosys Finacle (SBI, ICICI, Axis — 65%+ market share)
- TCS BaNCS (HDFC, Bank of Baroda, Deutsche Bank India)
- Oracle FLEXCUBE (Canara Bank, Union Bank, PNB)
- Temenos T24 (YES Bank, IndusInd, Federal Bank)

Compliance: RBI Master Direction 2021 — real-time risk integration.
"""

import hashlib
import hmac
import json
import time
import logging
from abc import ABC, abstractmethod
from typing import Dict, Optional, List, Callable, TypeVar
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Lightweight circuit breaker for external service calls.

    States:
        CLOSED   — normal operation, failures are counted.
        OPEN     — calls are short-circuited; after ``cooldown_s`` we move to HALF_OPEN.
        HALF_OPEN — one probe call is allowed; success → CLOSED, failure → OPEN.
    """

    def __init__(self, failure_threshold: int = 5, cooldown_s: float = 30.0):
        self.failure_threshold = failure_threshold
        self.cooldown_s = cooldown_s
        self.state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float = 0.0

    def call(self, fn: Callable[..., T], *args, **kwargs) -> T:
        """Execute ``fn`` through the circuit breaker."""
        if self.state == CircuitState.OPEN:
            if time.monotonic() - self._last_failure_time >= self.cooldown_s:
                self.state = CircuitState.HALF_OPEN
                logger.info("Circuit breaker transitioning to HALF_OPEN (probe)")
            else:
                raise ExternalCallError(
                    f"Circuit breaker OPEN — call rejected (cooldown {self.cooldown_s}s)"
                )

        try:
            result = fn(*args, **kwargs)
            self._on_success()
            return result
        except Exception as exc:
            self._on_failure()
            raise exc

    def _on_success(self):
        self._failure_count = 0
        if self.state == CircuitState.HALF_OPEN:
            logger.info("Circuit breaker CLOSED after successful probe")
        self.state = CircuitState.CLOSED

    def _on_failure(self):
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if self._failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning(
                "Circuit breaker OPENED after %d consecutive failures",
                self._failure_count,
            )
        elif self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            logger.warning("Circuit breaker re-OPENED after failed probe")


class ExternalCallError(Exception):
    """Raised when a CBS call fails or is rejected by the circuit breaker."""

    pass


class CBSAdapter(ABC):
    """Abstract base class for Core Banking System integration.

    All CBS adapters must implement:
    - inject_risk_score(): Push behavioral risk into transaction pipeline
    - query_transaction_history(): Pull recent transaction context
    - validate_session(): Validate session against CBS session manager
    - get_customer_risk_profile(): Get customer's historic risk level

    A per-adapter CircuitBreaker protects all outbound calls.
    """

    def __init__(self, config: Dict):
        self.config = config
        self.api_base_url = config.get("api_base_url", "")
        self.api_key = config.get("api_key", "")
        self.timeout_ms = config.get("timeout_ms", 5000)
        self.connected = False
        self.breaker = CircuitBreaker(
            failure_threshold=config.get("circuit_breaker_threshold", 5),
            cooldown_s=config.get("circuit_breaker_cooldown_s", 30.0),
        )

    @abstractmethod
    def inject_risk_score(
        self,
        transaction_id: str,
        behavioral_score: float,
        duress_score: float,
        risk_factors: Dict,
    ) -> Dict:
        """Inject behavioral risk score into CBS transaction pipeline."""
        pass

    @abstractmethod
    def query_transaction_history(self, account_id: str, days: int = 30) -> List[Dict]:
        """Query recent transaction history for risk context."""
        pass

    @abstractmethod
    def validate_session(self, session_id: str, customer_id: str) -> bool:
        """Validate behavioral session against CBS session manager."""
        pass

    @abstractmethod
    def get_customer_risk_profile(self, customer_id: str) -> Dict:
        """Get customer's aggregate risk profile from CBS."""
        pass

    def call_with_breaker(self, fn: Callable[..., T], *args, **kwargs) -> T:
        """Execute a CBS call through the circuit breaker."""
        return self.breaker.call(fn, *args, **kwargs)

    def health_check(self) -> Dict:
        """CBS connection health check."""
        return {
            "platform": self.__class__.__name__,
            "connected": self.connected,
            "api_base_url": self.api_base_url,
            "latency_ms": self._measure_latency(),
            "circuit_breaker": self.breaker.state.value,
        }

    def _measure_latency(self) -> float:
        """Measure round-trip latency (mock)."""
        return 12.5  # Simulated 12.5ms latency


class FinacleAdapter(CBSAdapter):
    """Infosys Finacle CBS Adapter.

    Market: SBI, ICICI Bank, Axis Bank, Bank of India
    Integration: REST API via Finacle Connect Platform
    Risk Engine: FINRISK real-time risk scoring

    Behavioral score injection point:
    POST /finacle/api/v1/transactions/{txn_id}/risk-overlay
    """

    def __init__(self, config: Dict = None):
        super().__init__(config or {})
        self.platform = "Finacle"
        self.api_version = "v1"
        self.connected = True  # Mock — always connected

    def inject_risk_score(
        self,
        transaction_id: str,
        behavioral_score: float,
        duress_score: float,
        risk_factors: Dict,
    ) -> Dict:
        """Inject behavioral risk into Finacle FINRISK engine.

        Finacle uses a 1-100 risk scale. We map our 0.0-1.0 score
        to Finacle's scale and inject via the risk-overlay API.
        """
        finacle_risk_score = int(behavioral_score * 100)
        finacle_duress_flag = duress_score > 0.75

        # Simulate Finacle API call
        payload = {
            "txnRefNo": transaction_id,
            "riskOverlay": {
                "behavioralRiskScore": finacle_risk_score,
                "duressFlag": finacle_duress_flag,
                "duressConfidence": round(duress_score, 4),
                "riskFactors": {
                    "keystrokeAnomaly": risk_factors.get("keystroke_anomaly", 0),
                    "mouseAnomaly": risk_factors.get("mouse_anomaly", 0),
                    "sessionDeviation": risk_factors.get("session_deviation", 0),
                    "deviceTrust": risk_factors.get("device_trust", 1.0),
                },
                "source": "behavioral_biometrics_engine",
                "version": "2.0",
                "timestamp": datetime.now().isoformat(),
            },
        }

        logger.info(
            f"[Finacle] Risk overlay injected for txn {transaction_id}: "
            f"score={finacle_risk_score}, duress={finacle_duress_flag}"
        )

        # Simulate response
        return {
            "status": "accepted",
            "txnRefNo": transaction_id,
            "riskDecision": self._finacle_risk_decision(finacle_risk_score),
            "processingTimeMs": 8.3,
        }

    def query_transaction_history(self, account_id: str, days: int = 30) -> List[Dict]:
        """Query Finacle transaction history (mock)."""
        return [
            {
                "txnRefNo": f"FIN{account_id}001",
                "amount": 5000.00,
                "type": "NEFT",
                "date": "2024-01-15",
                "status": "completed",
                "riskScore": 15,
            }
        ]

    def validate_session(self, session_id: str, customer_id: str) -> bool:
        """Validate against Finacle session manager (mock)."""
        return True

    def get_customer_risk_profile(self, customer_id: str) -> Dict:
        """Get customer risk profile from Finacle (mock)."""
        return {
            "customerId": customer_id,
            "riskCategory": "low",
            "historicFraudCount": 0,
            "averageTransactionAmount": 15000.0,
            "accountAgeMonths": 36,
            "kycStatus": "complete",
        }

    def _finacle_risk_decision(self, score: int) -> str:
        if score > 80:
            return "BLOCK"
        elif score > 60:
            return "STEP_UP"
        elif score > 40:
            return "MONITOR"
        else:
            return "ALLOW"


class BaNCSAdapter(CBSAdapter):
    """TCS BaNCS CBS Adapter.

    Market: HDFC Bank, Bank of Baroda, Deutsche Bank India
    Integration: BaNCS Open API Platform
    """

    def __init__(self, config: Dict = None):
        super().__init__(config or {})
        self.platform = "BaNCS"
        self.connected = True

    def inject_risk_score(
        self,
        transaction_id: str,
        behavioral_score: float,
        duress_score: float,
        risk_factors: Dict,
    ) -> Dict:
        bancs_score = round(behavioral_score * 1000)  # BaNCS uses 0-1000
        payload = {
            "transactionId": transaction_id,
            "riskAssessment": {
                "behavioralScore": bancs_score,
                "duressIndicator": duress_score > 0.75,
                "assessmentSource": "behavioral_biometrics",
            },
        }
        logger.info(f"[BaNCS] Risk injected for txn {transaction_id}: {bancs_score}")
        return {
            "status": "accepted",
            "decision": "ALLOW" if bancs_score < 600 else "REVIEW",
        }

    def query_transaction_history(self, account_id: str, days: int = 30) -> List[Dict]:
        return []

    def validate_session(self, session_id: str, customer_id: str) -> bool:
        return True

    def get_customer_risk_profile(self, customer_id: str) -> Dict:
        return {"customerId": customer_id, "riskBand": "A", "kycComplete": True}


class FLEXCUBEAdapter(CBSAdapter):
    """Oracle FLEXCUBE CBS Adapter.

    Market: Canara Bank, Union Bank, PNB
    Integration: FLEXCUBE REST API Sidecar
    """

    def __init__(self, config: Dict = None):
        super().__init__(config or {})
        self.platform = "FLEXCUBE"
        self.connected = True

    def inject_risk_score(
        self,
        transaction_id: str,
        behavioral_score: float,
        duress_score: float,
        risk_factors: Dict,
    ) -> Dict:
        fc_score = round(behavioral_score, 4)
        logger.info(f"[FLEXCUBE] Risk injected for txn {transaction_id}: {fc_score}")
        return {"status": "accepted", "riskScore": fc_score}

    def query_transaction_history(self, account_id: str, days: int = 30) -> List[Dict]:
        return []

    def validate_session(self, session_id: str, customer_id: str) -> bool:
        return True

    def get_customer_risk_profile(self, customer_id: str) -> Dict:
        return {"customerId": customer_id, "riskLevel": "LOW"}


class T24Adapter(CBSAdapter):
    """Temenos T24 CBS Adapter.

    Market: YES Bank, IndusInd Bank, Federal Bank
    Integration: T24 OFS (Open Financial Services) Framework
    """

    def __init__(self, config: Dict = None):
        super().__init__(config or {})
        self.platform = "T24"
        self.connected = True

    def inject_risk_score(
        self,
        transaction_id: str,
        behavioral_score: float,
        duress_score: float,
        risk_factors: Dict,
    ) -> Dict:
        ofs_risk = (
            "H" if behavioral_score > 0.7 else "M" if behavioral_score > 0.4 else "L"
        )
        logger.info(f"[T24] OFS risk band for txn {transaction_id}: {ofs_risk}")
        return {"status": "accepted", "ofsBand": ofs_risk}

    def query_transaction_history(self, account_id: str, days: int = 30) -> List[Dict]:
        return []

    def validate_session(self, session_id: str, customer_id: str) -> bool:
        return True

    def get_customer_risk_profile(self, customer_id: str) -> Dict:
        return {"customerId": customer_id, "tier": "RETAIL"}


# ── Factory ─────────────────────────────────────────────────────────────

CBS_ADAPTERS = {
    "finacle": FinacleAdapter,
    "bancs": BaNCSAdapter,
    "flexcube": FLEXCUBEAdapter,
    "t24": T24Adapter,
}


def get_cbs_adapter(platform: str, config: Dict = None) -> CBSAdapter:
    """Factory function for CBS adapter creation.

    Args:
        platform: One of 'finacle', 'bancs', 'flexcube', 't24'
        config: Platform-specific configuration dict
    """
    adapter_cls = CBS_ADAPTERS.get(platform.lower())
    if not adapter_cls:
        raise ValueError(
            f"Unknown CBS platform: {platform}. Supported: {list(CBS_ADAPTERS.keys())}"
        )
    return adapter_cls(config or {})
