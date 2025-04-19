import os
import sqlite3
import requests
from telegram import Update, Document
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters

BOT_TOKEN = os.getenv("BOT_TOKEN")

conn = sqlite3.connect("database.db")
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT,
    content TEXT
)
""")
conn.commit()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Pošli mi .txt soubor nebo napiš `search: slovo`, nebo `link: https://...`.")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc: Document = update.message.document
    if not doc.file_name.endswith(".txt"):
        await update.message.reply_text("❌ Jen .txt soubory prosím.")
        return
    if doc.file_size > 20 * 1024 * 1024:
        await update.message.reply_text("⚠️ Soubor je moc velký. Zkus poslat odkaz přes `link:`.")
        return
    file = await doc.get_file()
    content = await file.download_as_bytearray()
    decoded = content.decode("utf-8", errors="ignore")
    cursor.execute("INSERT INTO files (filename, content) VALUES (?, ?)", (doc.file_name, decoded))
    conn.commit()
    await update.message.reply_text(f"✅ `{doc.file_name}` uložen.")

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if not text.lower().startswith("link:"):
        return
    url = text[5:].strip()
    await update.message.reply_text("⏬ Stahuju soubor...")
    try:
        # Gofile API přesměruje na reálný soubor
        response = requests.get(url, allow_redirects=True)
        final_url = response.url
        file_data = requests.get(final_url)
        decoded = file_data.content.decode("utf-8", errors="ignore")
        filename = final_url.split("/")[-1] or "downloaded.txt"
        cursor.execute("INSERT INTO files (filename, content) VALUES (?, ?)", (filename, decoded))
        conn.commit()
        await update.message.reply_text(f"✅ Soubor z `{url}` byl úspěšně stažen a uložen jako `{filename}`.")
    except Exception as e:
        await update.message.reply_text(f"❌ Chyba při stahování: {e}")

async def search_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if not text.lower().startswith("search:"):
        return
    keyword = text[7:].strip().lower()
    cursor.execute("SELECT filename, content FROM files")
    results = []
    for filename, content in cursor.fetchall():
        lines = content.split("\n")
        for i, line in enumerate(lines, 1):
            if keyword in line.lower():
                results.append(f"📄 {filename} (řádek {i}): {line.strip()}")
                if len(results) >= 10:
                    break
        if len(results) >= 10:
            break
    if results:
        await update.message.reply_text("\n\n".join(results))
    else:
        await update.message.reply_text(f"❌ Nic pro '{keyword}'.")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^link:"), handle_link))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^search:"), search_handler))
    app.run_polling()

if __name__ == "__main__":
    main()
