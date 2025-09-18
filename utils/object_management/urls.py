from django.urls import path

from . import views

app_name = "object_management"

urlpatterns = [
    path("review/", views.ReviewDashboardView.as_view(), name="review_dashboard"),
    path(
        "review/detail/<int:content_type_id>/<int:object_id>/",
        views.ReviewItemDetailView.as_view(),
        name="review_item_detail",
    ),
    path(
        "comment/<int:content_type_id>/<int:object_id>/",
        views.AddReviewCommentView.as_view(),
        name="add_review_comment",
    ),
    path(
        "approve/<int:content_type_id>/<int:object_id>/",
        views.ApproveItemView.as_view(),
        name="approve_item",
    ),
    # Modal endpoints for confirmations (loaded into global #modal container)
    path(
        "modal/approve/<int:content_type_id>/<int:object_id>/",
        views.ApproveItemModalView.as_view(),
        name="approve_item_modal",
    ),
    path(
        "reject/<int:content_type_id>/<int:object_id>/",
        views.RejectItemView.as_view(),
        name="reject_item",
    ),
    path(
        "modal/reject/<int:content_type_id>/<int:object_id>/",
        views.RejectItemModalView.as_view(),
        name="reject_item_modal",
    ),
    path(
        "submit-for-review/<int:content_type_id>/<int:object_id>/",
        views.SubmitForReviewView.as_view(),
        name="submit_for_review",
    ),
    path(
        "modal/submit-for-review/<int:content_type_id>/<int:object_id>/",
        views.SubmitForReviewModalView.as_view(),
        name="submit_for_review_modal",
    ),
    path(
        "withdraw-from-review/<int:content_type_id>/<int:object_id>/",
        views.WithdrawFromReviewView.as_view(),
        name="withdraw_from_review",
    ),
    path(
        "modal/withdraw-from-review/<int:content_type_id>/<int:object_id>/",
        views.WithdrawFromReviewModalView.as_view(),
        name="withdraw_from_review_modal",
    ),
]
