"""The Sentry integrations ``settings.py`` passes to ``sentry_sdk.init`` (todo 623).

A function, not a literal in the gated ``init()`` block, so a test can build
the same list without a DSN: the init only runs when ``SENTRY_DSN`` is set and
``DEBUG`` is off, which no test or CI run has.

``CeleryIntegration(monitor_beat_tasks=True)`` is the beat alert (owner
decision 2026-10-12: operational alerts go to Sentry). Sentry auto-enables the
Celery integration whenever Celery is installed, but with crons off. With them
on, the SDK patches ``celery.beat.Scheduler.apply_entry``, which the embedded
beat (``worker -B``, ``bin/start.sh``) runs in-process, so every
``CELERY_BEAT_SCHEDULE`` entry becomes a Sentry Cron Monitor named after its
schedule key:

- beat sends an ``in_progress`` check-in when it enqueues the task;
- the worker sends ``ok`` when the task succeeds, ``error`` when it fails or
  retries;
- Sentry raises a **missed** check-in when beat did not enqueue on schedule
  (worker or beat dead), and a **timeout** when the task did not finish within
  the monitor's max runtime (the queue is backed up, or the worker is wedged).

Only messages beat itself sent carry the monitor headers, so a weekly
recovery run (``schedule_weekly_recovery``) or a manual ``.delay()`` does not
check in. Every entry must be a ``crontab`` or a ``schedule`` of a minute or
more; ``apps/core/tests/test_notification_ops.py`` pins that.
"""


def sentry_integrations() -> list:
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.django import DjangoIntegration

    return [
        DjangoIntegration(),
        CeleryIntegration(monitor_beat_tasks=True),
    ]


# The operational alerts (todo 623) are ERROR logs. With ``attach_stacktrace``
# and local variables on, the logging integration would ship the frame
# locals of whoever logged them: a dispatch's ``payload``, a task's
# ``token`` kwarg, a bound broker exception whose text holds the broker URL.
# The alerts promise counts and class names only, so their events lose frame
# variables here. Every other event keeps them: this is narrow on purpose.
ALERT_LOGGERS = ("apps.core.notification_ops", "apps.core.delivery")
ALERT_MARKERS = ("[PUSH]", "[DELIVERY]", "[OUTCOME]")
BROKER_MARKER = " (broker: %s)"


def is_alert_event(event: dict) -> bool:
    logger_name = str(event.get("logger") or "")
    template = str((event.get("logentry") or {}).get("message") or "")
    return (
        logger_name.startswith(ALERT_LOGGERS)
        or template.startswith(ALERT_MARKERS)
        or template.endswith(BROKER_MARKER)
    )


def _strip_frame_vars(container) -> None:
    for entry in (container or {}).get("values") or []:
        for frame in (entry.get("stacktrace") or {}).get("frames") or []:
            frame.pop("vars", None)


def before_send(event, hint):
    """Drop frame variables from the operational-alert events only."""
    if is_alert_event(event):
        _strip_frame_vars(event.get("exception"))
        _strip_frame_vars(event.get("threads"))
    return event
