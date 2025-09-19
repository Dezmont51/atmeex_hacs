#!/usr/bin/env python3
"""
Простой пример авторизации по телефону
"""

import asyncio
from atmeexpy import AtmeexClient

async def main():
    phone = input("Введите телефон: ")
    
    # Запрос SMS кода
    print(f"Запрашиваем SMS код для {phone}...")
    sms_client = AtmeexClient(phone)
    await sms_client.request_sms_code()
    print("SMS код отправлен!")
    
    # Ввод кода с клавиатуры
    code = input("Введите код из SMS: ")
    
    # Авторизация с полученным кодом
    client = AtmeexClient(phone, code)
    devices = await client.get_devices()
    print(f"Найдено устройств: {len(devices)}")

if __name__ == "__main__":
    asyncio.run(main()) 
