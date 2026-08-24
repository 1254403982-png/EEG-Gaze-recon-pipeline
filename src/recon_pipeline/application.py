"""Application service coordinating synchronization, policy, and audit logs."""

from __future__ import annotations

import threading
from dataclasses import asdict
from typing import Any, Dict, Optional

from .clock import Timestamp, utc_now_iso
from .models import EEGFeatures, GazeFeatures, PolicyDecision, UIContext
from .policy import MultimodalPolicyEngine
from .storage import ExperimentRunManager, JsonlRecorder
from .synchronization import MultimodalSynchronizer


class ExperimentApplication:
    def __init__(
        self,
        synchronizer: MultimodalSynchronizer,
        policy: MultimodalPolicyEngine,
        event_recorder: JsonlRecorder,
        policy_recorder: JsonlRecorder,
        *,
        interaction_recorder: Optional[JsonlRecorder] = None,
        run_manager: Optional[ExperimentRunManager] = None,
    ) -> None:
        self.synchronizer = synchronizer
        self.policy = policy
        self.event_recorder = event_recorder
        self.policy_recorder = policy_recorder
        self.interaction_recorder = interaction_recorder or event_recorder
        self.run_manager = run_manager
        self._lock = threading.Lock()
        self._latest_policy: Optional[PolicyDecision] = None
        self._pending_policy_offer: Optional[PolicyDecision] = None

    def start_session(
        self,
        session_id: str,
        condition: int = 1,
        *,
        resume_stamp: Optional[str] = None,
    ) -> dict:
        if self.run_manager is not None:
            self.run_manager.start_session(session_id, condition, resume_stamp=resume_stamp)
        self.synchronizer.start_session(session_id, condition=condition)
        self.policy.reset()
        with self._lock:
            self._latest_policy = None
            self._pending_policy_offer = None
        self._record_event("session_started", {"condition": condition}, session_id=session_id)
        result = self.snapshot()
        if self.run_manager is not None:
            result["run_stamp"] = self.run_manager.current_stamp
        return result

    def set_condition(self, condition: int) -> PolicyDecision:
        if self.run_manager is not None:
            self.run_manager.set_condition(condition)
        self.synchronizer.set_condition(condition)
        self.policy.reset()
        self._record_event("condition_changed", {"condition": condition})
        return self.evaluate_policy()

    def end_session(self) -> dict:
        state = self.synchronizer.snapshot()
        self._record_event("session_ended", {"phase": state.ui.phase})
        if self.run_manager is not None:
            self.run_manager.end_session()
        return {"ok": True, "session_id": state.session_id, "recording": False}

    def record_interaction(self, action: str, payload: Dict[str, Any]) -> dict:
        clean_action = str(action).strip()[:80]
        if not clean_action:
            raise ValueError("interaction action must not be empty.")
        state = self.synchronizer.snapshot()
        timestamp = Timestamp.now()
        record = {
            "schema_version": "2.0",
            "event_type": "interaction",
            "action": clean_action,
            "session_id": state.session_id,
            "trial_id": state.trial_id,
            "condition": state.condition,
            "phase": state.ui.phase,
            "timestamp": timestamp.to_dict(),
            "synchronization": state.to_dict()["synchronization"],
            "payload": dict(payload),
        }
        self.interaction_recorder.append(record)
        return record

    def update_eeg(self, features: EEGFeatures) -> PolicyDecision:
        self.synchronizer.update_eeg(features)
        self._record_event("eeg_features", features.to_dict())
        return self.evaluate_policy()

    def update_gaze(self, features: GazeFeatures) -> PolicyDecision:
        self.synchronizer.update_gaze(features)
        self._record_event("gaze_features", features.to_dict())
        return self.evaluate_policy()

    def update_ui(self, context: UIContext, trial_id: Optional[str] = None) -> PolicyDecision:
        if trial_id is not None:
            self.synchronizer.set_trial(trial_id, context)
        else:
            self.synchronizer.update_ui(context)
        self._record_event("ui_context", asdict(context))
        return self.evaluate_policy()

    def evaluate_policy(self) -> PolicyDecision:
        state = self.synchronizer.snapshot()
        decision = self.policy.evaluate(state)
        released_trial: Optional[str] = None
        with self._lock:
            self._latest_policy = decision
            pending = self._pending_policy_offer
            if pending is not None and (
                pending.session_id != decision.session_id
                or pending.trial_id != decision.trial_id
                or pending.condition != decision.condition
            ):
                self._pending_policy_offer = None
                pending = None
            invalidating_reasons = {
                "ui_policy_suppressed",
                "gaze_on_ai_panel",
                "gaze_not_on_reading_content",
            }
            if pending is not None and invalidating_reasons.intersection(
                decision.reason_codes
            ):
                # A latched reading-area offer must not reappear after the
                # participant moves into the assistant panel.
                released_trial = pending.trial_id
                self._pending_policy_offer = None
                pending = None
            if _is_actionable_offer(decision) and pending is None:
                self._pending_policy_offer = decision
        if released_trial is not None:
            self.policy.release_offer(released_trial)
        self.policy_recorder.append(decision.to_dict())
        return decision

    def latest_policy(self) -> dict:
        with self._lock:
            decision = self._pending_policy_offer or self._latest_policy
        return decision.to_dict() if decision else self.evaluate_policy().to_dict()

    def acknowledge_policy(
        self, policy_id: Optional[int] = None, response: Optional[str] = None
    ) -> dict:
        """Clear a latched offer after the experiment UI has received it."""

        with self._lock:
            pending = self._pending_policy_offer
            if pending is None:
                return {"ok": True, "acknowledged": False, "policy_id": None}
            if policy_id is not None and pending.policy_id != policy_id:
                return {
                    "ok": True,
                    "acknowledged": False,
                    "policy_id": pending.policy_id,
                    "reason": "policy_id_mismatch",
                }
            self._pending_policy_offer = None
            normalized_response = str(response or "").strip().lower()
            # The browser can suppress an already-answered area/level before
            # rendering another prompt.  Treat that as an acknowledgement too,
            # otherwise the latched server offer would be returned on every poll.
            if normalized_response in {"accepted", "rejected", "suppressed_area_history"}:
                self.policy.release_offer(pending.trial_id)
            return {
                "ok": True,
                "acknowledged": True,
                "policy_id": pending.policy_id,
                "response": normalized_response or None,
            }

    def snapshot(self) -> dict:
        state = self.synchronizer.snapshot()
        return {
            "ok": True,
            "state": state.to_dict(),
            "policy": self.latest_policy(),
        }

    def recording_context(self) -> dict:
        """Return identifiers needed to attribute an acquisition chunk."""

        state = self.synchronizer.snapshot()
        return {
            "session_id": state.session_id,
            "trial_id": state.trial_id,
            "condition": state.condition,
            "phase": state.ui.phase,
        }

    def _record_event(
        self,
        event_type: str,
        payload: Dict[str, Any],
        *,
        session_id: Optional[str] = None,
    ) -> None:
        state = self.synchronizer.snapshot()
        self.event_recorder.append(
            {
                "schema_version": "1.0",
                "event_type": event_type,
                "session_id": session_id or state.session_id,
                "trial_id": state.trial_id,
                "condition": state.condition,
                "timestamp": Timestamp.now().to_dict(),
                "recorded_at": utc_now_iso(),
                "payload": payload,
            }
        )


def _is_actionable_offer(decision: PolicyDecision) -> bool:
    return (
        decision.explanation_level != "none"
        and decision.action != "hold"
        and not decision.suppressed
    )
