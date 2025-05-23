# UserCreatedObject Permission System

This document outlines the permission system for UserCreatedObject models across both class-based views and viewsets.

## Architecture Overview

BRIT uses a dual architecture for handling UserCreatedObject models:

1. **Django Class-Based Views**: Used for template-rendered HTML responses
2. **Django REST Framework ViewSets**: Used for API endpoints returning JSON

Both systems should enforce the same permission rules and publication workflow, ensuring consistent behavior regardless of the interface.

## Core Permission Concepts

### Publication Status

UserCreatedObjects have a `publication_status` field with possible values:

- `private`: Only visible to the owner and staff
- `review`: In review process - visible to owner, moderators and staff
- `published`: Publicly visible to all users
- `archived`: Historical version - visible to owner and staff

### Permission Rules

| Action | Object Status | Anonymous Users | Regular Users | Object Owners | Moderators/Staff |
|--------|---------------|-----------------|---------------|---------------|------------------|
| View   | published     | ✅              | ✅            | ✅            | ✅               |
| View   | review        | ❌              | ❌            | ✅            | ✅               |
| View   | private       | ❌              | ❌            | ✅            | ✅               |
| View   | archived      | ❌              | ❌            | ✅            | ✅               |
| Create | N/A           | ❌              | ✅ (with permission) | ✅ (with permission) | ✅               |
| Edit   | published     | ❌              | ❌            | ❌            | ✅               |
| Edit   | review        | ❌              | ❌            | ✅            | ✅               |
| Edit   | private       | ❌              | ❌            | ✅            | ❌               |
| Edit   | archived      | ❌              | ❌            | ❌            | ✅               |

### Review Workflow Actions

| Action              | Allowed Users                    | Requirements                       |
|---------------------|----------------------------------|-----------------------------------|
| register_for_review | Object owner                     | Object is 'private'               |
| withdraw_from_review| Object owner                     | Object is 'review'                |
| approve             | Moderators                       | Object is 'review'                |
| reject              | Moderators                       | Object is 'review'                |
| archive             | Moderators/Owner (if published)  | Object is 'published'             |

## Implementation for Class-Based Views

### Mixins

1. **UserCreatedObjectReadAccessMixin**: Controls read access to objects
   - Published objects: accessible to all users
   - Unpublished objects: only accessible to owners and staff

2. **UserCreatedObjectWriteAccessMixin**: Controls write access to objects
   - Published objects: only staff can edit
   - Review/Private objects: only owners can edit

3. **CreateUserObjectMixin**: Controls object creation
   - Staff can always create objects
   - Regular users must have appropriate model permission

### Standard Views

- **UserCreatedObjectCreateView**: Object creation with owner assignment
- **UserCreatedObjectDetailView**: Object viewing with permission checks
- **UserCreatedObjectUpdateView**: Object editing with permission checks
- **UserCreatedObjectDeleteView**: Object deletion with permission checks

## Implementation for ViewSets

### Permission Classes

1. **UserCreatedObjectPermission**: 
   - Handles safe methods (GET, HEAD, OPTIONS)
   - Handles object-level permissions based on ownership and publication status
   - Controls workflow actions (register_for_review, approve, etc.)
   - **CRITICAL BUG (to be fixed)**: Currently allows any authenticated user to create objects without checking model permissions

### ViewSet Classes

1. **UserCreatedObjectViewSet**:
   - Applies UserCreatedObjectPermission
   - Filters queryset based on authentication and publication status
   - Provides review workflow actions as DRF actions
   - Sets owner automatically on object creation

### GeoJSON Support (Planned)

A **GeoJSONMixin** will provide geospatial functionality for UserCreatedObject viewsets:
   - Respects the same permission model as UserCreatedObjectViewSet
   - Supports scope-based filtering (private/published)
   - Configurable serializer class

## Required Fixes

1. **UserCreatedObjectPermission** needs to be updated to check model permissions for the 'create' action:
   ```python
   # In has_permission method:
   if getattr(view, 'action', None) == 'create':
       # Get model from viewset
       model = view.get_queryset().model
       app_label = model._meta.app_label
       model_name = model._meta.model_name
       # Check if user has 'add' permission
       return (request.user and request.user.is_authenticated and 
               request.user.has_perm(f'{app_label}.add_{model_name}'))
   ```

## Best Practices

1. **Consistency**: Always use the appropriate mixin/viewset for UserCreatedObject models
2. **Permissions**: Ensure users have proper model permissions via Django admin
3. **Testing**: Test all permission combinations (anonymous, authenticated, owner, staff)
4. **Error Messages**: Provide clear error messages for permission failures
5. **Documentation**: Update this document when permission logic changes
