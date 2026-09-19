import argparse
import asyncio
import statistics
import time
from typing import List
import httpx


async def worker(
    name: int,
    url: str,
    queue: asyncio.Queue,
    latencies: List[float],
    status_counts: dict,
    client: httpx.AsyncClient,
):
    while not queue.empty():
        try:
            _ = queue.get_nowait()
        except asyncio.QueueEmpty:
            break

        start = time.perf_counter()
        try:
            # We set follow_redirects=False because we are measuring the redirect lookup latency!
            resp = await client.get(url, follow_redirects=False)
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            latencies.append(elapsed_ms)
            status_counts[resp.status_code] = status_counts.get(resp.status_code, 0) + 1
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            latencies.append(elapsed_ms)
            status_counts["ERROR"] = status_counts.get("ERROR", 0) + 1
        finally:
            queue.task_done()


async def run_benchmark(target_url: str, total_requests: int, concurrency: int):
    print("=" * 60)
    print(f" URL Shortener Redirect Latency Benchmark ")
    print("=" * 60)
    print(f" Target URL     : {target_url}")
    print(f" Total Requests : {total_requests}")
    print(f" Concurrency    : {concurrency}")
    print("-" * 60)

    queue = asyncio.Queue()
    for _ in range(total_requests):
        queue.put_nowait(1)

    latencies: List[float] = []
    status_counts: dict = {}

    # High-throughput client with connection pooling
    limits = httpx.Limits(max_keepalive_connections=concurrency * 2, max_connections=concurrency * 2)
    async with httpx.AsyncClient(limits=limits, timeout=10.0) as client:
        # Warmup connection
        try:
            await client.get(target_url, follow_redirects=False)
        except Exception:
            pass

        t0 = time.perf_counter()
        tasks = [
            asyncio.create_task(worker(i, target_url, queue, latencies, status_counts, client))
            for i in range(concurrency)
        ]
        await asyncio.gather(*tasks)
        total_time = time.perf_counter() - t0

    if not latencies:
        print("No requests completed.")
        return

    latencies.sort()
    count = len(latencies)
    rps = count / total_time

    p50 = latencies[int(count * 0.50)]
    p90 = latencies[int(count * 0.90)]
    p95 = latencies[int(count * 0.95)]
    p99 = latencies[int(count * 0.99)]
    min_lat = latencies[0]
    max_lat = latencies[-1]
    avg_lat = statistics.mean(latencies)

    print("\nBenchmark Results:")
    print("-" * 60)
    print(f" Completed Requests   : {count} in {total_time:.2f}s")
    print(f" Throughput (RPS)     : {rps:.1f} req/sec")
    print(f" Status Codes         : {dict(status_counts)}")
    print("-" * 60)
    print(f" Latency Min          : {min_lat:.2f} ms")
    print(f" Latency Avg          : {avg_lat:.2f} ms")
    print(f" Latency p50 (Median) : {p50:.2f} ms")
    print(f" Latency p90          : {p90:.2f} ms")
    print(f" Latency p95          : {p95:.2f} ms")
    print(f" Latency p99          : {p99:.2f} ms")
    print(f" Latency Max          : {max_lat:.2f} ms")
    print("-" * 60)

    if p99 < 10.0:
        print(">> SUCCESS: p99 latency is UNDER 10ms! Resumé claim verified. <<")
    else:
        print(f">> INFO: p99 latency measured at {p99:.2f}ms. <<")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Latency benchmark for URL redirect path")
    parser.add_argument("--url", type=str, required=True, help="Short URL redirect endpoint (e.g. http://localhost/test)")
    parser.add_argument("--requests", type=int, default=2000, help="Total number of requests (default: 2000)")
    parser.add_argument("--concurrency", type=int, default=50, help="Concurrent workers (default: 50)")

    args = parser.parse_args()
    asyncio.run(run_benchmark(args.url, args.requests, args.concurrency))
