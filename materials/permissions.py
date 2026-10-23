"""Sample-scoped permission helpers shared by HTML views and API viewsets."""

from utils.object_management.policy import decide, decide_reassign


def can_add_data_to_sample(
    user,
    sample,
    previous_sample_id,
    policy_key=None,
    request=None,
    *,
    model=None,
    obj=None,
):
    """Whether *user* may attach relation data to *sample*.

    Bound creates delegate to ``decide(user, "create", model, parent=sample)``;
    persisted rows delegate to ``decide`` for same-parent edits and
    ``decide_reassign`` when the row moves to a different sample, so owned
    children require edit on both roots and independent evidence rows follow
    their typed attachment eligibility.
    """
    del policy_key, request  # superseded by the canonical core decisions
    if sample is None or not getattr(user, "is_authenticated", False):
        return False
    if obj is not None and getattr(obj, "pk", None) is not None:
        if previous_sample_id is not None and previous_sample_id != sample.pk:
            return decide_reassign(user, obj, sample).allowed
        return decide(user, "edit", obj).allowed
    if model is None and obj is not None:
        model = type(obj)
    if model is None:
        return False
    return decide(user, "create", model, parent=sample).allowed
