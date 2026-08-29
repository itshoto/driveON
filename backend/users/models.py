from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models


class Plan(models.Model):
    """Configurable subscription tier -- see driveON SOP section 69."""

    name = models.CharField(max_length=50, unique=True)
    # One combined cap across every connected provider (Google + OneDrive),
    # matching "one unified storage pool" -- not a per-provider limit.
    max_connected_accounts = models.PositiveIntegerField(default=5)
    max_file_size_mb = models.PositiveIntegerField(default=4096)
    ai_queries_per_month = models.PositiveIntegerField(default=50)

    def __str__(self):
        return self.name

    @classmethod
    def get_default_plan(cls):
        plan, _ = cls.objects.get_or_create(
            name="free",
            defaults={
                "max_connected_accounts": 5,
                "max_file_size_mb": 4096,
                "ai_queries_per_month": 50,
            },
        )
        return plan


class UserManager(BaseUserManager):
    def create_user(self, firebase_uid, username, email, **extra_fields):
        if not firebase_uid:
            raise ValueError("firebase_uid is required")
        if not username:
            raise ValueError("username is required")
        email = self.normalize_email(email)
        user = self.model(
            firebase_uid=firebase_uid, username=username, email=email, **extra_fields
        )
        user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, firebase_uid, username, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if not extra_fields.get("is_staff") or not extra_fields.get("is_superuser"):
            raise ValueError("Superuser must have is_staff=True and is_superuser=True.")

        email = self.normalize_email(email)
        user = self.model(firebase_uid=firebase_uid, username=username, email=email, **extra_fields)
        # Unlike create_user (Firebase owns application-user auth), an admin
        # account needs a real Django password to log into /admin/.
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user


class User(AbstractBaseUser, PermissionsMixin):
    """A driveON account. Authentication is delegated to Firebase Auth;
    this row is the application profile keyed off the Firebase UID."""

    firebase_uid = models.CharField(max_length=128, unique=True)
    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(unique=True)
    plan = models.ForeignKey(
        Plan, on_delete=models.PROTECT, related_name="users", null=True
    )
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = "firebase_uid"
    REQUIRED_FIELDS = ["username", "email"]

    def __str__(self):
        return self.username

    def max_connected_accounts(self):
        return self.plan.max_connected_accounts if self.plan else 5
