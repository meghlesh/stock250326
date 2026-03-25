from django.db import models
from django.contrib.auth.models import User
from django.db import models
from django.core.exceptions import ValidationError
import re

 


class Company(models.Model):
    name = models.CharField(max_length=50, unique=True)
    email = models.EmailField()
    owner = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="company_owner"
    )
    created_at = models.DateTimeField(auto_now_add=True)


    def __str__(self):
        return self.name
    
class Transaction(models.Model):
    STATUS_CHOICES = (
        ("DELIVERED", "Delivered"),
        ("PROCESSING", "Processing"),
        ("CANCELLED", "Cancelled"),
    )

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="transactions"
    )
    ref_id = models.CharField(max_length=20, unique=True)
    item_name = models.CharField(max_length=200)
    quantity = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.ref_id
    

def validate_name(value):
    value = value.strip()

    if not value:
        raise ValidationError("This field cannot be empty.")

    if len(value) > 20:
        raise ValidationError("Maximum 20 characters allowed.")

    if not re.match(r'^[A-Za-z]+$', value):
        raise ValidationError("Only alphabetic characters are allowed.")


class Vendor(models.Model):
    primary_contact_first_name = models.CharField(
        max_length=20,
        validators=[validate_name]
    )
    primary_contact_last_name = models.CharField(
        max_length=20,
        validators=[validate_name]
    )

    company_name = models.CharField(max_length=50)
    display_name = models.CharField(max_length=50)
    email = models.EmailField()
    mobile = models.CharField(max_length=10)
    address = models.TextField(max_length=500)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)



class Staff(models.Model):
    company = models.ForeignKey(
        "Company",
        on_delete=models.CASCADE,
        related_name="staff"
    )
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name