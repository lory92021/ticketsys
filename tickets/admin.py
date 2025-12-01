from django.contrib import admin
from .models import Ticket, Message
from django.contrib.auth.models import User, Group


admin.site.unregister(User)
admin.site.unregister(Group)

admin.site.register(Ticket)
admin.site.register(Message)