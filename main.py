#!/usr/bin/env python3
import os
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"  # отключает CUDA полностью
import sys
import subprocess
from PIL import Image, ImageEnhance

# --- Загрузка секретов ---
from dotenv import load_dotenv
import requests

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

if not TELEGRAM_TOKEN or not CHAT_ID:
    print("❌ Отсутствуют TELEGRAM_TOKEN или CHAT_ID в .env", file=sys.stderr)
    sys.exit(1)

# --- Настройки ---
SHOT_PATH = "/tmp/ocr_shot.png"
LANG = "eng"  # или "eng+rus" для двух языков

# --- 1. Скриншот ---
print("🖱️  Выбери область на экране...")
try:
    subprocess.run(["scrot", "-s", SHOT_PATH], check=True)
except subprocess.CalledProcessError:
    print("❌ Ошибка: не удалось сделать скриншот.", file=sys.stderr)
    sys.exit(1)

if not os.path.exists(SHOT_PATH):
    print("❌ Скриншот не найден.", file=sys.stderr)
    sys.exit(1)

# --- 2. Предобработка изображения ---
try:
    img = Image.open(SHOT_PATH).convert('L')  # серый

    # Увеличение в 2x — критически важно для качества
    img = img.resize((img.width * 2, img.height * 2), Image.NEAREST)

    # Усиление контраста и резкости
    img = ImageEnhance.Contrast(img).enhance(2.5)
    img = ImageEnhance.Sharpness(img).enhance(2.0)

    # Бинаризация: чёткое разделение текст/фон
    #threshold = 160
    #img = img.point(lambda x: 0 if x < threshold else 255, mode='1')

except Exception as e:
    print(f"❌ Ошибка обработки: {e}", file=sys.stderr)
    sys.exit(1)

# --- 3. OCR через Tesseract ---
try:
    import pytesseract
    text = pytesseract.image_to_string(
        img,
        lang=LANG,
        config='--psm 11'  # сплошной текст без структуры — лучший режим для скриншотов
    )
    # Убираем form feed и лишние пробелы
    text = text.replace('\f', '').strip()
except Exception as e:
    print(f"❌ Ошибка Tesseract: {e}", file=sys.stderr)
    sys.exit(1)

# --- 4. ЛОКАЛЬНЫЙ ПЕРЕВОД (en → ru) ---
print("🌍 Перевод на русский (оффлайн)...")
try:
    import argostranslate.package
    import argostranslate.translate

    from_code = "en"
    to_code = "ru"

    # Правильная проверка: установлен ли пакет en→ru?
    installed = any(
        pkg.from_code == from_code and pkg.to_code == to_code
        for pkg in argostranslate.package.get_installed_packages()
    )

    if not installed:
        print("📦 Скачивание модели перевода en→ru (однократно, ~30 МБ)...")
        argostranslate.package.update_package_index()
        available_packages = argostranslate.package.get_available_packages()
        package_to_install = next(
            pkg for pkg in available_packages
            if pkg.from_code == from_code and pkg.to_code == to_code
        )
        argostranslate.package.install_from_path(package_to_install.download())

    translated = argostranslate.translate.translate(text, from_code, to_code)
except Exception as e:
    print(f"⚠️  Ошибка перевода: {e}. Используем оригинал.")
    translated = text

# --- 5. Отправка в Telegram ---
print("📤 Отправка в Telegram...")
try:
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": f"📄 EN:\n{text}\n\n🇷🇺 RU:\n{translated}",
        "parse_mode": "HTML"  # можно убрать, если не используешь HTML
    }
    resp = requests.post(url, data=payload, timeout=10)
    if resp.status_code == 200:
        print("✅ Отправлено!")
    else:
        print(f"❌ Ошибка Telegram API: {resp.status_code} – {resp.text}")
except Exception as e:
    print(f"⚠️  Не удалось отправить в Telegram: {e}")

# --- 6. Вывод ---
print("\n" + "=" * 50)
print("📄 Распознанный текст (en):")
print("-" * 50)
print(text)
print("\n[RU] Перевод (ru):")
print("-" * 50)
print(translated)
print("=" * 50)

# --- 7. Очистка ---
if os.path.exists(SHOT_PATH):
    os.remove(SHOT_PATH)


#       "You did. But i didn't. So, it's time.
#       We end. Don't forget this."
