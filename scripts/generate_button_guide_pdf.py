"""
Generate a Turkish user guide PDF that explains every button in the
Patent Drafting Tool UI, screen by screen.

Run from the repo root:
    python scripts/generate_button_guide_pdf.py

Output: docs/Patent_Drafting_Tool_Button_Guide.pdf
"""

from pathlib import Path

from fpdf import FPDF


FONT_DIR = Path("C:/Windows/Fonts")
OUTPUT = Path(__file__).resolve().parent.parent / "docs" / "Patent_Drafting_Tool_Button_Guide.pdf"


class Guide(FPDF):
    def header(self):
        if self.page_no() == 1:
            return
        self.set_font("Arial", "", 9)
        self.set_text_color(120, 120, 120)
        self.cell(0, 6, "Patent Drafting Tool — Buton Rehberi", new_x="LMARGIN", new_y="NEXT", align="R")
        self.set_text_color(0, 0, 0)
        self.ln(2)

    def footer(self):
        self.set_y(-14)
        self.set_font("Arial", "", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 6, f"Sayfa {self.page_no()}", align="C")
        self.set_text_color(0, 0, 0)


pdf = Guide()
pdf.add_font("Arial", "", str(FONT_DIR / "arial.ttf"))
pdf.add_font("Arial", "B", str(FONT_DIR / "arialbd.ttf"))
pdf.add_font("Arial", "I", str(FONT_DIR / "ariali.ttf"))
pdf.set_auto_page_break(auto=True, margin=18)
pdf.set_margins(left=18, top=18, right=18)


def reset_x():
    pdf.set_x(pdf.l_margin)


def title(t):
    pdf.set_font("Arial", "B", 22)
    reset_x()
    pdf.cell(0, 14, t, new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(2)


def subtitle(t):
    pdf.set_font("Arial", "", 12)
    pdf.set_text_color(90, 90, 90)
    reset_x()
    pdf.cell(0, 8, t, new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)


def h1(t):
    if pdf.get_y() > 240:
        pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.set_fill_color(30, 60, 130)
    pdf.set_text_color(255, 255, 255)
    reset_x()
    pdf.cell(0, 9, "  " + t, new_x="LMARGIN", new_y="NEXT", fill=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(3)


def h2(t):
    if pdf.get_y() > 250:
        pdf.add_page()
    pdf.set_font("Arial", "B", 12)
    pdf.set_text_color(30, 60, 130)
    reset_x()
    pdf.cell(0, 7, t, new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(1)


def p(t):
    reset_x()
    pdf.set_font("Arial", "", 10)
    pdf.multi_cell(0, 5.5, t)
    pdf.ln(1)


def kv(label, body):
    """Bold label inline + regular body on same paragraph."""
    if pdf.get_y() > 265:
        pdf.add_page()
    reset_x()
    pdf.set_font("Arial", "B", 10)
    pdf.write(5.5, label + " ")
    pdf.set_font("Arial", "", 10)
    pdf.write(5.5, body)
    pdf.ln(7)


def button_block(name, what, how, note=None):
    """Render a button entry: name (bold), Ne işe yarar, Nasıl kullanılır, Not."""
    if pdf.get_y() > 240:
        pdf.add_page()
    pdf.set_font("Arial", "B", 11)
    pdf.set_text_color(20, 20, 20)
    reset_x()
    pdf.cell(0, 6, "• " + name, new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.set_x(pdf.l_margin + 4)
    pdf.set_font("Arial", "B", 9)
    pdf.write(5, "Ne işe yarar: ")
    pdf.set_font("Arial", "", 9)
    pdf.write(5, what)
    pdf.ln(5)
    pdf.set_x(pdf.l_margin + 4)
    pdf.set_font("Arial", "B", 9)
    pdf.write(5, "Nasıl kullanılır: ")
    pdf.set_font("Arial", "", 9)
    pdf.write(5, how)
    pdf.ln(5)
    if note:
        pdf.set_x(pdf.l_margin + 4)
        pdf.set_font("Arial", "I", 9)
        pdf.set_text_color(120, 80, 0)
        pdf.write(5, "Not: " + note)
        pdf.set_text_color(0, 0, 0)
        pdf.ln(5)
    pdf.ln(2)


# ─────────────────────────────────────────────────────────────────
# COVER
# ─────────────────────────────────────────────────────────────────
pdf.add_page()
pdf.ln(40)
title("Patent Drafting Tool")
title("Buton Rehberi")
pdf.ln(6)
subtitle("Arayüzdeki her butonun ne işe yaradığını ve")
subtitle("nasıl kullanılacağını anlatan kullanıcı kılavuzu")
pdf.ln(20)
pdf.set_font("Arial", "", 11)
pdf.set_text_color(80, 80, 80)
reset_x()
pdf.multi_cell(
    0,
    6,
    "Bu rehber, Patent Drafting Tool arayüzünün ana ekranlarındaki "
    "ve modal pencerelerindeki tüm butonları tek tek açıklar. Her "
    "buton için ne işe yaradığı, nasıl kullanıldığı ve dikkat "
    "edilmesi gereken durumlar verilmiştir.",
    align="C",
)
pdf.set_text_color(0, 0, 0)
pdf.ln(40)
pdf.set_font("Arial", "I", 10)
pdf.set_text_color(120, 120, 120)
reset_x()
pdf.cell(0, 6, "Sürüm: feature/inventor-qa-section", align="C", new_x="LMARGIN", new_y="NEXT")
pdf.set_text_color(0, 0, 0)


# ─────────────────────────────────────────────────────────────────
# 1) ANA SAYFA — DASHBOARD
# ─────────────────────────────────────────────────────────────────
pdf.add_page()
h1("1. Ana Sayfa (Dashboard)")
p(
    "Uygulamayı açtığınızda gördüğünüz ilk ekran. Sol tarafta proje "
    "(workspace) listesi, sağ tarafta ise uygulamanın tanıtım panosu yer alır. "
    "Üstte ortak bir navbar bulunur."
)

h2("Üst Navbar (Ana Sayfada)")
button_block(
    "PATENT DRAFTING TOOL (logo + başlık)",
    "Uygulamanın markasını gösterir. Tıklanabilir bir aksiyonu yoktur.",
    "Sadece görsel — başka bir sekmedeyseniz ana sayfaya dönmek için "
    "Back to Home butonunu kullanın.",
)
button_block(
    "Data Loaded / No Data (durum rozeti)",
    "Excel verisinin (RAG vektör veritabanı) yüklü olup olmadığını "
    "gösterir. Yeşil 'Data Loaded' = embedding'ler hazır; gri 'No Data' "
    "= henüz Excel yüklenmedi.",
    "Sadece bilgi amaçlıdır. AI Suggest Definition gibi özellikler için "
    "rozetin yeşil olması gerekir.",
)
button_block(
    "Back to Home",
    "Açık olan workspace'ten çıkıp ana sayfaya (proje listesine) döner.",
    "Workspace'teyken bu butona tıklayın; seçili proje sıfırlanır ve "
    "dashboard ekranı gelir.",
)
button_block(
    "Upload Data",
    "Excel veri yükleme modalını açar (Upload Excel Data). Aynı işlevi "
    "soldaki '[Klasör]Upload Excel Data' butonu da görür.",
    "Tıklayın → Çıkan modaldan .xlsx dosyasını seçin → embedding'ler "
    "arka planda oluşturulur.",
)

h2("Sol Panel — Projects")
button_block(
    "[Klasör]Upload Excel Data",
    "Sol panelden Excel yükleme modalını açar. Üst navbardaki Upload "
    "Data ile aynı şeyi yapar; kolaylık için iki yerde de bulunur.",
    "Tıklayın → modal açılır → Excel dosyasını seçip yükleyin.",
)
button_block(
    "+ New Project",
    "Yeni bir patent projesi oluşturmak için 'New Project' modalını açar.",
    "Tıklayın → Project Name (proje adı) ve Patent Owner (sahibi) "
    "alanlarını doldurun → Create butonuna basın. Proje listesine "
    "eklenir.",
)

h2("Proje Kartı (her proje için)")
p(
    "Listedeki her projenin altında üç buton bulunur. Kartın kendisine "
    "tıklamak da projeyi açar."
)
button_block(
    "📋 Inputs",
    "Projeye ait Patent Inputs modalını açar. Şu anda bu modalın içinde "
    "'Buluşçu ile Yazışmalar (Inventor_QA)' kartı vardır: Q&A metnini "
    "yazabilir ve doküman ekleyebilirsiniz.",
    "Projenin yanındaki Inputs butonuna tıklayın → metin yazıp Save "
    "Q&A Text ile kaydedin veya Choose document ile dosya seçip Upload "
    "ile yükleyin. Mevcut dokümanlar listelenir, indirilebilir veya "
    "silinebilir.",
)
button_block(
    "✎ Edit",
    "Projenin adını ve patent sahibini düzenlemek için Edit Project "
    "modalını açar.",
    "Edit'e tıklayın → Project Name ve/veya Patent Owner alanlarını "
    "değiştirin → Save ile kaydedin.",
)
button_block(
    "Open",
    "Projeyi açar ve workspace ekranına (Claims, Elements, Draft Editor) "
    "geçer. Karta herhangi bir yerine tıklamak da aynı işi yapar.",
    "Tıklayın → seçili proje workspace'te yüklenir.",
)


# ─────────────────────────────────────────────────────────────────
# 2) WORKSPACE — ÜST NAVBAR
# ─────────────────────────────────────────────────────────────────
pdf.add_page()
h1("2. Workspace — Üst Navbar")
p(
    "Bir proje açıldığında üstteki navbar, projeyle ilgili bilgileri "
    "gösterir ve hızlı aksiyonlar sunar."
)
button_block(
    "Proje Adı (deneme1)",
    "Açık olan projenin adını gösterir. Yanında küçük gri yazıyla "
    "proje sahibi (— melike) görünür.",
    "Sadece bilgi amaçlıdır; düzenlemek için yanındaki ✎ Rename "
    "butonunu kullanın.",
)
button_block(
    "✎ Rename",
    "Açık projenin adını/sahibini değiştirmek için Edit Project modalını "
    "açar (proje listesindeki ✎ Edit ile aynı modal).",
    "Tıklayın → yeni adı ve/veya owner'ı yazın → Save'e basın. Navbar "
    "ve proje listesi otomatik güncellenir.",
)
button_block(
    "← Back to Home",
    "Workspace'ten çıkıp ana sayfaya (proje listesi) döner.",
    "Tıklayın; üzerinde çalıştığınız değişiklikler kaydedildiyse "
    "korunur.",
)
button_block(
    "↑ Upload Data",
    "Excel veri yükleme modalını açar (Workspace içinden de Excel "
    "yüklenebilir).",
    "Tıklayın → Excel dosyasını seçip yükleyin.",
)


# ─────────────────────────────────────────────────────────────────
# 3) WORKSPACE — SOL PANEL: CLAIMS & ELEMENTS
# ─────────────────────────────────────────────────────────────────
h1("3. Workspace — Sol Panel: Claims & Elements")
p(
    "Patentin tüm istemlerini (claims) ve her istemin element ağacını "
    "yönettiğiniz alandır. Üstte 'Claim Structures' başlığı yer alır."
)

button_block(
    "+ Add Claim",
    "Yeni bir istem (claim) eklemek için 'Add Claim' modalını açar.",
    "Tıklayın → Dependency Type (Independent/Dependent) ve Category "
    "(Apparatus/Method) seçin; Dependent seçtiyseniz Parent Claim "
    "belirleyin → Add Claim ile oluşturun.",
)

h2("Her bir Claim kartında")
button_block(
    "Claim Numarası (Claim 1, Claim 2, ...)",
    "İstemi tanımlayan başlık. Yanında durum rozeti (Ready / "
    "Incomplete) bulunabilir: 'Ready' = bağlı tüm element'lerin "
    "tanımı tamam; 'Incomplete' = en az birinin tanımı eksik.",
    "Karta tıklayarak istemi seçin; sağdaki Claim Draft Editor o "
    "iste min metnini gösterir.",
)
button_block(
    "∨ / › (genişlet/daralt)",
    "Claim kartının altındaki ELEMENT TREE bölümünü açar veya kapatır.",
    "Ok simgesine tıklayın; element ağacı görünür/gizlenir.",
)
button_block(
    "+ Add Elements",
    "Patent havuzundaki bir element'i bu istem'e bağlamak için Link "
    "Element modalını açar.",
    "Tıklayın → açılan modaldan element seçin → Link ile bağlayın. "
    "Element ağacında yeni satır olarak görünür.",
)
button_block(
    "🗑 (claim sil)",
    "Claim kartının sağ üstündeki çöp ikonu; bu istemi siler.",
    "Tıklayın → onay kutusu çıkar → Delete'e basarsanız claim silinir. "
    "Geri alınamaz.",
    note="Silmek istemediğiniz bir istem için tıklamadığınızdan emin olun.",
)

h2("Element Tree (her claim altında)")
button_block(
    "∧ / ∨ (sırayı yukarı/aşağı al)",
    "Seçili element'in claim içindeki sırasını bir yukarı veya bir "
    "aşağı taşır.",
    "Önce element'in üzerine tıklayarak SELECTED rozetini almasını "
    "sağlayın → ∧ veya ∨ ile sırayı değiştirin.",
)
button_block(
    "↻ (yenile)",
    "Bu claim'in element ağacını backend'den yeniden yükler.",
    "Sıralama veya bağlantılarda görünmeyen bir değişiklik olursa "
    "tıklayın.",
)
button_block(
    "Search elements (arama kutusu)",
    "Element ağacını isimle filtreler.",
    "Aramak istediğiniz kelimeyi yazın → eşleşmeyen element'ler gizlenir.",
)
button_block(
    "Element satırı",
    "Element'in adını gösterir. Sağda durum ikonu (✓ tanım tamam / "
    "⚠ tanım eksik) vardır.",
    "Tıklayın → element seçilir ve Element Definition modalı açılır.",
)
button_block(
    "🗑 (element bağlantısını çöz)",
    "Bu element'i bu claim'den ayırır (element silinmez, sadece bağ kalkar).",
    "Tıklayın; element claim'in ağacından çıkar ama patent havuzunda "
    "kalmaya devam eder.",
)


# ─────────────────────────────────────────────────────────────────
# 4) WORKSPACE — ORTA PANEL: LLM EXTRACTION QUEUE
# ─────────────────────────────────────────────────────────────────
pdf.add_page()
h1("4. Workspace — Orta Panel: LLM Extraction Queue")
p(
    "Patent havuzundaki tüm element'lerin listelendiği panel. "
    "Buradaki element'ler claim'lere bağlanabilir ve tanımları "
    "düzenlenebilir."
)

button_block(
    "⚡ Extract",
    "BBF + Report dökümanlarından otomatik element çıkarmak için "
    "'Extract Elements from BBF + Report' modalını açar. Bu modalda "
    "ek olarak Buluşçu ile Yazışmalar (Inventor_QA) dokümanı da "
    "yüklenebilir.",
    "Tıklayın → BBF, Report (zorunlu) ve isterseniz Inventor_QA "
    "dosyalarını seçin → ⚡ Extract Elements butonuna basın. "
    "İşlem bitince çıkarılan element'ler havuza eklenir.",
)
button_block(
    "+ Add Element",
    "Boş bir Element Definition modalı açar; havuza manuel olarak "
    "yeni element eklemenizi sağlar.",
    "Tıklayın → Element Name (zorunlu), Reference Number ve Definition "
    "alanlarını doldurun → 💾 Save & Close ile kaydedin.",
)

h2("Element listesindeki her satırda")
button_block(
    "DRAG (sürükleme tutamağı)",
    "Element'i sürükleyip claim kartlarının üzerine bırakarak hızlıca "
    "bağlama imkânı verir.",
    "DRAG yazısının üzerine basılı tutun → istediğiniz claim kartının "
    "üzerine bırakın → element o claim'e link'lenir.",
)
button_block(
    "Edit",
    "Element Definition modalını düzenleme modunda açar.",
    "Tıklayın → element adı, reference number, definition, AI suggest, "
    "linked claims listesi gibi tüm alanlara erişebilirsiniz.",
)
button_block(
    "🗑 (element sil)",
    "Element'i havuzdan tamamen siler. Bağlı olduğu tüm claim'lerden "
    "de düşer.",
    "Onay verdikten sonra silinir; geri alınamaz.",
    note="Element kalıcı olarak silinir; sadece bağlantıyı çözmek "
    "istiyorsanız claim altındaki 🗑 (unlink) butonunu kullanın.",
)


# ─────────────────────────────────────────────────────────────────
# 5) WORKSPACE — SAĞ PANEL: CLAIM DRAFT EDITOR
# ─────────────────────────────────────────────────────────────────
pdf.add_page()
h1("5. Workspace — Sağ Panel: Claim Draft Editor")
p(
    "Seçili istem'in (claim) draft (taslak) metnini yazıp düzenlediğiniz "
    "alan. Sol panelden bir claim seçtiğinizde buradaki textarea aktifleşir."
)

button_block(
    "⚙ Settings",
    "Project Settings modalını açar; Invention Context, BBF Text ve "
    "LLM API URL alanlarını içerir.",
    "Tıklayın → Invention Context (örn: 'Antenna assembly for an "
    "aircraft'), BBF Text (BBF'in metin içeriği) ve isteğe bağlı "
    "Colab ngrok LLM URL'sini girin → Save'e basın.",
)
button_block(
    "📋 Assemble with Report",
    "Tüm tanımlanmış element'lerden bir 'ELEMENT DEFINITIONS REPORT' "
    "üretip draft alanına yazar.",
    "Tıklayın → element listesinden tanımı dolu olanlar bir araya "
    "getirilip düzenli bir rapor olarak draft textarea'sına yazılır.",
    note="Mevcut draft metninin üzerine yazar; önce kaydetmek "
    "istiyorsanız Save'e basın.",
)
button_block(
    "💾 Save",
    "Seçili claim'in draft metnini PostgreSQL veritabanına kaydeder. "
    "Sonra kısa bir '✓ Saved' geri bildirimi gösterir.",
    "Önce sol panelden bir claim seçin → metni düzenleyin → Save'e "
    "basın. Buton kısaca 'Saving…' → '✓ Saved' olur.",
    note="Hiçbir claim seçili değilse uyarı verir.",
)
button_block(
    "✈ Go to AI Draft",
    "Tüm claim'lerin yapılandırılmış metnini Draft Composer ekranına "
    "aktarıp AI ile tam patent draft'ı üretmek için yönlendirir.",
    "Tıklayın → composer ekranına geçersiniz; oradan ⚡ Generate Draft "
    "ile AI üretimi başlatabilirsiniz.",
)
button_block(
    "📝 Draft Composer",
    "Doğrudan Draft Composer (AI Draft Workspace) sayfasına geçiş yapar.",
    "Tıklayın → Structured Claims paneline mevcut claim'leri girip "
    "Draft Output panelinde AI çıktısı üretebilirsiniz.",
)


# ─────────────────────────────────────────────────────────────────
# 6) MODAL — UPLOAD EXCEL DATA
# ─────────────────────────────────────────────────────────────────
pdf.add_page()
h1("6. Modal — Upload Excel Data")
p(
    "RAG (Retrieval-Augmented Generation) için kullanılan vektör "
    "veritabanını oluşturan Excel dosyasını yükleme ekranı."
)
button_block(
    "Click to select Excel file (.xlsx)",
    "Bilgisayarınızdan bir .xlsx dosyası seçmek için sistem dosya "
    "tarayıcısını açar.",
    "Tıklayın → çevirisi yapılmış Excel dosyasını seçin. Yükleme ve "
    "embedding oluşturma otomatik başlar; durumu altta görürsünüz "
    "(örn: '✓ Loaded 9133 docs. FAISS index ready.').",
    note="Embedding oluşturma birkaç dakika sürebilir; modalı kapatsanız "
    "bile arka planda tamamlanır.",
)
button_block(
    "× / Close",
    "Modalı kapatır.",
    "Yükleme bittiyse veya devam ediyorsa kapatabilirsiniz; arka plan "
    "işlemi etkilenmez.",
)


# ─────────────────────────────────────────────────────────────────
# 7) MODAL — EXTRACT ELEMENTS FROM BBF + REPORT
# ─────────────────────────────────────────────────────────────────
h1("7. Modal — Extract Elements from BBF + Report")
p(
    "BBF (Buluş Bildirim Formu) ve Research Report dökümanlarını "
    "yükleyerek otomatik element çıkarımı yapan modal. Ayrıca "
    "isteğe bağlı 'Buluşçu ile Yazışmalar (Inventor_QA)' dosyası da "
    "yükleyebilirsiniz."
)
button_block(
    "BBF Document — Click to select BBF file",
    "BBF (Buluş Bildirim Formu) dökümanını seçmek için kullanılır. "
    "Pipeline bu dosyadan unsurları (elements) çıkarır.",
    "Tıklayın → .docx, .pdf veya .txt formatında BBF dosyanızı seçin.",
)
button_block(
    "Report Document — Click to select Report file",
    "Araştırma raporu (Research Report) dökümanını seçer; pipeline "
    "BBF ile birlikte bu dosyayı kullanarak element ve tanımları "
    "çıkarır.",
    "Tıklayın → .docx, .pdf veya .txt formatında raporunuzu seçin.",
)
button_block(
    "Buluşçu ile Yazışmalar (Inventor_QA) — Click to select Inventor_QA file",
    "Buluşçu ile yapılan yazışma/açıklama dökümanlarını yükler. "
    "Bu alan opsiyoneldir. Dosya seçer seçmez otomatik olarak ilgili "
    "patent'in inventor_qa kayıtlarına yüklenir ve modalı kapatsanız "
    "dahi listede kalır.",
    "Tıklayın → .pdf, .docx, .txt vb. dosyanızı seçin. Yükleme tamam "
    "olunca '✓ Uploaded ...' mesajı görünür ve mevcut dökümanlar "
    "listede listelenir.",
    note="Bu dosya pipeline'a verilmez; sadece projenin Inventor_QA "
    "dökümanlarına eklenir. Pipeline yalnızca BBF + Report ile "
    "çalışır.",
)
button_block(
    "Cancel",
    "Modalı kapatır; çalışmaya başlamış pipeline'ı durdurmaz.",
    "Tıklayın; modal kapanır.",
)
button_block(
    "⚡ Extract Elements",
    "Seçili BBF + Report dökümanlarıyla extraction pipeline'ını "
    "çalıştırır. Pipeline bittiğinde çıkarılan element'ler havuza "
    "(LLM Extraction Queue) otomatik eklenir.",
    "Önce BBF ve Report dosyalarını seçin → tıklayın → 'Running "
    "pipeline…' mesajını görürsünüz → tamamlanınca '✓ Extracted N "
    "elements!' yazısı çıkar.",
    note="BBF ve Report her ikisi de zorunludur; biri eksikse uyarı verir.",
)


# ─────────────────────────────────────────────────────────────────
# 8) MODAL — PROJECT SETTINGS
# ─────────────────────────────────────────────────────────────────
pdf.add_page()
h1("8. Modal — Project Settings")
p(
    "AI üretiminde kullanılacak invention context, BBF text ve LLM "
    "ayarlarını giriş alanı."
)
button_block(
    "Invention Context",
    "Patent için kısa bağlam metni; AI promptlarına context olarak verilir "
    "(örn: 'Antenna assembly for an aircraft').",
    "Buluşunuzu en kısa şekilde tarif eden tek satırlık bir cümle yazın.",
)
button_block(
    "BBF Text",
    "BBF (Buluş Bildirim Formu) içeriğinin tam metni. AI Suggest "
    "Definition ve diğer üretim modülleri bu metni kullanır.",
    "BBF dökümanından kopyaladığınız metni textarea'ya yapıştırın "
    "(ya da Extract Elements ile pipeline çalıştırırsanız sistem "
    "otomatik doldurur).",
)
button_block(
    "LLM API URL (Colab ngrok)",
    "Colab'da çalışan Mistral-7B (veya benzeri) LLM'in ngrok adresini "
    "girer. Boş bırakılırsa heuristik fallback kullanılır.",
    "Colab notebook'unuzu çalıştırın → ngrok URL'sini kopyalayın → "
    "buraya yapıştırın.",
    note="URL yanlışsa veya ngrok düşmüşse AI suggest çalışmaz; "
    "boş bırakırsanız basit fallback devreye girer.",
)
button_block(
    "Cancel",
    "Modalı kaydetmeden kapatır.",
    "Tıklayın; girilen değerler kaybolur (henüz Save'lemediyseniz).",
)
button_block(
    "Save",
    "Girilen Invention Context, BBF Text ve LLM URL ayarlarını "
    "uygulamanın bellek/cache'ine kaydeder.",
    "Doldurduktan sonra Save'e basın → modal kapanır → ayarlar "
    "sonraki AI üretimlerinde kullanılır.",
)


# ─────────────────────────────────────────────────────────────────
# 9) HIZLI İŞ AKIŞI
# ─────────────────────────────────────────────────────────────────
pdf.add_page()
h1("9. Hızlı İş Akışı (Tipik Kullanım)")
p(
    "Aşağıdaki adımlar, sıfırdan bir patent draft'ı oluşturmak için "
    "izlemeniz gereken en kısa yolu özetler."
)

steps = [
    ("1. Excel verisini yükleyin",
     "Üst navbardaki 'Upload Data' veya sol panelden '[Klasör]Upload Excel "
     "Data' ile çevirisi yapılmış Excel dosyanızı yükleyin. 'Data "
     "Loaded' rozeti yeşile dönmeli."),
    ("2. Yeni proje oluşturun",
     "Sol paneldeki '+ New Project' ile Project Name ve Patent Owner "
     "alanlarını girip Create'e basın."),
    ("3. (İsteğe bağlı) Inventor_QA ekleyin",
     "Proje kartındaki '📋 Inputs' butonu ile Buluşçu ile Yazışmalar "
     "metnini yazın ve/veya doküman yükleyin."),
    ("4. Projeyi açın",
     "Proje kartına veya 'Open' butonuna tıklayın; workspace açılır."),
    ("5. Element'leri çıkarın",
     "Orta paneldeki '⚡ Extract' butonuyla BBF + Report (ve isterseniz "
     "Inventor_QA) dosyalarını yükleyip pipeline'ı çalıştırın. "
     "Çıkan element'ler havuza eklenir."),
    ("6. Claim'leri oluşturun",
     "Sol panelden '+ Add Claim' ile bir veya birden fazla istem "
     "ekleyin (independent / dependent + apparatus / method)."),
    ("7. Element'leri claim'lere bağlayın",
     "Her claim altındaki '+ Add Elements' veya orta paneldeki DRAG "
     "ile element'leri uygun claim'lere bağlayın."),
    ("8. Tanımları tamamlayın",
     "Element'lerin Edit modalını açıp Definition alanını doldurun. "
     "Gerekirse '⚡ AI Suggest Definition' ile öneri alın."),
    ("9. Draft yazın ve kaydedin",
     "Bir claim seçin → sağdaki textarea'ya draft metnini yazın → "
     "💾 Save'e basın. '📋 Assemble with Report' ile element "
     "tanımlarını otomatik raporlayabilirsiniz."),
    ("10. AI ile tam draft üretin",
     "'✈ Go to AI Draft' veya '📝 Draft Composer' ile composer "
     "ekranına geçin → '⚡ Generate Draft' ile AI çıktısı üretin."),
]

for h, body in steps:
    pdf.set_font("Arial", "B", 11)
    pdf.set_text_color(30, 60, 130)
    reset_x()
    pdf.cell(0, 6, h, new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", "", 10)
    reset_x()
    pdf.multi_cell(0, 5.5, body)
    pdf.ln(2)


OUTPUT.parent.mkdir(parents=True, exist_ok=True)
pdf.output(str(OUTPUT))
print(f"Wrote {OUTPUT}")
