"""Run the service's load test once with config.CONFIG and print its p95 latency in milliseconds."""
from config import CONFIG
import simsvc

print(f"p95_ms={simsvc.measure(CONFIG):.2f}")
