"""Settings for the service. Every value is an integer in the range shown.

The host has 2048 MB for the service: cache_mb + 48 * workers must stay at or under 2048.
"""
CONFIG = {
    "workers": 8,            # 1..64
    "batch_size": 16,        # 1..512
    "cache_mb": 128,         # 0..4096
    "compression": 6,        # 0..9
    "prefetch": 0,           # 0..16
    "pool_timeout_ms": 200,  # 1..1000
}
