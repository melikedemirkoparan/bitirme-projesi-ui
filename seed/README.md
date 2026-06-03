# Seed veritabanı — `patent_db_seed.sql`

Bu klasör, projenin **demo verisini** içeren bir PostgreSQL dump'ı barındırır.
Amaç: depoyu sıfırdan klonlayan birinin, ekstra hiçbir veri girmeden `docker compose up`
deyince **uygulamayı dolu bir veritabanıyla** çalıştırabilmesidir.

## İçerik (dump alındığı andaki durum)

| Tablo | Satır |
|-------|-------|
| patent | 5 |
| research_report | 5 (element-patent analizleriyle birlikte) |
| invention_disclosure | 5 |
| element | 119 |
| claim / claim_element | mevcut |
| alembic_version | `23fbf1ca0df3` (şemanın güncel hali) |

> **Not:** `app_setting` tablosu **bilerek boş** bırakıldı. Böylece uygulama varsayılan
> olarak **lokal Ollama**'ya (`http://host.docker.internal:11434`) bağlanır. Önceki
> ortamda kayıtlı olan uzaktan (ngrok) LLM URL'i, artık geçersiz olduğu için seed'e
> dahil edilmedi.

## Nasıl yükleniyor?

`docker-compose.yml` içinde bu dosya, db servisine şu şekilde bağlanır:

```yaml
volumes:
  - ./seed/patent_db_seed.sql:/docker-entrypoint-initdb.d/01_seed.sql:ro
```

PostgreSQL imajı, `/docker-entrypoint-initdb.d/` altındaki `.sql` dosyalarını
**yalnızca veri volume'u boşken (ilk başlatmada)** otomatik çalıştırır. Yani:

- **İlk `docker compose up`** → boş `pgdata` volume'u → seed otomatik yüklenir → veri hazır.
- **Sonraki açılışlar** → volume dolu olduğundan seed TEKRAR yüklenmez (mevcut veri korunur).

Uygulamanın `start.sh`'i ardından `alembic upgrade head` çalıştırır; seed zaten güncel
şemada (head) olduğu için migration no-op olur, çakışma olmaz.

## Veriyi sıfırlamak / yeniden yüklemek

Seed'i yeniden yüklemek istersen (DİKKAT: mevcut DB verisini siler):

```bash
docker compose down
docker volume rm bitirme-projesi-ui_pgdata
docker compose up --build
```

## Seed'i güncellemek (yeni dump almak)

Çalışan db'den güncel bir dump almak için:

```bash
docker compose exec -T db pg_dump -U patent_user -d patent_db \
  --no-owner --no-privileges --inserts --exclude-table-data=public.app_setting \
  > seed/patent_db_seed.sql
```

## Veritabanı erişim bilgileri (demo)

| Alan | Değer |
|------|-------|
| Host (host'tan) | `localhost:5433` |
| Host (container içinden) | `db:5432` |
| Kullanıcı | `patent_user` |
| Şifre | `patent_pass_password123` |
| Veritabanı | `patent_db` |
