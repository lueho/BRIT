"""Sample-scoped permission helpers shared by HTML views and API viewsets."""

from utils.object_management.permissions import get_object_policy


def can_add_data_to_sample(user, sample, previous_sample_id, policy_key, request=None):
    """Whether *user* may attach relation data to *sample* under *policy_key*.

    Used when creating or re-assigning compositions, component measurements,
    and property values. Skips the policy check when there is nothing to
    protect: no target sample, or the instance stays on its previous sample.
    """
    if sample is None or sample.pk == previous_sample_id:
        return True
    policy = get_object_policy(user, sample, request=request)
    return bool(policy[policy_key])
