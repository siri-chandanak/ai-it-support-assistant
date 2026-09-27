from itertools import count

from locust import task

from performance.data.rag_questions import (
    COLD_RAG_BASE_QUESTIONS,
    WARM_RAG_QUESTIONS,
)

_warm_counter = count()
_cold_counter = count()


def register_rag_tasks(user_class) -> None:
    @task(3)
    def rag_warm(self) -> None:
        request_number = next(_warm_counter)

        question = WARM_RAG_QUESTIONS[request_number % len(WARM_RAG_QUESTIONS)]

        with self.client.post(
            "/api/v1/rag/answer",
            json={
                "question": question,
            },
            headers=self.auth_headers,
            name="/api/v1/rag/answer [warm]",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"RAG warm request failed: status={response.status_code}")

    @task(1)
    def rag_cold(self) -> None:
        request_number = next(_cold_counter)

        base_question = COLD_RAG_BASE_QUESTIONS[request_number % len(COLD_RAG_BASE_QUESTIONS)]

        question = f"{base_question} Performance variation {request_number}."

        with self.client.post(
            "/api/v1/rag/answer",
            json={
                "question": question,
            },
            headers=self.auth_headers,
            name="/api/v1/rag/answer [cold]",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"RAG cold request failed: status={response.status_code}")

    user_class.rag_warm = rag_warm
    user_class.rag_cold = rag_cold
