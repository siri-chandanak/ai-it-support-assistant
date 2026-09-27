from itertools import count

from locust import task

from performance.data.rag_questions import RETRIEVAL_QUERIES

_retrieval_counter = count()


def register_retrieval_tasks(user_class) -> None:

    @task(2)
    def retrieval_warm(self) -> None:
        request_number = next(_retrieval_counter)

        query = RETRIEVAL_QUERIES[request_number % len(RETRIEVAL_QUERIES)]

        with self.client.post(
            "/api/v1/retrieval/search",
            json={
                "query": query,
                "top_k": 3,
            },
            headers=self.auth_headers,
            name="/api/v1/retrieval/search [warm]",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"Warm retrieval request failed: status={response.status_code}")

    @task(2)
    def retrieval_search(self) -> None:
        request_number = next(_retrieval_counter)

        base_query = RETRIEVAL_QUERIES[request_number % len(RETRIEVAL_QUERIES)]

        query = f"{base_query} performance variation {request_number}"

        with self.client.post(
            "/api/v1/retrieval/search",
            json={
                "query": query,
                "top_k": 3,
            },
            headers=self.auth_headers,
            name="/api/v1/retrieval/search",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"Retrieval request failed: status={response.status_code}")

    user_class.retrieval_search = retrieval_search
