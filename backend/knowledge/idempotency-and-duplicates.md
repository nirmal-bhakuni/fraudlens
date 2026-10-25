# Duplicate requests and the Idempotency-Key

Every scoring request must include an Idempotency-Key header. If the same key is sent again with the same transaction, the API returns the saved result and does not create a second row. That replay has status 200 and a header Idempotent-Replay set to true. If the same key is sent with a different transaction, the API answers 409, because that is probably a client mistake. A unique constraint in the database enforces this, not just a lookup, so two simultaneous requests cannot both create a row. Keys never expire in this project.
