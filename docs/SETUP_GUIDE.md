# Patent Drafting Tool — Kurulum ve Kullanım Kılavuzu

## Hızlı Başlangıç (Tek Komut)

### Gereksinimler
- **Docker Desktop** (tek gereksinim — başka hiçbir şey kurmaya gerek yok)
- İndirin: https://www.docker.com/products/docker-desktop

### Kurulum

```bash
git clone -b feature/fastapi-full-integration https://github.com/melikedemirkoparan/bitirme-projesi-ui.git
cd bitirme-projesi-ui
docker compose up --build
```

Tarayıcıda **http://localhost:8000** açın. Hepsi bu.

### Ne Yapıyor

1. **PostgreSQL 16** veritabanı container'ı başlar
2. Veritabanı hazır olana kadar bekler (healthcheck)
3. **Alembic migration'ları** otomatik çalışır (7 tablo oluşturulur)
4. **FastAPI** sunucusu port 8000'de başlar
5. RAG verileri cache varsa otomatik yüklenir

### Durdurma

```bash
docker compose down
```

Veritabanı verileri Docker volume'da saklanır, durdurup başlatsanız da kaybolmaz.

---

## Proje Mimarisi

### Teknoloji Yığını

| Katman | Teknoloji |
|--------|-----------|
| Backend | FastAPI (Python 3.12) |
| Veritabanı | PostgreSQL 16 (Docker) |
| ORM | SQLAlchemy 2.0 + Alembic |
| Vektör Arama | FAISS (faiss-cpu) |
| Embedding | intfloat/multilingual-e5-base (sentence-transformers) |
| LLM | Mistral-7B via Colab (opsiyonel) veya akıllı fallback |
| Frontend | Vanilla JS + CSS (dark theme) |
| Container | Docker Compose |

### Veritabanı Şeması

7 tablo:
- **patent** — Ana patent/proje kaydı
- **claim** — Patent talepleri (independent/dependent, apparatus/method)
- **element** — Patent unsurları (isim, referans numarası, tanım)
- **claim_element** — Claim-element bağlantıları (sıralama destekli)
- **invention_disclosure** — Buluş açıklama belgesi
- **research_report** — Araştırma raporu
- **inventor_qa** — Mucit soru-cevap

### API Endpoint'leri

| Grup | Yol | Açıklama |
|------|-----|----------|
| Patents | `GET/POST /api/patents` | Proje listele/oluştur |
| Patents | `GET/DELETE /api/patents/{id}` | Proje detay/sil |
| Claims | `GET/POST /api/patents/{id}/claims` | Claim listele/oluştur |
| Claims | `PATCH /api/patents/{id}/claims/{cid}/text` | Claim metni güncelle |
| Claims | `DELETE /api/patents/{id}/claims/{cid}` | Claim sil |
| Elements | `GET/POST /api/patents/{id}/elements` | Element listele/oluştur |
| Elements | `PATCH /api/patents/{id}/elements/{eid}` | Element güncelle |
| Elements | `DELETE /api/patents/{id}/elements/{eid}` | Element sil |
| Claim-Elements | `GET/POST .../claims/{cid}/elements` | Element bağla/listele |
| Claim-Elements | `PATCH .../claims/{cid}/elements/{eid}` | Sıralama değiştir |
| Claim-Elements | `DELETE .../claims/{cid}/elements/{eid}` | Bağlantıyı kaldır |
| RAG | `GET /api/rag/data-status` | Veri yükleme durumu |
| RAG | `POST /api/rag/upload-excel` | Excel yükle (embedding oluştur) |
| RAG | `POST /api/rag/generate-definition` | AI tanım önerisi |
| RAG | `POST /api/rag/set-llm-url` | Colab LLM URL ayarla |
| Pipeline | `POST /api/pipeline/extract-elements` | BBF+Report'tan element çıkar |
| Pipeline | `GET /api/pipeline/extract-elements-status` | Çıkarma durumu |

---

## Kullanım Kılavuzu

### 1. Proje Oluşturma
- Ana sayfada **+ New Project** tıklayın
- Proje adı ve patent sahibi girin

### 2. Veri Yükleme (Excel)
- **Upload Data** butonuna tıklayın
- `all_definitions_translated.xlsx` veya `TUSAŞ_Tarifname_Translated.xlsx` dosyasını yükleyin
- Embedding'ler oluşturulur (ilk seferde birkaç dakika, sonraki yüklemeler cache'den anlık)

### 3. BBF/Report'tan Element Çıkarma
- **⚡ Extract** butonuna tıklayın
- BBF dokümanı (.docx/.pdf/.txt) ve Report dokümanı yükleyin
- Pipeline otomatik olarak unsurları çıkarır ve element havuzuna ekler

### 4. Claim Yönetimi
- **+ Add Claim** ile yeni talep oluşturun (independent/dependent, apparatus/method)
- **+ Add Elements** ile element havuzundan claim'e unsur bağlayın
- Element'leri **sürükle-bırak** (drag & drop) ile claim'e ekleyin
- Element tree'de **∧∨** butonlarıyla sıralama değiştirin

### 5. Element Tanımları
- Element'e tıklayın → **Element Definition** modal açılır
- **⚡ AI Suggest Definition** ile RAG + LLM tabanlı otomatik tanım önerisi alın
- Tanımı düzenleyip **💾 Save & Close** ile kaydedin

### 6. AI Tanım Önerisi (Detay)

Tanım önerisi 3 aşamada çalışır:
1. **RAG Fragment**: FAISS vektör araması ile benzer patent tanımlarından genel teknik tanım
2. **BBF Fragment**: Yüklenen BBF dokümanından unsura özel konumsal/ilişkisel bilgi
3. **Final Definition**: İki fragment'ın birleştirilmiş hali

### 7. Colab LLM Bağlantısı (Opsiyonel)

Daha kaliteli tanımlar için Google Colab'da Mistral-7B çalıştırabilirsiniz:

1. Colab'da yeni notebook açın (Runtime → T4 GPU)
2. LLM sunucu kodunu çalıştırın (ngrok ile dışarı açılır)
3. **⚙ Settings** → LLM API URL'ye ngrok URL'sini yapıştırın

LLM bağlı değilse akıllı fallback çalışır (FAISS'ten en iyi tanım + BBF'ten ilgili cümleler).

### 8. Draft Oluşturma
- **📋 Assemble with Report**: Tüm element tanımlarını rapor formatında birleştirir
- **⚡ Go to AI Draft**: Claim yapısıyla birlikte taslak oluşturur
- **📝 Draft Composer**: Tam patent taslağı oluşturma sayfası

---

## Dizin Yapısı

```
paten_draft_backend/
├── Dockerfile                    # App container tanımı
├── docker-compose.yml            # PostgreSQL + App orchestration
├── requirements.txt              # Python bağımlılıkları
├── alembic.ini                   # Migration konfigürasyonu
├── alembic/                      # Veritabanı migration'ları
│   └── versions/
├── app/
│   ├── main.py                   # FastAPI uygulama giriş noktası
│   ├── config.py                 # Uygulama ayarları
│   ├── database.py               # SQLAlchemy bağlantısı
│   ├── rag_engine.py             # FAISS RAG + LLM tanım üretimi
│   ├── bbf_report_unsur_pipeline.py  # BBF/Report element çıkarma
│   ├── models/                   # SQLAlchemy ORM modelleri
│   ├── routes/                   # API endpoint'leri
│   ├── schemas/                  # Pydantic şemaları
│   ├── services/                 # İş mantığı servisleri
│   └── ingestion/                # Veri yükleme modülleri
├── static/
│   ├── home.html                 # Ana sayfa (SPA)
│   ├── cs/style.css              # Dark theme CSS
│   └── jss/app.js                # Frontend JavaScript
├── scripts/
│   └── start.sh                  # Docker başlangıç scripti
└── data/                         # Excel dosyaları + FAISS cache
    └── .cache/
```

---

## Ortam Değişkenleri

| Değişken | Varsayılan | Açıklama |
|----------|-----------|----------|
| `DATABASE_URL` | `postgresql+psycopg://patent_user:patent_pass_password123@localhost:5433/patent_db` | Veritabanı bağlantı URL'si |
| `APP_HOST` | `0.0.0.0` | Sunucu host |
| `APP_PORT` | `8000` | Sunucu port |

---

## Sorun Giderme

| Sorun | Çözüm |
|-------|-------|
| Port 5433 kullanımda | `docker compose down -v` ile temizleyin |
| Port 8000 kullanımda | Başka sunucuyu durdurun veya `.env`'de `APP_PORT` değiştirin |
| "Data not loaded" | Upload Data ile Excel yükleyin veya `data/` klasörüne kopyalayın |
| BBF fragment boş | Extract ile BBF dokümanını tekrar yükleyin |
| LLM kalitesi düşük | Colab'da Mistral-7B bağlayın (Settings → LLM API URL) |
