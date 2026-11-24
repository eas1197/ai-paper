"""D19: original academic gates must not accept self-reported review identity."""
from pathlib import Path


def require_original_review(work, *, intake=None):
    """Stop legacy state mutation until a real independent authorization adapter exists.

    An intake is supplied by the dispatcher, never by the legacy report. D18 can
    preserve the actual blocked candidate. No fixture or boolean can authorize a gate.
    """
    if intake is None:
        raise ValueError('unable_to_review: independent execution authorization is required; legacy report fields are not credentials')
    import task_packet
    from review_wait import receive_review_or_wait
    if not isinstance(intake, dict) or intake.get('current_run_id') != Path(work).name:
        raise ValueError('unable_to_review: independent intake does not match original run')
    root = (task_packet.heritage.RUNS / intake['current_run_id']).resolve(strict=True)
    if Path(work).resolve(strict=True) != root:
        raise ValueError('unable_to_review: independent intake is outside the original run')
    waiting = receive_review_or_wait(**intake)
    raise ValueError('unable_to_review: ' + waiting['reason_code'])
