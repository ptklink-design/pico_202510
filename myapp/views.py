from django.shortcuts import render
from django.http import HttpResponse

# Create your views here.

def index(request):
    """首頁視圖"""
    return HttpResponse("<h1>歡迎來到 Django 專案！</h1><p>這是 myapp 應用程式的主頁。</p>")

def about(request):
    """關於頁面視圖"""
    return HttpResponse("<h1>關於我們</h1><p>這是一個 Django 學習專案。</p>")
