import json
import tempfile
import unittest
from pathlib import Path

from recon_pipeline.storage import ExperimentRunManager


class ExperimentRunManagerTests(unittest.TestCase):
    def test_single_condition_directory_and_question_history(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "runs"
            manager = ExperimentRunManager(root)

            directory = manager.start_session("S 001", 2)
            self.assertIsNotNone(directory)
            assert directory is not None
            self.assertRegex(directory.name, r"^S 001_condition_2_\d{8}_\d{6}_\d{6}$")

            manager.append_jsonl(
                "interactions.jsonl",
                {
                    "condition": 2,
                    "action": "conversation_message",
                    "payload": {
                        "role": "user",
                        "content": "manual question",
                        "source": "manual",
                    },
                },
            )
            destination = manager.save_experiment(
                {
                    "subjectId": "S 001",
                    "experimentData": {
                        "trials": [
                            {"condition": 2, "slideId": 1},
                            {"condition": 3, "slideId": 2},
                        ]
                    },
                }
            )
            manager.reserve_questions("S 001", ["1", "17"], 2)

            self.assertEqual(destination, directory / "experiment.json")
            experiment = json.loads((directory / "experiment.json").read_text(encoding="utf-8"))
            self.assertEqual(
                experiment["experimentData"]["trials"],
                [{"condition": 2, "slideId": 1}],
            )
            interaction = json.loads(
                (directory / "interactions.jsonl").read_text(encoding="utf-8").strip()
            )
            self.assertEqual(interaction["payload"]["source"], "manual")
            self.assertEqual(manager.used_question_ids("s 001"), ["1", "17"])

            manager.end_session()
            self.assertFalse(manager.active)

    def test_resume_reuses_existing_condition_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "runs"
            manager = ExperimentRunManager(root)

            directory = manager.start_session("S001", 2)
            assert directory is not None
            stamp = manager.current_stamp
            assert stamp is not None
            manager.append_jsonl("interactions.jsonl", {"action": "before_interrupt"})
            manager.end_session()

            resumed = manager.start_session("S001", 2, resume_stamp=stamp)
            self.assertEqual(resumed, directory)
            self.assertEqual(manager.current_stamp, stamp)
            self.assertIn(
                "before_interrupt",
                (directory / "interactions.jsonl").read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
