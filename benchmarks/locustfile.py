import random
from locust import HttpUser, between, task


class ReadHeavyURLShortenerUser(HttpUser):
    # Simulates realistic human or machine think-time between 0.01 and 0.05 seconds
    wait_time = between(0.01, 0.05)

    created_codes = ["sample-link", "github-repo", "demo-doc"]

    def on_start(self):
        """Create an initial short link for this simulated user."""
        res = self.client.post(
            "/api/v1/shorten",
            json={"url": f"https://example.com/target/{random.randint(1, 10000)}"},
            name="/api/v1/shorten [Setup]",
        )
        if res.status_code == 201:
            data = res.json()
            self.created_codes.append(data["short_code"])

    # 90% of requests are reads/redirects (read-heavy pattern)
    @task(9)
    def redirect_url(self):
        code = random.choice(self.created_codes)
        # Avoid following redirect to measure redirect hop latency
        self.client.get(f"/{code}", allow_redirects=False, name="/{short_code} [Redirect]")

    # 5% of requests check analytics
    @task(1)
    def view_analytics(self):
        code = random.choice(self.created_codes)
        self.client.get(f"/api/v1/analytics/{code}", name="/api/v1/analytics/{short_code}")

    # 5% of requests create new short URLs
    @task(1)
    def shorten_new_url(self):
        res = self.client.post(
            "/api/v1/shorten",
            json={"url": f"https://news.ycombinator.com/item?id={random.randint(1000, 999999)}"},
            name="/api/v1/shorten [Create]",
        )
        if res.status_code == 201:
            data = res.json()
            self.created_codes.append(data["short_code"])
