#!/usr/bin/env python
"""非互動式創建 Django 超級使用者帳號的腳本"""
import os
import sys
import django

# 設置 Django 環境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_project.settings')
django.setup()

from django.contrib.auth.models import User

def create_superuser():
    """創建超級使用者（預設值）"""
    username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin')
    email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@example.com')
    password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'admin123')
    
    # 檢查使用者是否已存在
    if User.objects.filter(username=username).exists():
        print(f'使用者名稱 "{username}" 已存在，跳過創建。')
        print(f'你可以直接使用現有的帳號登入。')
        return
    
    # 創建超級使用者
    User.objects.create_superuser(
        username=username,
        email=email,
        password=password
    )
    
    print(f'\n✓ 超級使用者已成功創建！')
    print(f'  使用者名稱: {username}')
    print(f'  電子郵件: {email}')
    print(f'  密碼: {password}')
    print(f'\n⚠️  請記住修改預設密碼！')
    print(f'\n現在你可以訪問 http://localhost:8000/admin/ 並使用此帳號登入。')

if __name__ == '__main__':
    create_superuser()

