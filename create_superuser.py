#!/usr/bin/env python
"""創建 Django 超級使用者帳號的腳本"""
import os
import sys
import django

# 設置 Django 環境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_project.settings')
django.setup()

from django.contrib.auth.models import User

def create_superuser():
    """創建超級使用者"""
    username = input('請輸入使用者名稱 (預設: admin): ').strip() or 'admin'
    email = input('請輸入電子郵件 (預設: admin@example.com): ').strip() or 'admin@example.com'
    
    # 檢查使用者是否已存在
    if User.objects.filter(username=username).exists():
        print(f'錯誤：使用者名稱 "{username}" 已存在！')
        return
    
    # 輸入密碼
    while True:
        password = input('請輸入密碼: ').strip()
        if not password:
            print('密碼不能為空，請重新輸入。')
            continue
        
        password_confirm = input('請再次輸入密碼確認: ').strip()
        if password != password_confirm:
            print('兩次輸入的密碼不一致，請重新輸入。')
            continue
        break
    
    # 創建超級使用者
    User.objects.create_superuser(
        username=username,
        email=email,
        password=password
    )
    
    print(f'\n✓ 超級使用者 "{username}" 已成功創建！')
    print(f'  電子郵件: {email}')
    print(f'\n現在你可以訪問 http://localhost:8000/admin/ 並使用此帳號登入。')

if __name__ == '__main__':
    create_superuser()

