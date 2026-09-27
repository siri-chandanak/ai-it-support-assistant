from locust import task

INCIDENT_PROPOSAL_QUESTIONS = [
    (
        "Create a high severity incident for "
        "vpn-gateway because users are reporting "
        "VPN login failures."
    ),
    ("Create an incident for vpn-gateway because authentication is degraded."),
]


def register_approval_tasks(user_class) -> None:
    @task(1)
    def incident_proposal(self) -> None:
        question = INCIDENT_PROPOSAL_QUESTIONS[
            self.incident_proposal_index % len(INCIDENT_PROPOSAL_QUESTIONS)
        ]

        self.incident_proposal_index += 1

        with self.client.post(
            "/api/v1/agent/ask",
            json={
                "question": question,
            },
            headers=self.auth_headers,
            name=("/api/v1/agent/ask [incident-proposal]"),
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"Proposal failed: {response.status_code} {response.text[:200]}")
                return

            try:
                body = response.json()
            except ValueError:
                response.failure("Proposal response was not valid JSON.")
                return

            if not body.get("approval_required"):
                response.failure("Incident request did not create an approval-required proposal.")
                return

            if not body.get("approval_id"):
                response.failure("Proposal did not return approval_id.")
                return

            response.success()

    user_class.incident_proposal_index = 0
    user_class.incident_proposal = incident_proposal
