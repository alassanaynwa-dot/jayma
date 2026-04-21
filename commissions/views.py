from django.shortcuts import render


def revenues_dashboard(request):
    return render(request, "dashboard/revenues.html")
