"""Sample-scoped permission helpers shared by HTML views and API viewsets."""

from utils.object_management.policy import decide, decide_reassign


def can_add_data_to_sample(user, model, sample, previous_sample_id, obj=None):
    """Whether *user* may attach relation data of *model* to *sample*.

    Owned children resolve through parent edit; independent evidence rows
    need their own add capability plus the declared parent-attachment gate.
    Reparenting an existing row re-checks both parents via decide_reassign.
    Skips when there is nothing to protect: no target sample, or the
    instance stays on its previous sample.
    """
    if sample is None or sample.pk == previous_sample_id:
        return True
    if obj is not None and getattr(obj, "pk", None):
        return decide_reassign(user, obj, sample).allowed
    return decide(user, "create", model, parent=sample).allowed
