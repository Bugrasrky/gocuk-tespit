import sqlite3

conn = sqlite3.connect("gocuk_gecmisi.db")
cursor = conn.cursor()
cursor.execute("SELECT * FROM raporlar")

for kayit in cursor.fetchall():
    print(kayit)

conn.close()