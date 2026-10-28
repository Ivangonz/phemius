# Why we moved to a single database

For two years the product ran on three databases: one for users, one for
billing and one for analytics. Each was chosen for a good reason at the time.
Together they made every change slow.

A simple feature, such as showing a customer's invoices next to their usage,
needed three queries, two caches and a nightly job to keep them in step. When
the job failed, support saw numbers that did not match, and engineers spent
mornings reconciling them by hand.

We consolidated on one database last spring. The migration took six weeks, most
of it spent rewriting reports. Since then the nightly job is gone, the support
tickets about mismatched numbers have stopped, and new features ship in days
instead of weeks.

The lesson is not that one database is always right. It is that every extra
system has a cost that grows quietly, and that cost deserves a line in the
original decision.
