import sqlite3
import tkinter as tk
from tkinter import ttk, Toplevel
from paths import writable_path

DB_NAME = writable_path("gocuk_gecmisi.db")
def show_history_window(parent=None):
    """Veritabanındaki ölçüm geçmişini şık bir tabloda gösterir."""
    win = Toplevel(parent) if parent else tk.Tk()
    win.title("📋 Geçmiş Raporlar ve Ölçümler")
    win.geometry("900x400")
    win.attributes("-topmost", True)
    win.configure(bg="#f8fafc")

    # Üst Başlık
    header = tk.Frame(win, bg="#0f172a", pady=10)
    header.pack(fill="x")
    tk.Label(header, text="Geçmiş Göçük Ölçüm ve Fiyatlandırma Raporları", 
             font=("Arial", 12, "bold"), fg="white", bg="#0f172a").pack()

    # Tablo (Treeview) Stili
    style = ttk.Style()
    style.theme_use("clam")
    style.configure("Treeview.Heading", font=("Arial", 10, "bold"), background="#e2e8f0", foreground="#0f172a")
    style.configure("Treeview", font=("Arial", 9), rowheight=25, background="#ffffff", fieldbackground="#ffffff")
    style.map("Treeview", background=[('selected', '#3b82f6')])

    # Tablo Çerçevesi ve Scrollbar
    tree_frame = tk.Frame(win)
    tree_frame.pack(fill="both", expand=True, padx=10, pady=10)

    scroll_y = ttk.Scrollbar(tree_frame, orient="vertical")
    scroll_y.pack(side="right", fill="y")

    # Tablo Sütunları
    cols = ("ID", "Tarih", "Hasar Tipi", "Boyut (cm)", "Derinlik (mm)", "Tahmini Masraf", "Boya Durumu")
    tree = ttk.Treeview(tree_frame, columns=cols, show="headings", yscrollcommand=scroll_y.set)
    scroll_y.config(command=tree.yview)

    # Sütun Başlıkları ve Genişlikleri
    tree.heading("ID", text="ID")
    tree.column("ID", width=40, anchor="center")
    
    tree.heading("Tarih", text="Tarih & Saat")
    tree.column("Tarih", width=120, anchor="center")
    
    tree.heading("Hasar Tipi", text="Hasar Senaryosu")
    tree.column("Hasar Tipi", width=160, anchor="w")
    
    tree.heading("Boyut (cm)", text="Boyut (cm)")
    tree.column("Boyut (cm)", width=90, anchor="center")
    
    tree.heading("Derinlik (mm)", text="Derinlik (mm)")
    tree.column("Derinlik (mm)", width=90, anchor="center")
    
    tree.heading("Tahmini Masraf", text="Tahmini Masraf")
    tree.column("Tahmini Masraf", width=130, anchor="center")
    
    tree.heading("Boya Durumu", text="Boya Durumu")
    tree.column("Boya Durumu", width=130, anchor="center")

    tree.pack(fill="both", expand=True)

    # Veritabanından Verileri Çek ve Tabloya Ekle
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        # En son yapılan ölçüm en üstte çıksın diye ORDER BY id DESC yapıyoruz
        cursor.execute("SELECT * FROM raporlar ORDER BY id DESC")
        rows = cursor.fetchall()
        
        for row in rows:
            # Satırları renklendirme (çift ve tek satırlar farklı renk)
            tags = ('evenrow',) if row[0] % 2 == 0 else ('oddrow',)
            tree.insert("", "end", values=row, tags=tags)
            
        conn.close()
    except Exception as e:
        print(f"Veritabanı okuma hatası: {e}")

    # Satır renkleri
    tree.tag_configure('oddrow', background="#f1f5f9")
    tree.tag_configure('evenrow', background="#ffffff")

    if parent:
        win.wait_window()
    else:
        win.mainloop()

if __name__ == "__main__":
    show_history_window()