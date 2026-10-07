# Accepted audio cleanup during shutdown

The speech bridge drains undequeued requests after stopping its worker, removing
accepted upload files that would otherwise remain when shutdown precedes dequeue.
Running transactions retain their existing finally cleanup; unrelated saved clips
are preserved. Cleanup is idempotent and filesystem errors are logged.

12 targeted bridge/transport tests pass, including execution of the real drain
method against temporary files. No graph inputs or physical devices were used.
