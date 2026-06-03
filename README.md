# Patent Drafting Tool

Patent taslaklarının yapılandırılmış biçimde hazırlanması için geliştirilen, çevrimdışı
çalışabilen bir uygulama. Backend **FastAPI**, veritabanı **PostgreSQL**, yapay zekâ
katmanı yerel veya uzaktan bir **LLM** (Ollama / OpenAI-uyumlu) ile çalışır. Tümü
**Docker** ile ayağa kalkar.

## Hızlı Başlangıç (sıfırdan, veriyle birlikte)

### Gereksinimler
- **Docker Desktop** (Compose dahil)
- **Ollama** (yerel LLM için) — host makinede çalışır olmalı:
  ```bash
  ollama serve            # arka planda çalışıyorsa gerek yok
  ollama pull qwen2.5:7b  # uygulamanın varsayılan modeli
  ```

### Çalıştırma
```bash
git clone <bu-repo>
cd bitirme-projesi-ui
docker compose up --build
```

Bu kadar. Açılışta:
- PostgreSQL ayağa kalkar ve **`seed/patent_db_seed.sql`** otomatik yüklenir →
  **5 patent + araştırma raporları + elementler hazır gelir** (bkz. `seed/README.md`).
- App migration'ları çalıştırır (seed zaten güncel şemada olduğu için no-op) ve sunucuyu başlatır.

Uygulama: **http://localhost:8000**

| Servis | Port |
|--------|------|
| App (FastAPI) | `8000` |
| PostgreSQL | `5433` (host) → `5432` (container) |

## LLM Yapılandırması

Uygulama iki şekilde LLM'e bağlanabilir; protokol base URL'den otomatik seçilir
(`/v1` ile biterse OpenAI-uyumlu, değilse Ollama-native).

### 1) Yerel Ollama (varsayılan, önerilen)
`docker-compose.yml` içinde:
```yaml
OLLAMA_BASE_URL: "http://host.docker.internal:11434"
```
Host makinede `ollama serve` + `qwen2.5:7b` yeterli. Ağdan bağımsız, kararlı.

### 2) Uzaktan LLM (ngrok / Colab vb.)
Arayüzden veya API'den uzak bir URL ayarlanabilir; DB'de saklanır ve sonraki açılışlarda korunur:
```bash
curl -X POST http://localhost:8000/api/rag/set-llm-url \
  -H "Content-Type: application/json" \
  -d '{"url": "https://<sizin-tunneliniz>.ngrok-free.app/v1"}'
# Temizleyip yerele dönmek için: {"url": ""}
```
> Uyarı: Bazı kurumsal/üniversite ağları ngrok'u engeller. Engelli ağda yerel Ollama kullanın.

## Veritabanı

Demo verisi `seed/` klasöründe versiyonlanır ve ilk açılışta otomatik yüklenir.
Ayrıntılar, sıfırlama ve yeni dump alma adımları için: **[`seed/README.md`](seed/README.md)**.

Erişim (demo): kullanıcı `patent_user` / şifre `patent_pass_password123` / db `patent_db`.

## Notlar
- `*.sh` betikleri LF satır sonuyla zorlanır (`.gitattributes`); Windows checkout'ta
  CRLF kaynaklı container başlatma hatası bu sayede önlenir.
- Daha ayrıntılı modül/şema dokümanları `docs/` altındadır.
