from fpdf import FPDF

pdf = FPDF()
pdf.set_auto_page_break(auto=True, margin=20)
pdf.add_page()

def reset_x():
    pdf.set_x(pdf.l_margin)

def h1(t):
    pdf.set_font("Helvetica", "B", 22)
    reset_x()
    pdf.cell(0, 14, t, new_x="LMARGIN", new_y="NEXT", align="C")

def h2(t):
    reset_x()
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, t, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)

def h3(t):
    reset_x()
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, t, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)

def p(t):
    reset_x()
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 6, t)
    pdf.ln(2)

def code(t):
    reset_x()
    pdf.set_font("Courier", "", 9)
    pdf.set_fill_color(235, 235, 235)
    pdf.multi_cell(0, 5, t, fill=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.ln(3)

def bullets(items):
    pdf.set_font("Helvetica", "", 10)
    for item in items:
        reset_x()
        pdf.multi_cell(0, 6, "  - " + item)
    pdf.ln(2)

# ===================== CONTENT =====================

h1("Patent Drafting Tool")
pdf.set_font("Helvetica", "", 13)
pdf.cell(0, 8, "Kurulum ve Kullanim Kilavuzu", new_x="LMARGIN", new_y="NEXT", align="C")
pdf.ln(12)

h2("1. Hizli Baslangic (Tek Komut)")
p("Gereksinim: Docker Desktop (tek gereksinim)\nIndirin: https://www.docker.com/products/docker-desktop")
p("Kurulum:")
code("git clone -b feature/fastapi-full-integration \\\n  https://github.com/melikedemirkoparan/bitirme-projesi-ui.git\ncd bitirme-projesi-ui\ndocker compose up --build")
p("Tarayicida http://localhost:8000 acin. Hepsi bu.")
p("Ne yapiyor:")
bullets([
    "PostgreSQL 16 veritabani containeri baslar",
    "DB hazir olana kadar bekler (healthcheck)",
    "Alembic migrationlari otomatik calisir (7 tablo)",
    "FastAPI sunucusu port 8000'de baslar",
    "RAG verileri cache varsa otomatik yuklenir",
])
p("Durdurmak icin: docker compose down")

pdf.add_page()
h2("2. Proje Mimarisi")
h3("Teknoloji Yigini")
bullets([
    "Backend: FastAPI (Python 3.12)",
    "Veritabani: PostgreSQL 16 (Docker)",
    "ORM: SQLAlchemy 2.0 + Alembic",
    "Vektor Arama: FAISS (faiss-cpu)",
    "Embedding: intfloat/multilingual-e5-base",
    "LLM: Mistral-7B via Colab (opsiyonel)",
    "Frontend: Vanilla JS + CSS (dark theme)",
    "Container: Docker Compose",
])

h3("Veritabani Semasi (7 tablo)")
bullets([
    "patent: Ana patent/proje kaydi",
    "claim: Patent talepleri (independent/dependent, apparatus/method)",
    "element: Patent unsurlari (isim, referans numarasi, tanim)",
    "claim_element: Claim-element baglantilari (siralama destekli)",
    "invention_disclosure: Bulus aciklama belgesi",
    "research_report: Arastirma raporu",
    "inventor_qa: Mucit soru-cevap",
])

pdf.add_page()
h2("3. Kullanim Kilavuzu")

h3("3.1 Proje Olusturma")
p("Ana sayfada '+ New Project' tiklayin. Proje adi ve patent sahibi girin.")

h3("3.2 Veri Yukleme (Excel)")
p("'Upload Data' butonuna tiklayin. Excel dosyasini yukleyin. Embeddingler olusturulur (ilk seferde birkac dakika, sonraki cache'den anlik).")

h3("3.3 BBF/Report Element Cikarma")
p("'Extract' butonuna tiklayin. BBF dokumani ve Report dosyasi yukleyin. Pipeline otomatik unsurlari cikarir ve element havuzuna ekler.")

h3("3.4 Claim Yonetimi")
bullets([
    "'+ Add Claim' ile yeni talep olusturun",
    "'+ Add Elements' ile havuzdan claim'e unsur baglayin",
    "Elementleri surukle-birak (drag & drop) ile claim'e ekleyin",
    "Element tree'de yukari/asagi butonlariyla siralama degistirin",
])

h3("3.5 AI Tanim Onerisi (3 Asama)")
bullets([
    "RAG Fragment: FAISS vektor aramasi ile benzer patent tanimlarindan genel teknik tanim",
    "BBF Fragment: Yuklenen BBF dokumanindan unsura ozel konumsal/iliskisel bilgi",
    "Final Definition: Iki fragmentin birlestirilmis hali",
])

h3("3.6 Colab LLM Baglantisi (Opsiyonel)")
p("Daha kaliteli tanimlar icin Google Colab'da Mistral-7B calistirilabilir. Colab'da notebook acin (T4 GPU), LLM sunucu kodunu calistirin, Settings'den ngrok URL'sini girin. LLM bagli degilse akilli fallback calisir.")

h3("3.7 Draft Olusturma")
bullets([
    "Assemble with Report: Tum element tanimlarini rapor formatinda birlestirir",
    "Go to AI Draft: Claim yapisiyla birlikte taslak olusturur",
    "Draft Composer: Tam patent taslagi olusturma sayfasi",
])

pdf.add_page()
h2("4. API Endpointleri")
endpoints = [
    ("GET/POST /api/patents", "Proje listele/olustur"),
    ("GET/DELETE /api/patents/{id}", "Proje detay/sil"),
    ("GET/POST .../claims", "Claim listele/olustur"),
    ("PATCH .../claims/{cid}/text", "Claim metni guncelle"),
    ("GET/POST .../elements", "Element listele/olustur"),
    ("PATCH .../elements/{eid}", "Element guncelle"),
    ("POST .../claims/{cid}/elements", "Element bagla"),
    ("POST /api/rag/generate-definition", "AI tanim onerisi"),
    ("POST /api/rag/set-llm-url", "LLM URL ayarla"),
    ("POST /api/pipeline/extract-elements", "BBF+Report element cikar"),
]
pdf.set_font("Courier", "", 8)
for ep, desc in endpoints:
    pdf.set_font("Courier", "", 8)
    pdf.cell(85, 5, ep)
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 5, desc, new_x="LMARGIN", new_y="NEXT")

pdf.ln(8)
h2("5. Sorun Giderme")
bullets([
    "Port kullanimda -> docker compose down -v ile temizleyin",
    "Data not loaded -> Upload Data ile Excel yukleyin",
    "BBF fragment bos -> Extract ile BBF tekrar yukleyin",
    "LLM kalitesi dusuk -> Colab'da Mistral-7B baglayin (Settings)",
])

pdf.output("C:/Users/melike/paten_draft_backend/docs/Patent_Drafting_Tool_Guide.pdf")
print("PDF created!")
