from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.generic import ListView, View

from case_studies.soilcom.models import Collection
from utils.models import UserCreatedObject
from utils.permissions import UserCreatedObjectPermission


class ReviewDashboardView(ListView):
    """Dashboard showing all objects in review status that the user can moderate."""
    template_name = 'moderation/review_dashboard.html'
    context_object_name = 'review_items'
    paginate_by = 20

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get_queryset(self):
        # Start with an empty queryset
        review_items = []

        # Get all model classes that inherit from UserCreatedObject
        # For now, we'll just use Collection as an example
        model_classes = [Collection]
        
        for model_class in model_classes:
            # Check if user can moderate this model type
            content_type = ContentType.objects.get_for_model(model_class)
            perm_codename = f'can_moderate_{model_class._meta.model_name}'
            app_label = model_class._meta.app_label
            full_perm = f'{app_label}.{perm_codename}'
            
            if self.request.user.is_staff or self.request.user.has_perm(full_perm):
                # Get items in review for this model
                items = model_class.objects.in_review().select_related('owner', 'approved_by')
                review_items.extend(items)

        # Sort by submitted_at date (newest first)
        review_items.sort(key=lambda x: x.submitted_at or timezone.now(), reverse=True)
        return review_items
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Content Review Dashboard'
        return context


class ApproveItemView(View):
    """View to approve an item that is in review."""
    
    @method_decorator(login_required)
    def post(self, request, *args, **kwargs):
        content_type_id = kwargs.get('content_type_id')
        object_id = kwargs.get('object_id')
        
        content_type = get_object_or_404(ContentType, pk=content_type_id)
        model_class = content_type.model_class()
        obj = get_object_or_404(model_class, pk=object_id)
        
        # Check permissions
        if not UserCreatedObjectPermission().has_approve_permission(request, obj):
            raise PermissionDenied("You don't have permission to approve this item.")
        
        # Approve the item
        try:
            obj.approve(user=request.user)
            messages.success(request, f"{obj._meta.verbose_name} has been approved and published.")
        except Exception as e:
            messages.error(request, f"Error approving item: {str(e)}")
        
        # Redirect back to the dashboard
        return redirect('moderation:review_dashboard')


class RejectItemView(View):
    """View to reject an item that is in review."""
    
    @method_decorator(login_required)
    def post(self, request, *args, **kwargs):
        content_type_id = kwargs.get('content_type_id')
        object_id = kwargs.get('object_id')
        
        content_type = get_object_or_404(ContentType, pk=content_type_id)
        model_class = content_type.model_class()
        obj = get_object_or_404(model_class, pk=object_id)
        
        # Check permissions
        if not UserCreatedObjectPermission().has_approve_permission(request, obj):
            raise PermissionDenied("You don't have permission to reject this item.")
        
        # Reject the item
        try:
            obj.reject()
            messages.success(request, f"{obj._meta.verbose_name} has been rejected and returned to private status.")
        except Exception as e:
            messages.error(request, f"Error rejecting item: {str(e)}")
        
        # Redirect back to the dashboard
        return redirect('moderation:review_dashboard')


class SubmitForReviewView(View):
    """View to submit an item for review."""
    
    @method_decorator(login_required)
    def post(self, request, *args, **kwargs):
        content_type_id = kwargs.get('content_type_id')
        object_id = kwargs.get('object_id')
        
        content_type = get_object_or_404(ContentType, pk=content_type_id)
        model_class = content_type.model_class()
        obj = get_object_or_404(model_class, pk=object_id)
        
        # Check permissions (must be owner)
        if obj.owner != request.user and not request.user.is_staff:
            raise PermissionDenied("You don't have permission to submit this item for review.")
        
        # Submit for review
        try:
            obj.submit_for_review()
            messages.success(request, f"{obj._meta.verbose_name} has been submitted for review.")
        except Exception as e:
            messages.error(request, f"Error submitting for review: {str(e)}")
        
        # Redirect back to the object detail page
        return HttpResponseRedirect(obj.get_absolute_url())


class WithdrawFromReviewView(View):
    """View to withdraw an item from review."""
    
    @method_decorator(login_required)
    def post(self, request, *args, **kwargs):
        content_type_id = kwargs.get('content_type_id')
        object_id = kwargs.get('object_id')
        
        content_type = get_object_or_404(ContentType, pk=content_type_id)
        model_class = content_type.model_class()
        obj = get_object_or_404(model_class, pk=object_id)
        
        # Check permissions (must be owner)
        if obj.owner != request.user and not request.user.is_staff:
            raise PermissionDenied("You don't have permission to withdraw this item from review.")
        
        # Withdraw from review
        try:
            obj.withdraw_from_review()
            messages.success(request, f"{obj._meta.verbose_name} has been withdrawn from review.")
        except Exception as e:
            messages.error(request, f"Error withdrawing from review: {str(e)}")
        
        # Redirect back to the object detail page
        return HttpResponseRedirect(obj.get_absolute_url())
