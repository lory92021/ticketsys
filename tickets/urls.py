from django.urls import path
import tickets.views as views

urlpatterns = [
    # ----- LISTA / PRINCIPALE -----
    path("", views.ticket_list, name="ticket_list"),
    path("my/", views.my_tickets, name="my_tickets"),

    path("<int:ticket_id>/", views.ticket_detail, name="ticket_detail"),
    path("new/", views.ticket_create, name="ticket_create"),
    path("<int:ticket_id>/assign/", views.ticket_assign, name="ticket_assign"),
    path("<int:ticket_id>/close/", views.ticket_close, name="ticket_close"),
   


    # ----- OPERATOR -----
    path("operator/open/", views.operator_open, name="operator_open"),
    path("operator/assigned/", views.operator_assigned, name="operator_assigned"),
    path("operator/", views.operator_dashboard, name="operator_dashboard"),

    # ----- ADMIN -----
    path("admin/dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path("admin/users/", views.admin_users, name="admin_users"),
    path("admin/users/<int:user_id>/edit/", views.admin_user_edit, name="admin_user_edit"),
    path("admin/users/<int:user_id>/delete/", views.admin_user_delete, name="admin_user_delete"),
    path("admin/users/<int:user_id>/", views.admin_user_detail, name="admin_user_detail"),
    path("admin/users/<int:user_id>/make-operator/", views.make_operator, name="make_operator"),
    path("admin/users/<int:user_id>/make-admin/", views.make_admin, name="make_admin"),
    path("admin/users/<int:user_id>/make-user/", views.make_user, name="make_user"),
    path("admin/ticket/<int:ticket_id>/reassign/", views.ticket_reassign_view, name="ticket_reassign_view"),
    path("admin/ticket/<int:ticket_id>/reassign/do/", views.ticket_reassign, name="ticket_reassign"),
    path("admin/logs/", views.admin_logs, name="admin_logs"),

    path("secure-download/<int:attachment_id>/", views.secure_download, name="secure_download"),
    path("attachment/<int:attachment_id>/delete/", views.attachment_delete, name="attachment_delete"),
    path("attachment/<int:attachment_id>/preview/", views.attachment_preview, name="attachment_preview"),
    path("admin/report/", views.report_dashboard, name="report_dashboard"),

]
