import re
import unittest
from html import unescape
from pathlib import Path

QUESTION_BANK = (
    Path(__file__).resolve().parents[1] / "src" / "recon_pipeline" / "web" / "question_bank"
)


class QuestionBankTests(unittest.TestCase):
    def test_each_difficulty_has_16_questions_with_matching_labels(self):
        specifications = {
            "easy": ("低", range(1, 17)),
            "medium": ("中", range(17, 33)),
            "hard": ("高", range(33, 49)),
        }
        all_ids = []
        for folder, (difficulty, expected_ids) in specifications.items():
            files = sorted((QUESTION_BANK / folder).glob("question_*.js"))
            self.assertEqual(len(files), 16, folder)
            for source, expected_id in zip(files, expected_ids):
                content = source.read_text(encoding="utf-8")
                ids = [int(value) for value in re.findall(r"\{\s*id:(\d+),", content)]
                labels = re.findall(r'difficulty:"([^"]+)"', content)

                self.assertEqual(source.name, f"question_{expected_id:02d}.js")
                self.assertEqual(ids, [expected_id], source.name)
                self.assertEqual(labels, [difficulty], source.name)
                self.assertEqual(content.count(f"window.questionBank.{folder}.push("), 1)
                all_ids.extend(ids)

        self.assertEqual(sorted(all_ids), list(range(1, 49)))
        self.assertEqual(len(set(all_ids)), 48)

    def test_experiment_loads_all_groups_before_index(self):
        experiment = (QUESTION_BANK.parent / "experiment.html").read_text(encoding="utf-8")
        references = []
        for question_id in range(1, 49):
            folder = "easy" if question_id <= 16 else "medium" if question_id <= 32 else "hard"
            references.append(f"question_bank/{folder}/question_{question_id:02d}.js")
        references.append("question_bank/index.js")
        positions = [experiment.index(reference) for reference in references]
        self.assertEqual(positions, sorted(positions))

    def test_hard_materials_have_two_whole_material_comprehension_questions(self):
        for source in sorted((QUESTION_BANK / "hard").glob("question_*.js")):
            content = source.read_text(encoding="utf-8")
            material_match = re.search(r"content:`([\s\S]*?)`,\s*quiz:", content)
            questions = re.findall(r'question:"([^"]+)"', content)
            option_groups = re.findall(r'options:\[([^\]]+)\]', content)
            answer_indexes = [
                int(value) for value in re.findall(r"answerIndex:(\d+)", content)
            ]

            self.assertIsNotNone(material_match, source.name)
            material_text = unescape(re.sub(r"<[^>]+>", "", material_match.group(1)))
            self.assertGreaterEqual(len(material_text), 750, source.name)
            self.assertLessEqual(len(material_text), 950, source.name)
            self.assertEqual(content.count("`"), 2, source.name)
            self.assertEqual(content.count("</p>`,"), 1, source.name)
            self.assertEqual(len(questions), 2, source.name)
            self.assertTrue(questions[0].startswith("综合"), source.name)
            for question in questions:
                self.assertNotRegex(
                    question,
                    r"\d|计算|多少|最接近|数值|求出",
                    source.name,
                )
            self.assertEqual(len(option_groups), 2, source.name)
            self.assertEqual(len(answer_indexes), 2, source.name)
            for options, answer_index in zip(option_groups, answer_indexes):
                self.assertEqual(len(re.findall(r'"[^"]*"', options)), 4, source.name)
                self.assertIn(answer_index, range(4), source.name)

    def test_experiment_checkpoint_can_resume_after_interruption(self):
        experiment = (QUESTION_BANK.parent / "experiment.html").read_text(encoding="utf-8")
        for needle in (
            "const CHECKPOINT_VERSION = 2;",
            "setInterval(() => saveToLocalStorage(), 2000);",
            'window.addEventListener("pagehide", checkpointBeforeUnload);',
            "resumeSavedExperiment",
            "restartInterrupted",
            "runStamp",
        ):
            self.assertIn(needle, experiment)

    def test_policy_prompt_has_reading_start_guard_and_response_release(self):
        experiment = (QUESTION_BANK.parent / "experiment.html").read_text(encoding="utf-8")
        for needle in (
            "policyPromptedLevels",
            "policyAnsweredLevels",
            "policyAreaDecisions",
            "areaId",
            "policyAreaSuppressionReason",
            "suppressed_area_history",
            "rememberPolicyAreaResponse",
            "policyMinimumTrialSeconds: 20",
            "releasePolicyOffer",
            "syncReadingProgress",
            "seconds_in_trial",
        ):
            self.assertIn(needle, experiment)

    def test_each_session_uses_two_unused_questions_from_each_difficulty(self):
        experiment = (QUESTION_BANK.parent / "experiment.html").read_text(encoding="utf-8")

        self.assertIn("const TRIALS_PER_CONDITION = 6;", experiment)
        self.assertIn("const PER_DIFFICULTY_PER_CONDITION = 2;", experiment)
        self.assertIn("async function buildSessionTrialOrder(subjectId)", experiment)
        self.assertIn("function validateSessionTrialOrder(order)", experiment)
        self.assertIn("validateSessionTrialOrder(order);", experiment)
        self.assertIn("/api/questions/used?subject_id=", experiment)
        self.assertIn("/api/questions/reserve", experiment)
        self.assertIn("trialOrder = await buildSessionTrialOrder(subjectId);", experiment)
        self.assertNotIn("generateConditionOrder", experiment)
        self.assertNotIn("trialOrder = slides.map((_, i) => i)", experiment)

    def test_experiment_timer_normalizes_legacy_timestamps(self):
        experiment = (QUESTION_BANK.parent / "experiment.html").read_text(encoding="utf-8")
        for needle in (
            "function normalizeEpochMs(value)",
            "function storedExperimentStartMs(data = experimentData)",
            "function formatElapsedSeconds(value)",
            "experimentStartTime = normalizeEpochMs(startAt) ?? "
            "storedExperimentStartMs() ?? Date.now();",
            "startExperimentTimer(experimentData.meta.experimentStartTime);",
            "const recoveredStartMs = storedExperimentStartMs(experimentData);",
            "experimentData.meta.totalDurationSec = Math.max(0, Math.floor("
            "(endMs - startMs) / 1000));",
        ):
            self.assertIn(needle, experiment)
        self.assertNotIn(
            "Number.isFinite(Number(startAt)) ? Number(startAt) : Date.now()",
            experiment,
        )

    def test_conversations_are_logged_with_trigger_source(self):
        experiment = (QUESTION_BANK.parent / "experiment.html").read_text(encoding="utf-8")

        self.assertIn('recordInteraction("conversation_message"', experiment)
        self.assertIn('source: options.source || "manual"', experiment)
        self.assertIn('messageType: "policy_prompt"', experiment)
        self.assertIn('messageType: "policy_response"', experiment)
        self.assertIn('messageType: "answer"', experiment)

    def test_ai_reply_keeps_a_chronological_message_stream(self):
        experiment = (QUESTION_BANK.parent / "experiment.html").read_text(encoding="utf-8")

        self.assertIn(
            'addChatMsg("ai", response, options.replyAfter || userRow)',
            experiment,
        )
        self.assertIn(
            'addChatMsg("ai", errMsg, options.replyAfter || userRow)',
            experiment,
        )
        self.assertIn("function addChatMsg(type, content, afterRow = null)", experiment)
        self.assertIn("chronological top-to-bottom stream", experiment)
        self.assertIn("messagesEl.insertBefore(row, typing);", experiment)
        self.assertIn("function insertChatRowChronologically(row)", experiment)
        self.assertIn("insertChatRowChronologically(card);", experiment)
        self.assertIn("insertChatRowChronologically(responseRow);", experiment)
        self.assertIn("messages.appendChild(typing);", experiment)

    def test_between_trial_rest_is_an_opaque_white_fixation_screen(self):
        experiment = (QUESTION_BANK.parent / "experiment.html").read_text(encoding="utf-8")

        self.assertIn("#restModal {", experiment)
        self.assertIn("background: #ffffff;", experiment)
        self.assertIn('<div id="restModal" class="modal-overlay">', experiment)
        self.assertIn('<div class="fixation-cross" aria-hidden="true"></div>', experiment)

    def test_llm_receives_full_material_and_structured_gaze_context(self):
        experiment = (QUESTION_BANK.parent / "experiment.html").read_text(encoding="utf-8")

        self.assertIn('const fullMaterial = $("readingContent")', experiment)
        self.assertIn("完整材料正文" + "\uff1a", experiment)
        self.assertIn("材料已经明确提供的信息", experiment)
        self.assertIn("scene_trajectory:", experiment)
        self.assertIn("screen_mapping: {", experiment)
        self.assertIn('recordInteraction("llm_gaze_context_attached"', experiment)
        self.assertIn("当前识别到的实验主屏幕边界", experiment)
        self.assertIn("sustained_dom_target", experiment)
        self.assertIn("parsePolicyFocus", experiment)
        self.assertIn('recordInteraction("policy_focus_inferred"', experiment)

    def test_policy_acceptance_reuses_the_trigger_frame_without_persisting_it(self):
        experiment = (QUESTION_BANK.parent / "experiment.html").read_text(encoding="utf-8")
        trigger_block = experiment.split(
            "async function triggerPolicyExplanation", 1
        )[1].split("async function inferPolicyFocus", 1)[0]
        inference_block = experiment.split("async function inferPolicyFocus", 1)[1].split(
            "function gazeOverlayGuide", 1
        )[0]
        acceptance_block = experiment.split(
            "async function acceptPolicySuggestion", 1
        )[1].split("function rejectPolicySuggestion", 1)[0]
        persistence_block = experiment.split("function recordPolicyResponse", 1)[1].split(
            "function restoreManualExplainLevel", 1
        )[0]
        policy_send_block = experiment.split(
            "async function sendPolicyTriggeredMessage", 1
        )[1].split("async function manualPolicyTrigger", 1)[0]
        llm_block = experiment.split("async function callQwenVL", 1)[1].split(
            "function explanationNeedsRewrite", 1
        )[0]

        self.assertIn("frameSnapshot: {", inference_block)
        self.assertIn("data_url: frame.data_url", inference_block)
        self.assertIn(
            "const { frameSnapshot = null, ...inferredFields } = inferenceResult || {};",
            trigger_block,
        )
        self.assertIn("const inferred = inferenceResult ? inferredFields : null;", trigger_block)
        self.assertIn("sceneFrame: frameSnapshot,", trigger_block)

        self.assertIn("const suggestion = pendingPolicySuggestion;", acceptance_block)
        self.assertIn("await sendPolicyTriggeredMessage(suggestion);", acceptance_block)
        self.assertIn("sceneFrame: suggestion.sceneFrame,", policy_send_block)

        self.assertIn("let frame = options.sceneFrame;", llm_block)
        cached_frame = llm_block.index("let frame = options.sceneFrame;")
        fallback_guard = llm_block.index("if (!frame) {")
        fallback_fetch = llm_block.index("await fetch(config.gazeFrameUrl")
        self.assertLess(cached_frame, fallback_guard)
        self.assertLess(fallback_guard, fallback_fetch)
        self.assertIn(
            'frame_source: options.sceneFrame ? "policy_trigger" : "latest_available"',
            llm_block,
        )

        self.assertIn("trial.policySuggestions.push({", persistence_block)
        self.assertIn("focusInference: suggestion.focusInference", persistence_block)
        self.assertNotIn("sceneFrame", persistence_block)
        self.assertNotIn("frameSnapshot", persistence_block)
        self.assertNotIn("data_url", persistence_block)


if __name__ == "__main__":
    unittest.main()
