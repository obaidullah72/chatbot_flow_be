import json

from django.test import TestCase


class AnswerFlowTests(TestCase):
    def test_good_answer_short_circuits_followups(self):
        payload = {
            "topic": "algorithms",
            "user": "alice",
            "question": "Explain recursion in detail",
            "main_answer": " ".join(["Recursion"] * 80) + " enables divide-and-conquer problem solving.",
            "language": "en",
        }

        response = self.client.post(
            "/api/answer/",
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data["needs_followups"])
        self.assertGreaterEqual(data["final_score"], 5)
        self.assertEqual(data["follow_ups"], [])

    def test_bad_answer_requires_followups_and_finalization(self):
        initial_payload = {
            "topic": "algorithms",
            "user": "bob",
            "question": "Explain recursion in detail",
            "main_answer": "It is a function calling itself.",
        }

        answer_response = self.client.post(
            "/api/answer/",
            data=json.dumps(initial_payload),
            content_type="application/json",
        )
        self.assertEqual(answer_response.status_code, 200)
        answer_data = answer_response.json()
        self.assertTrue(answer_data["needs_followups"])
        self.assertEqual(len(answer_data["follow_ups"]), 1)

        # Simulate iterative follow-up flow: answer first follow-up, then continue
        first_followup = answer_data["follow_ups"][0]
        continue_payload = {
            **initial_payload,
            "followup_pairs": [
                {"question": first_followup, "answer": "Detailed answer for: " + first_followup}
            ],
        }

        continue_response = self.client.post(
            "/api/answer/continue/",
            data=json.dumps(continue_payload),
            content_type="application/json",
        )

        self.assertEqual(continue_response.status_code, 200)
        continue_data = continue_response.json()
        self.assertIn("needs_followups", continue_data)

    def test_generate_questions_default_count(self):
        payload = {"topic": "Dynamic Programming"}

        response = self.client.post(
            "/api/questions/",
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["topic"], "Dynamic Programming")
        self.assertEqual(data["count"], 10)
        self.assertEqual(len(data["questions"]), 10)

    def test_generate_questions_custom_smaller_count(self):
        payload = {"topic": "Graphs", "count": 5}

        response = self.client.post(
            "/api/questions/",
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 5)
        self.assertEqual(len(data["questions"]), 5)

