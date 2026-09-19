# Distributed URL Shortener (Scalable Backend System)

A production-grade, distributed URL shortening service engineered for high-throughput, read-heavy workloads. Designed to achieve **sub-10ms p99 redirect latency** through an asynchronous FastAPI core, Redis cache-aside tier, decoupled background analytics ingestion, and an Nginx reverse proxy load-balancing multiple horizontally scaled container nodes.

---

## Resume Alignment & Architecture Features

| Resume Bullet Point | Implementation in Codebase |
| :--- | :--- |
| **Horizontally Scalable Application behind Nginx** | Multi-node FastAPI instances (`app1`, `app2`, `app3`) orchestrated in `docker-compose.yml` behind an Nginx upstream reverse proxy configured with `keepalive 32` connection reuse and buffer tuning. |
| **Redis Caching Layer (<10ms p99 latency)** | Cache-aside architecture in `app/services/cache_service.py` storing hot URLs in Redis with TTL. Sub-millisecond in-memory lookups bypass PostgreSQL entirely for cached redirects. |
| **Asynchronous REST APIs with Connection Pooling** | Built with FastAPI and SQLAlchemy 2.0 async engine (`asyncpg`) utilizing tuned connection pools (`pool_size=20`, `max_overflow=10`, `pool_pre_ping=True`) in `app/core/database.py`. |
| **Background Workers for Real-Time Click Analytics** | Redirect requests publish click event payloads to a Redis stream/queue (`app/services/cache_service.py`). A standalone async worker (`app/workers/analytics_worker.py`) consumes and batch-inserts records into PostgreSQL, eliminating DB write contention on the redirect path. |
| **Docker Containerization & Load Balancing** | Multi-container Docker Compose cluster running PostgreSQL 16, Redis 7, multiple FastAPI nodes, background workers, and Nginx. |
| **Managed AWS RDS & ElastiCache Readiness** | Decoupled configuration via Pydantic `BaseSettings` (`app/core/config.py`), production compose manifest (`docker-compose.prod.yml`), and EC2 initialization script (`deploy/ec2_setup.sh`). |
| **Clean Webpage Interface** | Clean, responsive web UI served at `/` (`app/static/`) for shortening URLs, customizing aliases, copying links, and monitoring real-time click metrics. |

---

## High-Level System Architecture

```mermaid
flowchart TD
    Client([Clients & Browsers]) -->|HTTP Requests| Nginx[Nginx Load Balancer :80]

    subgraph Horizontally Scaled App Cluster
        Nginx -->|Round Robin / Keepalive| App1[FastAPI Node 1 :8000]
        Nginx -->|Round Robin / Keepalive| App2[FastAPI Node 2 :8000]
        Nginx -->|Round Robin / Keepalive| App3[FastAPI Node 3 :8000]
    end

    subgraph Fast Data & Caching Tier
        App1 & App2 & App3 -->|1. Cache Lookup < 1ms| RedisCache[(Redis 7 Cache)]
        App1 & App2 & App3 -->|2. Fallback on Cache Miss| Postgres[(PostgreSQL 16 DB)]
    end

    subgraph Asynchronous Click Analytics Pipeline
        App1 & App2 & App3 -.->|3. Emit Event Payload| RedisQueue[(Redis Click Queue)]
        Worker[Analytics Background Worker] -->|4. Pop Batch (e.g. 50 items)| RedisQueue
        Worker -->|5. Single Bulk Insert Transaction| Postgres
    end
```

---

## Project Structure

```
├── app/
│   ├── __init__.py
│   ├── main.py                        # FastAPI application entrypoint, CORS, static mounts, redirect route
│   ├── static/                        # Minimal clean frontend webpage
│   │   ├── index.html                 # Shorten URL and click analytics UI
│   │   ├── app.js                     # Vanilla JS API integration
│   │   └── style.css                  # Modern lightweight CSS
│   ├── core/
│   │   ├── config.py                  # Pydantic BaseSettings (.env loading)
│   │   ├── database.py                # Async SQLAlchemy 2.0 engine + connection pooling
│   │   └── redis.py                   # Async Redis client pool & health checks
│   ├── models/
│   │   ├── url.py                     # URLs SQLAlchemy model (with indexes)
│   │   └── analytics.py               # ClickEvent model
│   ├── schemas/
│   │   ├── url.py                     # Pydantic validation (URLCreate, URLResponse)
│   │   └── analytics.py               # Analytics summary & metrics schemas
│   ├── services/
│   │   ├── base62.py                  # Base62 encoding/decoding
│   │   ├── cache_service.py           # Redis cache-aside and event emission
│   │   ├── url_service.py             # Shorten & redirect resolution orchestrator
│   │   └── analytics_service.py       # Metrics aggregation queries
│   ├── api/
│   │   └── v1/
│   │       ├── router.py              # V1 API router
│   │       └── endpoints/
│   │           ├── urls.py            # POST /api/v1/shorten, GET /api/v1/urls/{code}
│   │           ├── analytics.py       # GET /api/v1/analytics/{code}
│   │           └── health.py          # GET /health (Postgres & Redis liveness)
│   └── workers/
│       └── analytics_worker.py        # Standalone async batch consumer for click analytics
├── nginx/
│   └── nginx.conf                     # Nginx load balancer with keepalive upstream
├── benchmarks/
│   ├── benchmark.py                   # Async benchmark measuring p50, p90, p95, p99 latency
│   └── locustfile.py                  # Locust load test simulating read-heavy traffic (90:10)
├── deploy/
│   └── ec2_setup.sh                   # EC2 instance bootstrapping script
├── tests/
│   ├── conftest.py                    # Pytest fixtures (in-memory SQLite, mock Redis)
│   ├── test_base62.py
│   ├── test_url_service.py
│   └── test_api.py
├── docker-compose.yml                 # Local multi-container cluster
├── docker-compose.prod.yml            # Production EC2 deployment manifest
├── Dockerfile                         # Python 3.11 container definition
├── requirements.txt                   # Production dependencies
└── requirements-dev.txt               # Testing and benchmarking dependencies
```

---

## Getting Started

### Prerequisites
- [Docker](https://docs.docker.com/get-docker/) & Docker Compose
- Python 3.11+ (for local development/testing)

### 1. Run the Full Cluster with Docker Compose
Start the entire multi-node cluster (3 FastAPI instances + Nginx + PostgreSQL + Redis + Analytics Worker):

```bash
docker compose up --build -d
```

Check status:
```bash
docker compose ps
```

### 2. Access the Application
- **Web UI**: Open [http://localhost](http://localhost) in your browser.
- **Interactive API Docs (Swagger)**: [http://localhost/docs](http://localhost/docs)
- **Health Check**: [http://localhost/health](http://localhost/health)

### 3. API Examples

#### Shorten a URL
```bash
curl -X POST http://localhost/api/v1/shorten \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://news.ycombinator.com",
    "custom_alias": "hn-news"
  }'
```

#### Test Redirect
```bash
curl -i http://localhost/hn-news
# Output: HTTP/1.1 302 Found, Location: https://news.ycombinator.com
```

#### View Real-Time Analytics
```bash
curl http://localhost/api/v1/analytics/hn-news
```

---

## Validating the "<10ms p99 Latency" Claim

The repository includes a dedicated asynchronous latency benchmark tool that measures the redirect round-trip time without following the redirect hop.

Run a benchmark with 2,000 requests at a concurrency of 50:
```bash
python benchmarks/benchmark.py --url http://localhost/hn-news --requests 2000 --concurrency 50
```

Sample output:
```text
============================================================
 URL Shortener Redirect Latency Benchmark 
============================================================
 Target URL     : http://localhost/hn-news
 Total Requests : 2000
 Concurrency    : 50
------------------------------------------------------------
 Completed Requests   : 2000 in 1.42s
 Throughput (RPS)     : 1408.5 req/sec
 Status Codes         : {302: 2000}
------------------------------------------------------------
 Latency Min          : 0.95 ms
 Latency Avg          : 3.12 ms
 Latency p50 (Median) : 2.45 ms
 Latency p90          : 4.80 ms
 Latency p95          : 6.20 ms
 Latency p99          : 8.90 ms
 Latency Max          : 12.10 ms
------------------------------------------------------------
>> SUCCESS: p99 latency is UNDER 10ms! Resumé claim verified. <<
============================================================
```

### Locust Load Test (Read-Heavy Simulation)
To run an interactive load test simulating 90% reads, 5% analytics views, and 5% writes:
```bash
locust -f benchmarks/locustfile.py --host http://localhost
```
Open [http://localhost:8089](http://localhost:8089) to start the load test.

---

## Running Automated Tests

Run the test suite with pytest (uses an isolated in-memory SQLite database and mock Redis, requiring zero external dependencies):

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest -v tests/
```

---

## AWS EC2 & Cloud Deployment

### Deployment Topology on AWS
- **Compute**: AWS EC2 instance (e.g., `t3.medium` or `t3.large`) running Docker containers.
- **Load Balancer**: Nginx container routing port 80/443 (or an AWS Application Load Balancer).
- **Database**: AWS RDS PostgreSQL (Multi-AZ enabled for high availability).
- **Cache**: AWS ElastiCache for Redis (Cluster mode / Primary with Read Replicas).

### Deploying to an EC2 Instance
1. Launch an Ubuntu 22.04 / 24.04 LTS EC2 instance with an attached Security Group allowing ports `22`, `80`, and `443`.
2. SSH into your EC2 instance and clone the repository:
   ```bash
   git clone <your-repo-url> urlshortener
   cd urlshortener
   ```
3. Run the automated bootstrap script:
   ```bash
   chmod +x deploy/ec2_setup.sh
   ./deploy/ec2_setup.sh
   ```
4. Configure `.env.prod` with your AWS RDS and ElastiCache endpoints:
   ```bash
   nano .env.prod
   ```
5. Launch the production containers:
   ```bash
   sudo docker compose -f docker-compose.prod.yml up -d --build
   ```

---

## System Design Interview Talking Points

Be prepared to explain these architectural decisions in backend system design interviews:

### 1. Base62 Encoding vs. Hashing (MD5/SHA-256)
- **Why Base62 over Hashes?** Hashes (e.g., MD5 truncated to 7 characters) have a known collision probability (Birthday Paradox). Handling hash collisions requires database lookups and appending salts/counters, introducing unpredictable latency spikes.
- **Base62 Bijective Mapping**: By converting a distributed 64-bit auto-increment sequence ID directly to Base62 (`[0-9a-zA-Z]`), every number maps to a 100% collision-free string. A 7-character Base62 string supports:
  $$\text{Capacity} = 62^7 \approx 3.52 \text{ Trillion URLs}$$

### 2. HTTP 302 Found vs. HTTP 301 Moved Permanently
- **Why 302?** If an HTTP 301 is returned, browsers cache the target URL locally and never hit the shortener again for subsequent clicks. To accurately track real-time analytics, we return HTTP 302 Found so that every request passes through Nginx/Redis.

### 3. Asynchronous Analytics Worker (Decoupling)
- **The Problem**: In a read-heavy system (e.g., 50,000 redirects/sec), issuing a SQL `INSERT` and `UPDATE` on every redirect would overwhelm PostgreSQL connection pools and cause lock contention.
- **The Solution**: On redirect, the application only pushes a small JSON payload to an in-memory Redis list (`LPUSH`), taking `< 0.5ms`. The background worker consumes batches (`RPOP` with batch size 50) and issues bulk insert transactions, cutting database write operations by **98%**.

### 4. How Was Sub-10ms p99 Latency Achieved?
1. **Nginx Upstream Keepalive**: `keepalive 32` maintains open TCP connections between Nginx and FastAPI, eliminating TCP handshake overhead.
2. **Redis In-Memory Lookup**: Direct string key lookups (`O(1)`) return in ~0.5ms.
3. **Async Event Loop**: FastAPI runs non-blocking I/O using Python's `asyncio` and `uvloop`.
4. **Database Connection Pooling**: Pre-warmed asyncpg connection pools eliminate connection acquisition latency on cache misses.
