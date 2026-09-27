from locust import task

AGENT_QUESTIONS = [
    "What should I do if my VPN stopped working after changing my password?",
    "Is vpn-gateway healthy right now?",
    "What does the VPN policy say?",
]


def register_agent_tasks(user_class) -> None:
    @task(2)
    def agent_question(self) -> None:
        question = AGENT_QUESTIONS[self.agent_question_index % len(AGENT_QUESTIONS)]

        self.agent_question_index += 1

        with self.client.post(
            "/api/v1/agent/ask",
            json={
                "question": question,
            },
            headers=self.auth_headers,
            name="/api/v1/agent/ask [read]",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
                return

            response.failure(f"Agent request failed: {response.status_code} {response.text[:200]}")

    user_class.agent_question_index = 0
    user_class.agent_question = agent_question
