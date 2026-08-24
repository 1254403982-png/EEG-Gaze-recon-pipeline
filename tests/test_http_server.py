import json
import tempfile
import unittest
import urllib.request
from pathlib import Path

from recon_pipeline.application import ExperimentApplication
from recon_pipeline.clock import Timestamp
from recon_pipeline.config import PolicyConfig
from recon_pipeline.gaze.screen_mapping import MARKER_IDS, ScreenMapper
from recon_pipeline.gaze.tobii import SceneFrame
from recon_pipeline.policy import MultimodalPolicyEngine
from recon_pipeline.server import ExperimentHTTPServer
from recon_pipeline.storage import ExperimentRunManager, JsonDocumentStore, JsonlRecorder
from recon_pipeline.synchronization import MultimodalSynchronizer


class HTTPServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.events_path = root / "events.jsonl"
        self.app = ExperimentApplication(
            MultimodalSynchronizer(),
            MultimodalPolicyEngine(
                PolicyConfig(
                    cooldown_seconds=0,
                    required_confirmations=1,
                    minimum_evidence_seconds=0,
                    eye_baseline_seconds=0,
                    eye_baseline_min_samples=1,
                )
            ),
            JsonlRecorder(self.events_path),
            JsonlRecorder(root / "policies.jsonl"),
        )
        self.app.start_session("S001", condition=1)
        self.documents = root / "documents"
        self.screen_mapper = ScreenMapper()
        self.question_registry = ExperimentRunManager(root / "runs")
        self.calibration = {"status": "idle", "connected": True, "success": None}

        def start_calibration():
            self.calibration = {
                "status": "requested",
                "connected": True,
                "success": None,
            }
            return dict(self.calibration)

        self.server = ExperimentHTTPServer(
            self.app,
            port=0,
            document_store=JsonDocumentStore(self.documents),
            scene_frame_supplier=lambda: SceneFrame(
                jpeg=b"\xff\xd8test\xff\xd9",
                timestamp=Timestamp.now(device_seconds=12.5),
                width=640,
                height=360,
                gaze_x=0.4,
                gaze_y=0.6,
                gaze_trajectory=((0.3, 0.5, 500.0), (0.4, 0.6, 20.0)),
                trajectory_window_ms=3000.0,
            ),
            screen_mapping_supplier=self.screen_mapper.dashboard_snapshot,
            screen_layout_updater=self.screen_mapper.update_layout,
            tobii_calibration_supplier=lambda: dict(self.calibration),
            tobii_calibration_starter=start_calibration,
            question_registry=self.question_registry,
            eeg_acquisition_enabled=False,
        )
        self.server.start()
        self.base = "http://127.0.0.1:%s" % self.server.address[1]
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def tearDown(self):
        self.server.close()
        self.temp.cleanup()

    def test_condition_contract_and_c2_source_isolation(self):
        condition = self._get("/api/condition")
        self.assertEqual(condition["condition"], 1)
        self.assertEqual(condition["sources"], {"eeg": False, "gaze": False})

        self._post(
            "/api/ui/context",
            {"phase": "reading", "trial_id": "T01", "seconds_in_trial": 60},
        )
        decision = self._post("/api/condition", {"condition": 2})
        self.assertEqual(decision["action"], "hold")
        self.assertIn("required_eye_unavailable", decision["reason_codes"])

    def test_state_exposes_eye_schema_with_optional_revisit_metrics(self):
        self._post(
            "/api/gaze",
            {
                "status": "available",
                "quality": "pass",
                "valid_sample_ratio": 1.0,
                "eye": {
                    "aoi_dwell_time": 1.25,
                    "fixation_count": 4,
                    "mean_fixation_duration": 0.31,
                },
            },
        )

        eye = self._get("/api/state")["state"]["eye"]

        self.assertEqual(
            eye,
            {
                "aoi_dwell_time": 1.25,
                "fixation_count": 4,
                "mean_fixation_duration": 0.31,
                "aoi_revisit_count": None,
                "aoi_revisit_time": None,
            },
        )

    def test_rejects_a_second_server_on_the_same_port(self):
        with self.assertRaises(OSError):
            ExperimentHTTPServer(self.app, port=self.server.address[1])

    def test_serves_migrated_experiment_and_monitor_pages(self):
        home = self._raw("/")
        experiment = self._raw("/ui/experiment.html")
        monitor = self._raw("/ui/monitor.html")
        easy_question = self._raw("/ui/question_bank/easy/question_01.js")
        medium_question = self._raw("/ui/question_bank/medium/question_17.js")
        hard_question = self._raw("/ui/question_bank/hard/question_33.js")
        question_index = self._raw("/ui/question_bank/index.js")

        self.assertIn("Recon EEG Pipeline", home)
        self.assertIn("认知负荷实验", experiment)
        self.assertIn("实时数据监控", monitor)
        self.assertIn("window.questionBank.easy.push", easy_question)
        self.assertIn("window.questionBank.medium.push", medium_question)
        self.assertIn("window.questionBank.hard.push", hard_question)
        self.assertIn("const slides", question_index)
        self.assertIn("selectExplainLevel", experiment)
        self.assertNotIn("sendWithLevel", experiment)
        self.assertIn("acceptPolicySuggestion", experiment)
        self.assertIn("rejectPolicySuggestion", experiment)
        self.assertIn("data-policy-response=\"accept\"", experiment)
        self.assertIn("pendingPolicySuggestion.responseRow", experiment)
        self.assertIn("state.policyPollTimer = setInterval(pollPolicy, 400)", experiment)
        self.assertIn("acceptPolicySuggestion(responseRow)", experiment)
        self.assertIn("let policyPollInFlight = false", experiment)
        self.assertIn("let policyPromptPreparing = false", experiment)
        self.assertIn("function startPolicyQuietPeriod(seconds, reason)", experiment)
        self.assertIn("policyPostAIQuietMinimumSeconds: 45", experiment)
        self.assertIn('startPolicyQuietPeriod(reviewSeconds, "ai_content_review")', experiment)
        self.assertIn("policy_suppressed: state.condition === 3", experiment)
        self.assertIn("shown = await triggerPolicyExplanation", experiment)
        self.assertIn("lastPresentedPolicyId", experiment)
        self.assertIn("currentTrial !== triggerTrial", experiment)
        self.assertIn("inferenceResult?.policyBlocked", experiment)
        self.assertIn('mappedTarget?.policy_region === "ai_panel"', experiment)
        self.assertIn("context_text: contextElement.textContent", experiment)
        self.assertIn("targetText.length < 12 ? contextText : targetText", experiment)
        self.assertIn("Manual paste-and-send assistance remains available", experiment)
        self.assertIn(
            '$("sendBtn").disabled = state.inQuiz || state.aiBusy || '
            'state.policyInteractionLocked || !hasText;',
            experiment,
        )
        self.assertIn("function setPolicyInteractionLocked(locked)", experiment)
        self.assertIn("function resetChatPanelForTrial()", experiment)
        self.assertIn("internalPolicy: true", experiment)
        self.assertIn("function normalizeModelText(value)", experiment)
        self.assertIn(
            'options.explainLevel || state.lastExplainLevel || "简单解释"',
            experiment,
        )
        self.assertNotIn('document.addEventListener("contextmenu"', experiment)
        self.assertIn('id="decoderBadChannels"', monitor)
        self.assertIn('id="badChannelReasons"', monitor)
        self.assertIn('class="quiz-question-title"', experiment)
        self.assertIn('font-size:20px', experiment)
        self.assertNotIn("Condition C${state.condition}", experiment)
        self.assertIn('fitReadingContentToOnePage', experiment)
        self.assertIn('is-one-page-compact', experiment)
        self.assertIn('is-one-page-fit', experiment)

    def test_experiment_uses_only_the_requested_questionnaires(self):
        experiment = self._raw("/ui/experiment.html")

        trial_schema = experiment.split(
            "const TRIAL_SURVEY_SCHEMA = {", 1
        )[1].split("let trialQuestionnaireSubmitting", 1)[0]
        trial_item_ids = [
            line.strip().removeprefix('id: "').removesuffix('",')
            for line in trial_schema.splitlines()
            if line.strip().startswith('id: "')
        ]
        self.assertIn('version: "trial-survey-v1"', trial_schema)
        self.assertEqual(
            trial_item_ids,
            [
                "trial_mental_effort",
                "trial_confusion",
                "trial_understanding",
                "trial_help_need",
            ],
        )
        self.assertIn(
            'instruction: "请只根据刚才完成的这篇材料作答。请选择最符合你实际体验的选项。"',
            trial_schema,
        )
        self.assertIn(
            'scale: { min: 1, max: 7, left: "非常少", middle: "中等", right: "非常多" }',
            trial_schema,
        )
        self.assertIn(
            'scale: { min: 0, max: 2, left: "没有", '
            'middle: "有\uFF0C但需求较低", right: "有\uFF0C而且需求较高" }',
            trial_schema,
        )

        condition_schema = experiment.split(
            "const CONDITION_SURVEY_SCHEMA = {", 1
        )[1].split("const CONDITION_SURVEY_ITEMS", 1)[0]
        condition_items = condition_schema.split("items: [", 1)[1].split(
            "].map(item =>", 1
        )[0]
        condition_item_ids = [
            line.strip().removeprefix('id: "').removesuffix('",')
            for line in condition_items.splitlines()
            if line.strip().startswith('id: "')
        ]
        self.assertIn('version: "condition-survey-v3"', condition_schema)
        self.assertEqual(
            condition_item_ids,
            [
                "assistance_need_fit",
                "assistance_clarity",
                "assistance_personalization",
            ],
        )
        self.assertEqual(condition_schema.count("allowNotApplicable: true"), 1)
        self.assertNotIn("proactive_prompt_recalled", condition_schema)
        self.assertNotIn("系统是否曾在你没有主动发送问题的情况下", condition_schema)
        for removed_item in (
            "mental_effort",
            "task_difficulty",
            "core_understanding",
            "relational_understanding",
            "assistance_helpfulness",
            "assistance_timing",
            "assistance_interruption",
            "assistance_operation_burden",
            "assistance_control",
            "assistance_rejection_ease",
            "assistance_trust",
            "assistance_reuse_intention",
        ):
            self.assertNotIn(f'id: "{removed_item}"', condition_schema)

        self.assertNotIn('id="questionnairePage"', experiment)
        self.assertNotIn('id="finishQuestionnaireBtn"', experiment)
        self.assertNotIn("function openQuestionnaire()", experiment)
        self.assertNotIn('id="loadRating"', experiment)
        self.assertNotIn('id="diffRating"', experiment)
        self.assertNotIn('id="aiRating"', experiment)
        self.assertNotIn('id="qFeedback"', experiment)

    def test_questionnaires_cannot_be_bypassed(self):
        experiment = self._raw("/ui/experiment.html")

        self.assertIn('if (state.inQuiz) return;', experiment)
        self.assertIn(
            'if (e.key === "ArrowRight" && !state.inQuiz) $("nextBtn").click();',
            experiment,
        )
        self.assertIn('overlay.id !== "trialQModal"', experiment)
        self.assertIn('overlay.id !== "condQModal"', experiment)
        self.assertIn(
            'm.id !== "restModal" && m.id !== "trialQModal" && m.id !== "condQModal"',
            experiment,
        )
        self.assertIn('syncPipelineUIContext("trial_feedback"', experiment)
        self.assertIn('syncPipelineUIContext("condition_feedback")', experiment)

        flow = experiment.split('recordInteraction("trial_completed"', 1)[1].split(
            "/* ===== Modal & Toast ===== */", 1
        )[0]
        survey_call = flow.index("showTrialQuestionnaire(currentTrial, trial")
        trial_increment = flow.index("currentTrial++")
        next_rest = flow.index("showRestCalibration(currentTrial")
        condition_survey = flow.index("showConditionQuestionnaire(state.condition")
        self.assertLess(survey_call, trial_increment)
        self.assertLess(trial_increment, next_rest)
        self.assertLess(trial_increment, condition_survey)
        self.assertIn('recordInteraction("trial_questionnaire_started"', experiment)
        self.assertIn('recordInteraction("trial_questionnaire_submitted"', experiment)
        self.assertIn('questionnaireVersion: TRIAL_SURVEY_SCHEMA.version', experiment)
        self.assertIn('questionnaireVersion: CONDITION_SURVEY_SCHEMA.version', experiment)
        self.assertIn('responseLatenciesMs', experiment)

    def test_condition_questionnaire_retry_reuses_the_confirmed_record(self):
        experiment = self._raw("/ui/experiment.html")
        questionnaire_block = experiment.split(
            "/* ===== Condition Questionnaire ===== */", 1
        )[1].split("/* ===== Ten-second resting calibration", 1)[0]
        retry_handler = questionnaire_block.split("} catch (error) {", 1)[1].split(
            "      };", 1
        )[0]

        self.assertIn("let pendingConditionSurveyRecord = null;", questionnaire_block)
        self.assertIn(
            "const isFinalizeRetry = pendingConditionSurveyRecord !== null;",
            questionnaire_block,
        )
        self.assertIn(
            "responses: pendingConditionSurveyRecord.answers,",
            questionnaire_block,
        )
        self.assertIn(
            "notApplicable: pendingConditionSurveyRecord.notApplicable,",
            questionnaire_block,
        )
        self.assertIn(
            "responseLatenciesMs: pendingConditionSurveyRecord.responseLatenciesMs,",
            questionnaire_block,
        )
        self.assertIn("if (!isFinalizeRetry) {", questionnaire_block)
        self.assertIn(
            "experimentData.meta.conditionSurveys.push(surveyRecord);",
            questionnaire_block,
        )
        self.assertIn(
            "pendingConditionSurveyRecord = surveyRecord;",
            questionnaire_block,
        )
        self.assertIn(
            '$("condQBody").querySelectorAll(".likert-btn").forEach(button => {',
            questionnaire_block,
        )
        self.assertIn("button.disabled = true;", questionnaire_block)
        self.assertNotIn("Object.assign(surveyRecord", questionnaire_block)
        self.assertEqual(
            questionnaire_block.count(
                "experimentData.meta.conditionSurveys.push(surveyRecord);"
            ),
            1,
        )
        local_save = questionnaire_block.index("saveToLocalStorage();")
        finalize_try = questionnaire_block.index("try {")
        self.assertLess(local_save, finalize_try)
        self.assertIn(
            'if (!isFinalizeRetry) {\n'
            '            await recordInteraction("condition_questionnaire_submitted"',
            questionnaire_block,
        )
        self.assertIn(
            'await recordInteraction("condition_questionnaire_finalize_retried"',
            questionnaire_block,
        )
        self.assertIn(
            "originalSubmittedAt: pendingConditionSurveyRecord.submittedAt,",
            questionnaire_block,
        )
        self.assertIn("saveToLocalStorage();", retry_handler)
        self.assertNotIn("conditionSurveys.splice", retry_handler)
        self.assertNotIn("conditionSurveys.pop", retry_handler)
        self.assertNotIn("pendingConditionSurveyRecord = null", retry_handler)

        submit_block = experiment.split(
            "async function submitCollectedData()", 1
        )[1].split("function loadBand", 1)[0]
        session_request = submit_block.index(
            "const sessionEndResponse = await fetch(config.sessionEndUrl"
        )
        response_check = submit_block.index("if (!sessionEndResponse.ok)")
        end_navigation = submit_block.index('navigateTo("end")')
        self.assertLess(session_request, response_check)
        self.assertLess(response_check, end_navigation)
        self.assertIn(
            "实验会话结束失败\uFF08HTTP ${sessionEndResponse.status}\uFF09",
            submit_block,
        )

    def test_simple_explanation_contract_handles_manual_and_policy_replies(self):
        experiment = self._raw("/ui/experiment.html")
        qwen_block = experiment.split("async function callQwenVL", 1)[1].split(
            "function explanationNeedsRewrite", 1
        )[0]
        rewrite_check = experiment.split("function explanationNeedsRewrite", 1)[1].split(
            "function enforceExplanationContract", 1
        )[0]
        contract_block = experiment.split(
            "function enforceExplanationContract", 1
        )[1].split("function testApiConnection", 1)[0]

        self.assertIn("90至180个中文字符", experiment)
        self.assertIn("这是被试主动粘贴的材料片段或问题", experiment)
        self.assertIn("这是系统根据持续眼动轨迹主动提出的帮助", experiment)
        self.assertIn(
            'const maxTokens = explainLevel === "简单解释" ? 300',
            experiment,
        )
        self.assertIn(
            "callAI(messages, { max_tokens: maxTokens, temperature: 0.35 })",
            experiment,
        )
        self.assertIn(
            "while (explanationNeedsRewrite(reply, explainLevel) "
            "&& rewriteAttempts < 2)",
            qwen_block,
        )
        self.assertEqual(qwen_block.count("await callAI("), 2)
        self.assertIn("使用2至4个完整句子", qwen_block)
        self.assertIn("总长度90至180个中文字符", qwen_block)
        self.assertIn("不要举例或类比", qwen_block)
        self.assertIn(
            "return containsExample || characterCount < 90 || "
            "characterCount > 180 || sentenceCount < 2;",
            rewrite_check,
        )
        self.assertIn(
            "/例如|比如|譬如|举例|打个比方|假设一个/.test(text)",
            rewrite_check,
        )
        self.assertIn("let rewriteAttempts = 0;", qwen_block)
        self.assertIn(
            "while (explanationNeedsRewrite(reply, explainLevel) "
            "&& rewriteAttempts < 2)",
            qwen_block,
        )
        self.assertIn("rewriteAttempts++;", qwen_block)
        self.assertNotIn("AI 回答未满足", qwen_block)
        self.assertIn("characters.length > 180", contract_block)
        self.assertIn("characters.slice(0, 180)", contract_block)
        self.assertNotRegex(
            contract_block,
            r"(?:slice|substring)\(\s*0\s*,\s*120\s*\)",
        )

    def test_actionable_policy_is_latched_until_ui_acknowledges_it(self):
        self._post(
            "/api/ui/context",
            {"phase": "reading", "trial_id": "T01", "seconds_in_trial": 60},
        )
        self._post("/api/condition", {"condition": 2})
        base_gaze = {
            "status": "available",
            "quality": "pass",
            "valid_sample_ratio": 1.0,
            "eye": {
                "aoi_dwell_time": 1.0,
                "fixation_count": 2,
                "mean_fixation_duration": 0.2,
            },
        }
        self._post("/api/gaze", base_gaze)
        difficult = dict(base_gaze)
        difficult["eye"] = {
            "aoi_dwell_time": 2.0,
            "fixation_count": 5,
            "mean_fixation_duration": 0.5,
        }
        emitted = self._post("/api/gaze", difficult)
        self._post("/api/gaze", base_gaze)

        latched = self._get("/api/policy")
        acknowledged = self._post(
            "/api/policy", {"policy_id": emitted["policy_id"]}
        )
        after = self._get("/api/policy")

        self.assertEqual(latched["policy_id"], emitted["policy_id"])
        self.assertNotEqual(latched["explanation_level"], "none")
        self.assertTrue(acknowledged["acknowledged"])
        self.assertNotEqual(after["policy_id"], emitted["policy_id"])

    def test_compatibility_health_attention_and_collection(self):
        health = self._get("/api/health")
        attention = self._get("/api/attention")
        stored = self._post("/api/collect", {"subjectId": "S 001", "trials": []})

        self.assertTrue(health["ok"])
        self.assertFalse(health["eeg_acquisition_enabled"])
        self.assertFalse(health["eeg_connected"])
        self.assertEqual(health["eeg_reason"], "eeg_acquisition_disabled")
        self.assertIsNone(attention["visual_load_index"])
        self.assertTrue(stored["ok"])
        self.assertEqual(len(list(self.documents.glob("S_001_*.json"))), 1)

    def test_serves_latest_tobii_scene_frame_for_multimodal_llm(self):
        frame = self._get("/api/gaze/frame")

        self.assertTrue(frame["ok"])
        self.assertTrue(frame["data_url"].startswith("data:image/jpeg;base64,"))
        self.assertEqual(frame["width"], 640)
        self.assertEqual(frame["timestamp"]["device_seconds"], 12.5)
        self.assertEqual(len(frame["trajectory"]), 2)
        self.assertEqual(frame["trajectory_window_ms"], 3000.0)

    def test_tobii_calibration_uses_explicit_async_control_endpoint(self):
        before = self._get("/api/tobii/calibration")
        started = self._post("/api/tobii/calibration", {})
        after = self._get("/api/tobii/calibration")

        self.assertEqual(before["calibration"]["status"], "idle")
        self.assertEqual(started["calibration"]["status"], "requested")
        self.assertEqual(after["calibration"]["status"], "requested")

    def test_serves_screen_markers_and_accepts_experiment_layout(self):
        marker = self._raw_bytes("/api/screen/marker?id=10")
        layout = self._post(
            "/api/screen/layout",
            {
                "viewport": {"width": 1000, "height": 600},
                "markers": [
                    {
                        "id": marker_id,
                        "x_normalized": 0.05 if marker_id in {10, 13} else 0.95,
                        "y_normalized": 0.05 if marker_id in {10, 11} else 0.95,
                    }
                    for marker_id in MARKER_IDS
                ],
                "elements": [],
            },
        )
        mapping = self._get("/api/screen/mapping")

        self.assertTrue(marker.startswith(b"\x89PNG"))
        self.assertTrue(layout["ok"])
        self.assertEqual(mapping["mapping"]["layout"]["viewport"]["width"], 1000.0)

    def test_question_history_is_persistent_and_subject_scoped(self):
        empty = self._get("/api/questions/used?subject_id=S001")
        reserved = self._post(
            "/api/questions/reserve",
            {"subject_id": "S001", "question_ids": ["1", "17"], "condition": 2},
        )
        used = self._get("/api/questions/used?subject_id=S001")
        other = self._get("/api/questions/used?subject_id=S002")

        self.assertEqual(empty["question_ids"], [])
        self.assertEqual(reserved["question_ids"], ["1", "17"])
        self.assertEqual(used["question_ids"], ["1", "17"])
        self.assertEqual(other["question_ids"], [])

    def test_conversation_content_and_source_are_recorded(self):
        result = self._post(
            "/api/interaction",
            {
                "action": "conversation_message",
                "role": "user",
                "content": "完整问题内容",
                "source": "policy",
                "messageType": "policy_response",
                "policyId": 42,
            },
        )

        interaction = result["interaction"]
        self.assertEqual(interaction["payload"]["content"], "完整问题内容")
        self.assertEqual(interaction["payload"]["source"], "policy")
        records = [
            json.loads(line)
            for line in self.events_path.read_text(encoding="utf-8").splitlines()
        ]
        self.assertTrue(
            any(
                record.get("action") == "conversation_message"
                and record.get("payload", {}).get("policyId") == 42
                for record in records
            )
        )

    def _get(self, route):
        with self.opener.open(self.base + route) as response:
            return json.loads(response.read().decode("utf-8"))

    def _raw(self, route):
        with self.opener.open(self.base + route) as response:
            return response.read().decode("utf-8")

    def _raw_bytes(self, route):
        with self.opener.open(self.base + route) as response:
            return response.read()

    def _post(self, route, payload):
        request = urllib.request.Request(
            self.base + route,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.opener.open(request) as response:
            return json.loads(response.read().decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
