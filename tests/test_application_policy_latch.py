import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from recon_pipeline.application import ExperimentApplication
from recon_pipeline.clock import Timestamp
from recon_pipeline.models import PolicyDecision
from recon_pipeline.storage import JsonlRecorder


def decision(policy_id, action, reasons):
    return PolicyDecision(
        policy_id=policy_id,
        session_id="S001",
        trial_id="T01",
        condition=3,
        timestamp=Timestamp.now(),
        action=action,
        explanation_level="brief" if action.startswith("offer_") else "none",
        ui_mode="assistance" if action.startswith("offer_") else "normal",
        reason_codes=reasons,
        sources_available=["eye"],
        sources_used=["eye"],
    )


class ApplicationPolicyLatchTests(unittest.TestCase):
    def test_entering_ai_panel_discards_latched_offer(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            policy = SimpleNamespace(
                evaluate=lambda _state: decision(2, "hold", ["gaze_on_ai_panel"]),
                release_offer=lambda trial_id: released.append(trial_id),
            )
            released = []
            app = ExperimentApplication(
                SimpleNamespace(snapshot=lambda: object()),
                policy,
                JsonlRecorder(root / "events.jsonl"),
                JsonlRecorder(root / "policy.jsonl"),
            )
            app._pending_policy_offer = decision(1, "offer_brief_explanation", [])

            result = app.evaluate_policy()

            self.assertEqual(result.action, "hold")
            self.assertIsNone(app._pending_policy_offer)
            self.assertEqual(released, ["T01"])
            self.assertEqual(app.latest_policy()["policy_id"], 2)


if __name__ == "__main__":
    unittest.main()
