"""job_digest — shareable, profile-driven daily job digest engine.

Isolated fork of the operator's internal job pipeline: nothing here imports from
it and nothing in it imports from here. Changing this package never
affects the operator's own cron.
"""
__version__ = "0.1.0"
