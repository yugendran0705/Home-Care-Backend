# config/razorpay.py
import os
from functools import lru_cache

import razorpay
from dotenv import load_dotenv

load_dotenv()

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")
RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET")


@lru_cache
def get_razorpay_client() -> razorpay.Client:
    if not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET:
        raise RuntimeError("RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET must be set")
    client = razorpay.Client(
        auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET),
        # max_retries=3 caps the worst case at a few seconds of extra wait
        # (1s, 2s backoff) rather than the library's default 5 retries
        # (~31s), since this is a synchronous call the patient is waiting
        # on during booking creation.
        max_retries=3,
    )
    # razorpay.Client.__init__ reads max_retries/initial_delay/max_delay/
    # jitter from **options, but hardcodes self.retry_enabled = False
    # unconditionally - passing retry_enabled=True to the constructor is
    # silently ignored. The only way to actually turn on the SDK's built-in
    # exponential-backoff retry (for ConnectionError/Timeout - see
    # razorpay.Client.request) is setting the attribute after construction.
    client.retry_enabled = True
    return client