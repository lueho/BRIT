"""Access-control mixins for user-created objects.

Re-export shim: the canonical policy implementations live in
``utils.object_management.views``. Import from here keeps the historical
import location working for domain views while guaranteeing a single
policy implementation.
"""

from .views import (
    CreateUserObjectMixin,
    UserCreatedObjectReadAccessMixin,
    UserCreatedObjectWriteAccessMixin,
    UserOwnsObjectMixin,
)

__all__ = [
    "CreateUserObjectMixin",
    "UserCreatedObjectReadAccessMixin",
    "UserCreatedObjectWriteAccessMixin",
    "UserOwnsObjectMixin",
]
