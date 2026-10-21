import uuid
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra):
        if not email:
            raise ValueError("Email is required")

        email = self.normalize_email(email)
        user = self.model(email=email, **extra)   

        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault('is_staff', True)
        extra.setdefault('is_superuser', True)
        extra.setdefault('role', 'general_admin')
        return self.create_user(email, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):   
    ROLE_CHOICES = [
        ('general_admin', 'General Administrator'),
        ('team_leader', 'Response Team Leader'),
        ('team_member', 'Response Team Member'),
        ('general_user', 'General User'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    full_name = models.CharField(max_length=150)
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=20, blank=True)
    role = models.CharField(max_length=30, choices=ROLE_CHOICES, default='general_user')
    is_active = models.BooleanField(default=True)      
    is_staff = models.BooleanField(default=False)       
    must_change_password = models.BooleanField(default=False)
    accepted_terms_version = models.CharField(max_length=20, blank=True, default='')
    accepted_terms_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)   

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['full_name']

    def __str__(self):
        return f"{self.full_name} ({self.role})"
