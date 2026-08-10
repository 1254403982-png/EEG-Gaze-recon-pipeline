import unittest
from unittest.mock import patch

from recon_pipeline.clock import Timestamp
from recon_pipeline.config import PolicyConfig
from recon_pipeline.models import (
    EEGFeatures,
    EyeFeatures,
    GazeFeatures,
    MultimodalState,
    SignalStatus,
    UIContext,
)
from recon_pipeline.policy import MultimodalPolicyEngine


def eeg(load=20.0, attention=None, status=SignalStatus.AVAILABLE):
    return EEGFeatures(
        timestamp=Timestamp.from_monotonic_ns(1_000_000_000),
        status=status,
        quality="pass" if status == SignalStatus.AVAILABLE else status.value,
        cognitive_load=load,
        attention=100.0 - load if attention is None else attention,
    )


def eye_gaze(
    dwell=1.0,
    count=2,
    duration=0.2,
    *,
    revisit_count=None,
    revisit_time=None,
    timestamp_ns=1_000_000_000,
    status=SignalStatus.AVAILABLE,
    mapping=None,
):
    return GazeFeatures(
        timestamp=Timestamp.from_monotonic_ns(timestamp_ns),
        status=status,
        quality="pass" if status == SignalStatus.AVAILABLE else status.value,
        primary_aoi="reading",
        valid_sample_ratio=1.0,
        metadata={"screen_mapping": mapping or {"valid": True}},
        eye=EyeFeatures(
            aoi_dwell_time=dwell,
            fixation_count=count,
            mean_fixation_duration=duration,
            aoi_revisit_count=revisit_count,
            aoi_revisit_time=revisit_time,
        ),
    )


def unavailable_gaze():
    return GazeFeatures(Timestamp.now(), SignalStatus.UNAVAILABLE, "unavailable")


def state(
    condition,
    eeg_value=None,
    gaze_value=None,
    phase="reading",
    trial_id="T01",
    slide_id=None,
    seconds_in_trial=60,
):
    return MultimodalState(
        session_id="S001",
        trial_id=trial_id,
        condition=condition,
        timestamp=Timestamp.now(),
        eeg=eeg_value or eeg(status=SignalStatus.UNAVAILABLE),
        gaze=gaze_value or unavailable_gaze(),
        ui=UIContext(phase=phase, slide_id=slide_id, seconds_in_trial=seconds_in_trial),
    )


def policy_config(**overrides):
    values = {
        "cooldown_seconds": 0,
        "required_confirmations": 1,
        "minimum_evidence_seconds": 0,
        "eye_baseline_seconds": 0,
        "eye_baseline_min_samples": 1,
        "allow_degraded_c3": True,
        "require_screen_mapping": True,
        "max_multimodal_skew_ms": 5000,
    }
    values.update(overrides)
    return PolicyConfig(**values)


def prime_baseline(engine, condition=2, eeg_value=None, gaze_value=None):
    return engine.evaluate(state(condition, eeg_value, gaze_value or eye_gaze()))


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.engine = MultimodalPolicyEngine(policy_config())

    def test_c1_never_uses_biosignals(self):
        decision = self.engine.evaluate(state(1, eeg(), eye_gaze()))
        self.assertEqual(decision.action, "no_adaptation")
        self.assertEqual(decision.sources_used, [])

    def test_c2_requires_eye_and_never_falls_back_to_eeg(self):
        decision = self.engine.evaluate(state(2, eeg(90), None))
        self.assertEqual(decision.action, "hold")
        self.assertEqual(decision.sources_used, [])
        self.assertIn("required_eye_unavailable", decision.reason_codes)

    def test_c2_uses_only_personal_baseline_eye_ratios(self):
        prime_baseline(self.engine)
        decision = self.engine.evaluate(
            state(2, eeg(90), eye_gaze(1.6, 4, 0.32, timestamp_ns=2_000_000_000))
        )

        self.assertEqual(decision.sources_used, ["eye"])
        self.assertEqual(decision.explanation_level, "example")
        self.assertAlmostEqual(decision.difficulty_score, 1.72)
        self.assertAlmostEqual(decision.component_scores["aoi_dwell_ratio"], 1.6)
        self.assertAlmostEqual(decision.component_scores["fixation_count_ratio"], 2.0)

    def test_c2_strong_single_core_spike_offers_example_help(self):
        prime_baseline(self.engine)
        decision = self.engine.evaluate(
            state(2, gaze_value=eye_gaze(2.5, 2, 0.2, timestamp_ns=2_000_000_000))
        )

        self.assertEqual(decision.explanation_level, "example")
        self.assertGreaterEqual(decision.difficulty_score, 1.5)

    def test_c2_revisit_metrics_contribute_to_eye_difficulty(self):
        prime_baseline(
            self.engine,
            gaze_value=eye_gaze(revisit_count=0, revisit_time=0.0),
        )
        decision = self.engine.evaluate(
            state(
                2,
                gaze_value=eye_gaze(
                    revisit_count=2,
                    revisit_time=0.5,
                    timestamp_ns=2_000_000_000,
                ),
            )
        )

        self.assertIn("aoi_revisit_count_ratio", decision.component_scores)
        self.assertIn("aoi_revisit_time_ratio", decision.component_scores)
        self.assertIn("eye_ratio_aoi_revisit_count_ratio", decision.reason_codes)

    def test_c2_single_moderate_eye_feature_spike_does_not_offer_brief_help(self):
        prime_baseline(self.engine)
        decision = self.engine.evaluate(
            state(2, gaze_value=eye_gaze(0.5, 1, 0.31, timestamp_ns=2_000_000_000))
        )

        self.assertLess(decision.difficulty_score, self.engine.config.eye_mild_threshold)
        self.assertEqual(decision.explanation_level, "none")
        self.assertNotIn("eye_single_feature_spike", decision.reason_codes)

    def test_c3_case_1_eye_and_eeg_normal(self):
        prime_baseline(self.engine, 3, eeg(20))
        decision = self.engine.evaluate(
            state(3, eeg(20), eye_gaze(timestamp_ns=2_000_000_000))
        )
        self.assertEqual(decision.explanation_level, "none")
        self.assertIn("c3_eye_and_eeg_normal", decision.reason_codes)

    def test_c3_case_2_eye_abnormal_eeg_normal_is_reduced(self):
        prime_baseline(self.engine, 3, eeg(20))
        decision = self.engine.evaluate(
            state(3, eeg(20), eye_gaze(2.2, 5, 0.5, timestamp_ns=2_000_000_000))
        )
        self.assertEqual(decision.explanation_level, "brief")
        self.assertIn("c3_eye_only_abnormal_intervention_reduced", decision.reason_codes)

    def test_c3_case_3_eye_abnormal_and_load_elevated(self):
        prime_baseline(self.engine, 3, eeg(50, attention=60))
        decision = self.engine.evaluate(
            state(3, eeg(50, attention=60), eye_gaze(1.6, 4, 0.32, timestamp_ns=2_000_000_000))
        )
        self.assertEqual(decision.explanation_level, "example")
        self.assertEqual(decision.sources_used, ["eye", "eeg"])
        self.assertIn("c3_eye_and_eeg_difficulty_agree", decision.reason_codes)

    def test_c3_v2_uses_eeg_to_suppress_unconfirmed_gaze_anomaly(self):
        engine = MultimodalPolicyEngine(policy_config(c3_policy_version="v2"))
        prime_baseline(engine, 3, eeg(20))
        decision = engine.evaluate(
            state(3, eeg(20), eye_gaze(2.2, 5, 0.5, timestamp_ns=2_000_000_000))
        )

        self.assertEqual(decision.explanation_level, "none")
        self.assertIn(
            "c3_v2_eye_difficulty_not_confirmed_by_eeg", decision.reason_codes
        )

    def test_c3_v2_detects_covert_high_workload_not_visible_in_gaze(self):
        engine = MultimodalPolicyEngine(policy_config(c3_policy_version="v2"))
        prime_baseline(engine, 3, eeg(80))
        decision = engine.evaluate(
            state(3, eeg(80), eye_gaze(timestamp_ns=2_000_000_000))
        )

        self.assertEqual(decision.explanation_level, "example")
        self.assertEqual(decision.sources_used, ["eye", "eeg"])
        self.assertIn("c3_v2_covert_high_workload_eeg_only", decision.reason_codes)

    def test_c3_v2_concordant_evidence_offers_example(self):
        engine = MultimodalPolicyEngine(policy_config(c3_policy_version="v2"))
        prime_baseline(engine, 3, eeg(50))
        decision = engine.evaluate(
            state(3, eeg(50), eye_gaze(1.6, 4, 0.32, timestamp_ns=2_000_000_000))
        )

        self.assertEqual(decision.explanation_level, "example")
        self.assertIn("c3_v2_eye_and_eeg_difficulty_agree", decision.reason_codes)

    def test_c3_case_4_high_workload_and_eye_difficulty(self):
        prime_baseline(self.engine, 3, eeg(80, attention=20))
        decision = self.engine.evaluate(
            state(3, eeg(80, attention=20), eye_gaze(1.3, 3, 0.26, timestamp_ns=2_000_000_000))
        )
        self.assertEqual(decision.explanation_level, "brief")
        self.assertIn("c3_eeg_only_abnormal_intervention_reduced", decision.reason_codes)

    def test_c3_does_not_require_derived_attention(self):
        value = eeg(50)
        value.attention = None
        prime_baseline(self.engine, 3, value)
        decision = self.engine.evaluate(
            state(3, value, eye_gaze(1.6, 4, 0.32, timestamp_ns=2_000_000_000))
        )
        self.assertEqual(decision.explanation_level, "example")
        self.assertEqual(decision.sources_used, ["eye", "eeg"])

    def test_c3_case_5_low_quality_eeg_degrades_to_eye_only(self):
        warning = eeg(90, status=SignalStatus.WARNING)
        prime_baseline(self.engine, 3, warning)
        decision = self.engine.evaluate(
            state(3, warning, eye_gaze(1.6, 4, 0.32, timestamp_ns=2_000_000_000))
        )
        self.assertEqual(decision.explanation_level, "example")
        self.assertEqual(decision.sources_used, ["eye"])
        self.assertEqual(decision.degraded_mode, "eye_only_low_eeg_quality")
        self.assertEqual(decision.component_scores["eeg_quality_confidence"], 0.0)

    def test_quiz_phase_disables_policy_even_with_valid_signals(self):
        decision = self.engine.evaluate(state(3, eeg(90), eye_gaze(), phase="quiz"))
        self.assertEqual(decision.action, "no_adaptation")
        self.assertTrue(decision.suppressed)
        self.assertIn("ui_phase_policy_disabled", decision.reason_codes)

    def test_ai_content_review_metadata_disables_policy(self):
        current = state(3, eeg(90), eye_gaze())
        current.ui.metadata = {
            "policy_suppressed": True,
            "policy_suppression_reason": "ai_content_review",
        }
        decision = self.engine.evaluate(current)

        self.assertEqual(decision.action, "no_adaptation")
        self.assertTrue(decision.suppressed)
        self.assertIn("ui_policy_suppressed", decision.reason_codes)
        self.assertIn("ai_content_review", decision.reason_codes)

    def test_gaze_on_ai_panel_disables_policy(self):
        current = eye_gaze(
            mapping={
                "valid": True,
                "target": {"policy_region": "ai_panel", "tag": "chatMessages"},
            }
        )
        decision = self.engine.evaluate(state(2, gaze_value=current))
        self.assertEqual(decision.action, "hold")
        self.assertIn("gaze_on_ai_panel", decision.reason_codes)

    def test_mapping_from_previous_trial_is_held(self):
        previous_layout = {
            "valid": True,
            "trial_id": "T00",
            "slide_id": "old-slide",
        }
        decision = self.engine.evaluate(
            state(2, gaze_value=eye_gaze(mapping=previous_layout), trial_id="T01")
        )
        self.assertEqual(decision.action, "hold")
        self.assertIn("screen_mapping_trial_mismatch", decision.reason_codes)

    def test_trial_start_window_suppresses_automatic_offer(self):
        decision = self.engine.evaluate(
            state(
                2,
                eeg_value=eeg(90),
                gaze_value=eye_gaze(2.2, 5, 0.5),
                seconds_in_trial=5,
            )
        )
        self.assertEqual(decision.action, "hold")
        self.assertIn("trial_reading_baseline_window", decision.reason_codes)

    def test_missing_trial_elapsed_is_treated_as_start_window(self):
        decision = self.engine.evaluate(
            state(
                2,
                eeg_value=eeg(90),
                gaze_value=eye_gaze(2.2, 5, 0.5),
                seconds_in_trial=None,
            )
        )
        self.assertEqual(decision.action, "hold")
        self.assertIn("trial_reading_baseline_window", decision.reason_codes)

    def test_c2_baseline_is_collected_inside_start_window(self):
        engine = MultimodalPolicyEngine(
            policy_config(eye_baseline_seconds=5, minimum_trial_seconds=15)
        )
        normal = eye_gaze(timestamp_ns=1_000_000_000)
        for second in range(0, 6):
            decision = engine.evaluate(
                state(
                    2,
                    gaze_value=normal,
                    seconds_in_trial=second,
                )
            )
            normal = eye_gaze(timestamp_ns=(second + 2) * 1_000_000_000)
        self.assertIn("trial_reading_baseline_window", decision.reason_codes)
        self.assertIsNotNone(engine._eye_baseline)

        difficult = engine.evaluate(
            state(
                2,
                gaze_value=eye_gaze(2.0, 5, 0.5, timestamp_ns=9_000_000_000),
                seconds_in_trial=15,
            )
        )
        self.assertNotIn("eye_personal_baseline_collecting", difficult.reason_codes)
        self.assertIn("eye_difficulty_score", difficult.component_scores)

    def test_personal_baseline_requires_configured_time_span(self):
        engine = MultimodalPolicyEngine(
            policy_config(eye_baseline_seconds=10, eye_baseline_min_samples=3)
        )
        first = engine.evaluate(state(2, gaze_value=eye_gaze(timestamp_ns=1_000_000_000)))
        second = engine.evaluate(state(2, gaze_value=eye_gaze(timestamp_ns=6_000_000_000)))
        ready = engine.evaluate(state(2, gaze_value=eye_gaze(timestamp_ns=11_000_000_000)))
        self.assertIn("eye_personal_baseline_collecting", first.reason_codes)
        self.assertIn("eye_personal_baseline_collecting", second.reason_codes)
        self.assertNotIn("eye_personal_baseline_collecting", ready.reason_codes)

    def test_policy_requires_sustained_evidence_and_emits_once_per_episode(self):
        engine = MultimodalPolicyEngine(
            policy_config(required_confirmations=2, minimum_evidence_seconds=2.0)
        )
        prime_baseline(engine)
        difficult = state(
            2,
            gaze_value=eye_gaze(2.2, 5, 0.5, timestamp_ns=2_000_000_000),
        )
        with patch(
            "recon_pipeline.policy.engine.time.monotonic",
            side_effect=[10.0, 11.0, 12.1, 12.2],
        ):
            first = engine.evaluate(difficult)
            second = engine.evaluate(difficult)
            emitted = engine.evaluate(difficult)
            duplicate = engine.evaluate(difficult)
        self.assertEqual(first.action, "hold")
        self.assertEqual(second.action, "hold")
        self.assertFalse(emitted.suppressed)
        self.assertEqual(duplicate.action, "hold")
        self.assertIn("already_emitted_for_current_episode", duplicate.reason_codes)

    def test_trial_offer_budget_limits_two_offers_and_resets_on_next_trial(self):
        engine = MultimodalPolicyEngine(
            policy_config(max_automatic_offers_per_trial=2)
        )
        prime_baseline(engine)

        def difficult(trial_id, timestamp_ns):
            return state(
                2,
                gaze_value=eye_gaze(2.2, 5, 0.5, timestamp_ns=timestamp_ns),
                trial_id=trial_id,
            )

        def normal(trial_id, timestamp_ns):
            return state(
                2,
                gaze_value=eye_gaze(timestamp_ns=timestamp_ns),
                trial_id=trial_id,
            )

        first = engine.evaluate(difficult("T01", 2_000_000_000))
        engine.evaluate(normal("T01", 3_000_000_000))
        second = engine.evaluate(difficult("T01", 4_000_000_000))
        engine.evaluate(normal("T01", 5_000_000_000))
        blocked = engine.evaluate(difficult("T01", 6_000_000_000))
        next_trial = engine.evaluate(difficult("T02", 7_000_000_000))

        self.assertNotEqual(first.action, "hold")
        self.assertNotEqual(second.action, "hold")
        self.assertEqual(blocked.action, "hold")
        self.assertIn("trial_offer_budget_reached", blocked.reason_codes)
        self.assertNotEqual(next_trial.action, "hold")
        self.assertEqual(next_trial.component_scores["trial_offer_count"], 1.0)

    def test_zero_trial_offer_limit_is_unlimited(self):
        engine = MultimodalPolicyEngine(
            policy_config(max_automatic_offers_per_trial=0)
        )
        prime_baseline(engine)
        emitted = []
        for index in range(3):
            base_ns = (index * 2 + 2) * 1_000_000_000
            emitted.append(
                engine.evaluate(
                    state(
                        2,
                        gaze_value=eye_gaze(2.2, 5, 0.5, timestamp_ns=base_ns),
                    )
                )
            )
            engine.evaluate(
                state(
                    2,
                    gaze_value=eye_gaze(timestamp_ns=base_ns + 1_000_000_000),
                )
            )

        self.assertTrue(all(decision.action != "hold" for decision in emitted))
        self.assertEqual(
            [decision.component_scores["trial_offer_count"] for decision in emitted],
            [1.0, 2.0, 3.0],
        )

    def test_participant_response_releases_same_level_for_new_episode(self):
        engine = MultimodalPolicyEngine(policy_config())
        prime_baseline(engine)
        difficult = state(
            2,
            gaze_value=eye_gaze(2.2, 5, 0.5, timestamp_ns=2_000_000_000),
        )
        first = engine.evaluate(difficult)
        self.assertNotEqual(first.action, "hold")
        engine.release_offer("T01")
        second = engine.evaluate(
            state(
                2,
                gaze_value=eye_gaze(2.2, 5, 0.5, timestamp_ns=3_000_000_000),
            )
        )
        self.assertNotEqual(second.action, "hold")


if __name__ == "__main__":
    unittest.main()
