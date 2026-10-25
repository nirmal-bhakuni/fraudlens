# API keys and rate limits

Every request to the transactions endpoints needs an API key in the X-API-Key header, and a client can only see its own transactions. Each key may make 120 requests per minute by default. Above that the API answers 429 with a Retry-After header. The limiter lives in memory, so it resets when the server restarts and is not shared between several server copies. Wrong keys are not rate limited. Keys come from the API_KEYS setting and cannot be rotated or revoked while the server runs.
