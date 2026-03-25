from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from company.models import Transaction
from accounts.models import UserProfile
from django.http import HttpResponse
from reportlab.lib.pagesizes import A4
from datetime import date, timedelta
from reportlab.pdfgen import canvas
from company.models import Company, Staff
from inventory.models import StockTransaction, Product, ProductBatch, SalesOrder 
import csv
from django.db import IntegrityError
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from datetime import datetime
from django.db.models import Sum #26-2-26
from django.db.models import Q #26-2-26
from django.db.models.functions import Coalesce
from inventory.models import InventoryAlert
# =========================
# COMPANY OWNER LOGIN
# =========================
def company_login(request):
    if request.user.is_authenticated:
        # If already logged in, redirect safely to dashboard
        profile = UserProfile.objects.filter(user=request.user).first()
        if profile and profile.role == "COMPANY_OWNER":
            return redirect("company_dashboard")

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)

        if user:
            profile = UserProfile.objects.filter(user=user).first()

            if profile and profile.role == "COMPANY_OWNER":
                login(request, user)
                messages.success(request, f"Welcome back, {user.username}!")
                return redirect("company_dashboard")
            else:
                messages.error(request, "Access denied: This portal is for company owners only.")
        else:
            messages.error(request, "Invalid username or password.")

    return render(request, "company/company_login.html")



from django.db.models import Sum
from django.db.models.functions import TruncDate
from datetime import timedelta, date
import json

@login_required
def company_dashboard(request):
    profile = UserProfile.objects.get(user=request.user)
    company = profile.company

    # Welcome Banner Efficiency logic & count
    total_orders = SalesOrder.objects.filter(company=company).count()
    delivered_orders = SalesOrder.objects.filter(company=company, status="DELIVERED").count()

    efficiency = 0
    if total_orders > 0:
        efficiency = round((delivered_orders/total_orders)*100)
    # 26-2-26 - Added pending shipments count to dashboard context
    pending_shipments = SalesOrder.objects.filter(
        company=company
    ).filter(
        Q(status__iexact='pending') |
        Q(status__iexact='processing')
    ).count()

    # 26-2-26 Count Out of Stock Products
    products = Product.objects.filter(company=company).annotate(
        total_stock=Coalesce(Sum('productbatch__quantity'), 0)
    )

    out_of_stock_count = products.filter(total_stock=0).count()

    # Recent 5 Sales Orders with items + products (optimized)
    transactions = (
        SalesOrder.objects
        .filter(company=company)
        .select_related("company")
        .prefetch_related("items__product")
        .order_by("-created_at")[:5]
    )

    # Attach product names + total quantity per order
    for order in transactions:
        order.product_names = ", ".join(
            [item.product.name for item in order.items.all()]
        )
        order.total_quantity = sum(
            item.quantity for item in order.items.all()
        )

    today = date.today()
    near_expiry_limit = today + timedelta(days=30)

    # 🔹 Product counts
    total_products = Product.objects.filter(company=company).count()

    low_stock_products = Product.objects.filter(
        company=company,
        stock_quantity__lte=5
    ).count()

    # 26-2-26
    # Total Revenue (only DELIVERED orders)
    total_revenue = SalesOrder.objects.filter(
        company=company,
        status="DELIVERED"
    ).aggregate(total=Sum("total_amount"))["total"] or 0

    # 🔹 Batch health - Expired batches list
    expired_batches_list = ProductBatch.objects.filter(
        company=company,
        is_active=True,
        expiry_date__isnull=False,
        expiry_date__lt=date.today()
    ).select_related('product').order_by('expiry_date')

    expired_batches = expired_batches_list.count()

    # 🔹 Current/Active batches list
    current_batches_list = ProductBatch.objects.filter(
        company=company,
        is_active=True,
        expiry_date__isnull=False,
        expiry_date__gte=date.today()
    ).select_related('product').order_by('expiry_date')

    near_expiry_batches = current_batches_list.filter(
        expiry_date__range=(today, near_expiry_limit),
        quantity__gt=0
    ).count()



    # 🔔 UNREAD INVENTORY ALERTS (NEW)
    unread_alerts_count = InventoryAlert.objects.filter(
        company=company,
        is_read=False
    ).count()
    # 📈 Sales Trend - Last 7 Days (DELIVERED Orders)
    last_7_days = today - timedelta(days=6)

    sales_qs = (
        SalesOrder.objects
        .filter(
            company=company,
            status="DELIVERED",
            created_at__date__gte=last_7_days
        )
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(total=Sum("total_amount"))
        .order_by("day")
    )

    # Convert queryset to dictionary
    sales_dict = {item["day"]: item["total"] for item in sales_qs}

    # Ensure all 7 days appear (even if 0 sales)
    sales_trend = []
    for i in range(7):
        day = last_7_days + timedelta(days=i)
        sales_trend.append({
            "day": day.strftime("%d %b"),
            "total": float(sales_dict.get(day, 0))
        })

    context = {
        "total_products": total_products,
        "low_stock_products": low_stock_products,
        "expired_batches": expired_batches,
        "near_expiry_batches": near_expiry_batches,
        "unread_alerts_count": unread_alerts_count,  # 👈 NEW
        "total_revenue": total_revenue, # 26-2-26
        "pending_shipments": pending_shipments, # 26-2-26
        "company": company,
        "transactions": transactions,
        "out_of_stock_count": out_of_stock_count, # 26-2-26
        "sales_trend": json.dumps(sales_trend),
        "efficiency": efficiency,

    }

    return render(
        request,
        "company/company_dashboard.html",
        context
    )

# =========================
# OPERATIONS & PAGES
# =========================
@login_required
def new_entry(request):
    return render(request, "company/new_entry.html")

@login_required
def reports_page(request):
    return render(request, "company/reports.html")

@login_required
def add_stock(request):
    return render(request, "company/add_stock.html")

@login_required
def dispatcher(request):
    if request.method == "POST":
        order_number = request.POST.get('order_number')
        dispatch_date = request.POST.get('dispatch_date')

        if not dispatch_date:
            return render(request, 'company/dispatch.html', {
                'error': 'Dispatch Date is required.'
            })

        
        messages.success(request, "Order dispatched successfully.")
        return redirect('dispatch')

   
    return render(request, 'company/dispatch.html')

@login_required
def add_staff(request):
    profile = UserProfile.objects.get(user=request.user)
    company = profile.company

    if request.method == "POST":
        name = request.POST.get("staff_name")
        email = request.POST.get("email")

        # Create Staff
        Staff.objects.create(
            company=company,
            name=name,
            email=email
        )

        messages.success(request, "Staff member added successfully.")

        return redirect("staff_list")  # reload page to show message

    return render(request, "company/add_staff.html")

@login_required
def export_data(request):
    profile = UserProfile.objects.get(user=request.user)
    company = profile.company

    # When user clicks Export Now
    if request.method == "POST":
        return redirect("export_data_download")

    return render(request, "company/export.html", {"company": company})




@login_required
def export_data_download(request):
    profile = UserProfile.objects.get(user=request.user)
    company = profile.company

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="company_data.csv"'

    writer = csv.writer(response)
    writer.writerow(["Product Name", "Stock Quantity"])

    products = Product.objects.filter(company=company)

    for p in products:
        writer.writerow([p.name, p.stock_quantity])

    return response

@login_required
def transactions_list(request):
    profile = UserProfile.objects.select_related("company").filter(user=request.user).first()

    if not profile or profile.role != "COMPANY_OWNER":
        return redirect("company_login")

    transactions = Transaction.objects.filter(company=profile.company).order_by("-created_at")
    return render(request, "company/transactions_list.html", {"transactions": transactions})

# =========================
# COMPANY OWNER LOGOUT
# =========================
@login_required
def company_logout(request):
    """
    Handles secure logout for the company portal.
    Exclusively accepts POST requests to prevent accidental or malicious logouts.
    """
    if request.method == "POST":
        logout(request)
        messages.error(request, "You have been successfully logged out of the portal.")
        return redirect("company_login")
    
    # Redirect back to dashboard if someone tries to visit /logout via URL
    return redirect("company_dashboard")


# =========================
# SETTINGS
# =========================
@login_required
def company_settings(request):
    profile = UserProfile.objects.select_related("company").get(user=request.user)

    if profile.role != "COMPANY_OWNER":
        return redirect("company_login")

    company = profile.company

    if request.method == "POST":
        company.name = request.POST.get("company_name")
        company.email = request.POST.get("company_email")

        try:
            company.save()
        except IntegrityError:
            messages.error(request, "Email already exists")
            return redirect("company_settings")

        new_password = request.POST.get("new_password")
        if new_password:
            request.user.set_password(new_password)
            request.user.save()
            update_session_auth_hash(request, request.user)

        messages.success(request, "Settings updated successfully")
        return redirect("company_settings")

    return render(request, "company/company_settings.html", {"company": company})
@login_required
def export_stock_movement_pdf(request):
    company = Company.objects.get(owner=request.user)

    transactions = StockTransaction.objects.filter(
        product__company=company
    ).order_by('-created_at')

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="{company.name}_stock_movement_report.pdf"'
    )

    doc = SimpleDocTemplate(
        response,
        pagesize=A4,
        rightMargin=30,
        leftMargin=30,
        topMargin=40,
        bottomMargin=20
    )

    elements = []
    styles = getSampleStyleSheet()

    # Header style
    header_style = ParagraphStyle(
        "Header",
        parent=styles["Heading1"],
        fontSize=16,
        textColor=colors.white,
        alignment=1,
        spaceAfter=6
    )

    # Header bar
    header_data = [[
        Paragraph(f"{company.name} - Stock Movement Report", header_style)
    ]]

    header_table = Table(header_data, colWidths=[520])
    header_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#4071db")),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))

    elements.append(header_table)

    # Date
    elements.append(Spacer(1, 8))
    elements.append(Paragraph(
        f"Generated on: {datetime.now().strftime('%d %b %Y, %I:%M %p')}",
        styles["Normal"]
    ))
    elements.append(Spacer(1, 15))

    # Table data
    data = [
        ["Date", "Product", "Type", "Quantity"]
    ]

    for t in transactions:
        data.append([
            t.created_at.strftime("%d-%m-%Y"),
            t.product.name,
            t.transaction_type,
            str(t.quantity),
        ])

    table = Table(data, colWidths=[120, 200, 100, 80])

    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 10),

        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("ALIGN", (3, 1), (3, -1), "CENTER"),

        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.HexColor("#f1f5f9"), colors.white]),

        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
    ]))

    elements.append(table)

    doc.build(elements)
    return response

@login_required
def staff_list(request):
    profile = UserProfile.objects.get(user=request.user)
    company = profile.company

    staff_members = Staff.objects.filter(company=company)
    return render(request, "company/staff_list.html", {
        "staff_members": staff_members
    })