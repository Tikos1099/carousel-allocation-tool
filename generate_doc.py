from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import Flowable

# ── Colour palette ──────────────────────────────────────────────────────────
BLUE_DARK  = colors.HexColor("#2C2C2C")   # Hub Performance dark charcoal
BLUE_MID   = colors.HexColor("#C8321A")   # Hub Performance brand red
BLUE_LIGHT = colors.HexColor("#FEF0EE")   # Hub Performance light tint
GREY_LIGHT = colors.HexColor("#F5F5F5")
GREY_MID   = colors.HexColor("#D0D0D0")
ORANGE     = colors.HexColor("#E87722")
WHITE      = colors.white
BLACK      = colors.HexColor("#1A1A1A")

PAGE_W, PAGE_H = A4
MARGIN = 2 * cm


# ── Custom flowable: coloured section title bar ──────────────────────────────
class SectionBar(Flowable):
    def __init__(self, text, width=PAGE_W - 2 * MARGIN, height=0.75 * cm):
        super().__init__()
        self.text   = text
        self.width  = width
        self.height = height

    def wrap(self, *args):
        return self.width, self.height + 0.25 * cm

    def draw(self):
        c = self.canv
        c.setFillColor(BLUE_DARK)
        c.rect(0, 0, self.width, self.height, fill=1, stroke=0)
        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(0.3 * cm, 0.18 * cm, self.text)


# ── Header / Footer ──────────────────────────────────────────────────────────
def on_cover(canvas, doc):
    """Page 1 — white & red cover matching Hub Performance brand."""
    RED_HP   = colors.HexColor("#C8321A")   # Hub Performance brand red
    DARK     = colors.HexColor("#1A1A1A")
    MID_GREY = colors.HexColor("#666666")
    LT_GREY  = colors.HexColor("#F4F4F4")

    canvas.saveState()

    # ── Full white background ──
    canvas.setFillColor(WHITE)
    canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    # ── Light grey top strip ──
    canvas.setFillColor(LT_GREY)
    canvas.rect(0, PAGE_H - 1.6 * cm, PAGE_W, 1.6 * cm, fill=1, stroke=0)

    # ── Hub Performance logo (centered, upper area) ──
    logo_w = 10 * cm
    logo_h = 3.3 * cm       # ~3:1 aspect ratio of the image
    logo_x = (PAGE_W - logo_w) / 2
    logo_y = PAGE_H * 0.60
    canvas.drawImage(
        "assets/logo.png", logo_x, logo_y,
        width=logo_w, height=logo_h, mask="auto"
    )

    # ── Red horizontal separator ──
    canvas.setStrokeColor(RED_HP)
    canvas.setLineWidth(2.5)
    canvas.line(2 * cm, PAGE_H * 0.555, PAGE_W - 2 * cm, PAGE_H * 0.555)

    # ── Main title ──
    canvas.setFillColor(DARK)
    canvas.setFont("Helvetica-Bold", 27)
    canvas.drawCentredString(PAGE_W / 2, PAGE_H * 0.49, "Carousel Allocation Tool")

    # ── Subtitle in red ──
    canvas.setFillColor(RED_HP)
    canvas.setFont("Helvetica", 15)
    canvas.drawCentredString(PAGE_W / 2, PAGE_H * 0.42, "Documentation Utilisateur")

    # ── Light separator ──
    canvas.setStrokeColor(colors.HexColor("#DDDDDD"))
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN * 2, PAGE_H * 0.385, PAGE_W - MARGIN * 2, PAGE_H * 0.385)

    # ── Version tag ──
    canvas.setFillColor(MID_GREY)
    canvas.setFont("Helvetica-Oblique", 10)
    canvas.drawCentredString(PAGE_W / 2, PAGE_H * 0.35, "Version 1.0  —  Mars 2026")

    # ── Red footer bar ──
    canvas.setFillColor(RED_HP)
    canvas.rect(0, 0, PAGE_W, 1.3 * cm, fill=1, stroke=0)
    canvas.setFillColor(WHITE)
    canvas.setFont("Helvetica-Bold", 8.5)
    canvas.drawString(MARGIN, 0.46 * cm, "Hub Performance")
    canvas.setFont("Helvetica", 7.5)
    canvas.drawRightString(PAGE_W - MARGIN, 0.46 * cm, "Confidentiel – Usage interne")

    canvas.restoreState()


def on_page(canvas, doc):
    canvas.saveState()
    # top bar
    canvas.setFillColor(BLUE_DARK)
    canvas.rect(0, PAGE_H - 1.1 * cm, PAGE_W, 1.1 * cm, fill=1, stroke=0)
    canvas.setFillColor(WHITE)
    canvas.setFont("Helvetica-Bold", 10)
    canvas.drawString(MARGIN, PAGE_H - 0.75 * cm, "Carousel Allocation Tool")
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(PAGE_W - MARGIN, PAGE_H - 0.75 * cm, "Documentation utilisateur")
    # bottom bar
    canvas.setFillColor(BLUE_MID)
    canvas.rect(0, 0, PAGE_W, 0.7 * cm, fill=1, stroke=0)
    canvas.setFillColor(WHITE)
    canvas.setFont("Helvetica", 7.5)
    canvas.drawCentredString(PAGE_W / 2, 0.22 * cm,
                             f"Page {doc.page}  |  Carousel Allocation Tool  |  Confidentiel – Usage interne")
    canvas.restoreState()


# ── Styles ───────────────────────────────────────────────────────────────────
base = getSampleStyleSheet()

S_TITLE = ParagraphStyle(
    "doc_title",
    fontName="Helvetica-Bold", fontSize=26,
    textColor=WHITE, alignment=TA_CENTER, spaceAfter=6
)
S_SUBTITLE = ParagraphStyle(
    "doc_subtitle",
    fontName="Helvetica", fontSize=13,
    textColor=BLUE_LIGHT, alignment=TA_CENTER, spaceAfter=4
)
S_BODY = ParagraphStyle(
    "body",
    fontName="Helvetica", fontSize=10,
    textColor=BLACK, leading=16, alignment=TA_JUSTIFY, spaceAfter=6
)
S_BODY_BOLD = ParagraphStyle(
    "body_bold",
    fontName="Helvetica-Bold", fontSize=10,
    textColor=BLACK, leading=16, spaceAfter=4
)
S_BULLET = ParagraphStyle(
    "bullet",
    fontName="Helvetica", fontSize=10,
    textColor=BLACK, leading=15, leftIndent=18,
    bulletIndent=6, spaceAfter=3
)
S_NOTE = ParagraphStyle(
    "note",
    fontName="Helvetica-Oblique", fontSize=9,
    textColor=colors.HexColor("#555555"), leading=13,
    leftIndent=10, spaceAfter=4
)
S_CODE = ParagraphStyle(
    "code",
    fontName="Courier", fontSize=9,
    textColor=BLUE_DARK, backColor=GREY_LIGHT,
    leftIndent=12, rightIndent=12, leading=14, spaceAfter=4
)
S_H2 = ParagraphStyle(
    "h2",
    fontName="Helvetica-Bold", fontSize=11,
    textColor=BLUE_MID, spaceBefore=10, spaceAfter=4
)
S_CAPTION = ParagraphStyle(
    "caption",
    fontName="Helvetica-Oblique", fontSize=8,
    textColor=colors.HexColor("#777777"), alignment=TA_CENTER, spaceAfter=6
)


def hr():
    return HRFlowable(width="100%", thickness=0.5, color=GREY_MID, spaceAfter=8, spaceBefore=4)


def sp(h=0.3):
    return Spacer(1, h * cm)


def bullet(text):
    return Paragraph(f"• {text}", S_BULLET)


S_CELL_HDR = ParagraphStyle(
    "cell_hdr",
    fontName="Helvetica-Bold", fontSize=9,
    textColor=WHITE, leading=13, alignment=TA_CENTER,
)
S_CELL = ParagraphStyle(
    "cell",
    fontName="Helvetica", fontSize=9,
    textColor=BLACK, leading=13,
)


def _wrap(value, is_header=False):
    """Wrap a plain string in a Paragraph so cells word-wrap correctly."""
    if isinstance(value, str):
        return Paragraph(value, S_CELL_HDR if is_header else S_CELL)
    return value


def col_table(data, col_widths=None, header_bg=BLUE_MID):
    """Generic styled table — all cells are wrapped in Paragraphs to prevent overflow."""
    if col_widths is None:
        n = len(data[0])
        col_widths = [(PAGE_W - 2 * MARGIN) / n] * n

    wrapped = []
    for row_idx, row in enumerate(data):
        wrapped.append([_wrap(cell, is_header=(row_idx == 0)) for cell in row])

    style = TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), header_bg),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [WHITE, GREY_LIGHT]),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 7),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 7),
        ("GRID",          (0, 0), (-1, -1), 0.4, GREY_MID),
    ])
    t = Table(wrapped, colWidths=col_widths, style=style, repeatRows=1)
    return t


# ── Page 1 — Title (canvas only, no flowables needed) ────────────────────────
def cover_page():
    """Page 1 is drawn entirely by on_cover(). Just trigger a page break."""
    return [PageBreak()]


# ── Page 2 — Identity sheet ───────────────────────────────────────────────────
def identity_page():
    """Page 2: document info card + description. Uses the normal on_page header."""
    elems = []

    S_INFO_KEY = ParagraphStyle(
        "info_key2", fontName="Helvetica-Bold", fontSize=10, textColor=BLUE_DARK, leading=14
    )
    S_INFO_VAL = ParagraphStyle(
        "info_val2", fontName="Helvetica", fontSize=10, textColor=BLACK, leading=14
    )
    S_SHEET_TITLE = ParagraphStyle(
        "sheet_title", fontName="Helvetica-Bold", fontSize=14,
        textColor=BLUE_DARK, alignment=TA_CENTER, spaceBefore=10, spaceAfter=16
    )

    elems.append(sp(1.5))
    elems.append(Paragraph("Fiche d'identification du document", S_SHEET_TITLE))
    elems.append(hr())
    elems.append(sp(0.4))

    info_data = [
        [Paragraph("Titre",       S_INFO_KEY), Paragraph("Carousel Allocation Tool — Documentation Utilisateur", S_INFO_VAL)],
        [Paragraph("Version",     S_INFO_KEY), Paragraph("1.0",                                                   S_INFO_VAL)],
        [Paragraph("Date",        S_INFO_KEY), Paragraph("Mars 2026",                                             S_INFO_VAL)],
        [Paragraph("Auteur",      S_INFO_KEY), Paragraph("Aik Sidi Ahmed",                                        S_INFO_VAL)],
        [Paragraph("Usage",       S_INFO_KEY), Paragraph("Hub Performance",                                       S_INFO_VAL)],
        [Paragraph("Technologie", S_INFO_KEY), Paragraph("Python (usage interne)",                                S_INFO_VAL)],
        [Paragraph("Diffusion",   S_INFO_KEY), Paragraph("Confidentiel – Usage interne uniquement",               S_INFO_VAL)],
    ]
    info_style = TableStyle([
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [BLUE_LIGHT, WHITE]),
        ("TOPPADDING",     (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING",  (0, 0), (-1, -1), 9),
        ("LEFTPADDING",    (0, 0), (-1, -1), 14),
        ("RIGHTPADDING",   (0, 0), (-1, -1), 14),
        ("GRID",           (0, 0), (-1, -1), 0.4, GREY_MID),
        ("LINEAFTER",      (0, 0), (0, -1),  2,   BLUE_MID),
    ])
    t = Table(info_data, colWidths=[4 * cm, 12 * cm], style=info_style)
    elems.append(t)

    elems.append(sp(1.5))
    elems.append(hr())
    elems.append(sp(0.3))

    S_DESC_TITLE = ParagraphStyle(
        "desc_title", fontName="Helvetica-Bold", fontSize=11,
        textColor=BLUE_MID, spaceAfter=6
    )
    elems.append(Paragraph("Objet du document", S_DESC_TITLE))
    elems.append(Paragraph(
        "Ce document est le guide de référence de l'outil <b>Carousel Allocation Tool</b>, "
        "destiné aux équipes opérations aéroportuaires. Il décrit l'objectif de l'outil, "
        "les données d'entrée requises, la configuration des carrousels et des règles, "
        "le déroulement pas à pas de l'interface, ainsi que les fichiers de sortie générés.",
        S_BODY))
    elems.append(Paragraph(
        "L'outil est accessible via un navigateur web. Aucune installation n'est requise "
        "de la part de l'utilisateur final.",
        S_BODY))

    elems.append(PageBreak())
    return elems


# ── Table of contents (manual) ───────────────────────────────────────────────
def toc():
    elems = []
    elems.append(SectionBar("Sommaire"))
    elems.append(sp(0.4))

    sections = [
        ("1.", "Présentation de l'outil",                   "3"),
        ("2.", "Architecture générale",                      "3"),
        ("3.", "Données d'entrée",                           "4"),
        ("  3.1", "Format de fichier accepté",               "4"),
        ("  3.2", "Colonnes obligatoires",                   "4"),
        ("  3.3", "Colonnes optionnelles",                   "5"),
        ("  3.4", "Valeurs attendues par colonne",           "5"),
        ("4.", "Configuration de l'outil",                   "6"),
        ("  4.1", "Paramètres des carrousels",               "6"),
        ("  4.2", "Paramètres de temps",                     "6"),
        ("  4.3", "Réajustement",                            "7"),
        ("  4.4", "Règle 1 – Multi-carrousels",              "7"),
        ("  4.5", "Règle 2 – Narrow → Wide",                 "8"),
        ("  4.6", "Règle 3 – Extras (carrousels supp.)",     "8"),
        ("  4.7", "Ordre de priorité des règles",            "9"),
        ("  4.8", "Couleurs de planning",                    "9"),
        ("5.", "Utilisation pas à pas",                      "10"),
        ("6.", "Capacités et contraintes",                   "12"),
        ("7.", "Résultats générés (Outputs)",                "13"),
        ("  7.1", "Récapitulatif d'allocation (CSV)",        "13"),
        ("  7.2", "Timeline Excel",                          "13"),
        ("  7.3", "Heatmap Excel",                           "14"),
        ("  7.4", "KPIs affichés à l'écran",                 "14"),
        ("8.", "Codes d'erreur et avertissements",           "15"),
        ("9.", "Glossaire",                                  "16"),
    ]

    S_TOC_MAIN = ParagraphStyle(
        "toc_main", fontName="Helvetica-Bold", fontSize=10,
        textColor=BLUE_DARK, leading=16,
    )
    S_TOC_SUB = ParagraphStyle(
        "toc_sub", fontName="Helvetica", fontSize=9,
        textColor=colors.HexColor("#444444"), leading=14,
        leftIndent=18,
    )
    S_TOC_PAGE = ParagraphStyle(
        "toc_page", fontName="Helvetica", fontSize=9,
        textColor=colors.HexColor("#444444"), alignment=TA_CENTER,
    )
    S_TOC_PAGE_MAIN = ParagraphStyle(
        "toc_page_main", fontName="Helvetica-Bold", fontSize=10,
        textColor=BLUE_DARK, alignment=TA_CENTER,
    )

    toc_data = []
    ts_cmds = []

    for i, (num, title, page) in enumerate(sections):
        is_sub = "." in num.strip() and not num.strip().endswith(".")
        if is_sub:
            label = Paragraph(f"{num.strip()}  {title}", S_TOC_SUB)
            pg    = Paragraph(page, S_TOC_PAGE)
        else:
            label = Paragraph(f"{num}  {title}", S_TOC_MAIN)
            pg    = Paragraph(page, S_TOC_PAGE_MAIN)
        toc_data.append([label, pg])

    ts = TableStyle([
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [WHITE, GREY_LIGHT]),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW",     (0, -1), (-1, -1), 0.5, GREY_MID),
    ])
    t = Table(toc_data, colWidths=[14.5 * cm, 1.5 * cm], style=ts)
    elems.append(t)
    elems.append(PageBreak())
    return elems


# ── Section 1 – Présentation ─────────────────────────────────────────────────
def section_presentation():
    elems = []
    elems.append(SectionBar("1.  Présentation de l'outil"))
    elems.append(sp(0.3))
    elems.append(Paragraph(
        "Le <b>Carousel Allocation Tool</b> est un outil web dédié aux opérations aéroportuaires. "
        "Il automatise l'affectation des vols aux carrousels bagages d'un aéroport en tenant compte "
        "des contraintes de capacité, des catégories d'appareils et des fenêtres horaires de traitement bagages.",
        S_BODY))
    elems.append(Paragraph(
        "L'outil permet de :",
        S_BODY))
    elems.append(bullet("Importer un fichier de vols (Excel ou CSV)."))
    elems.append(bullet("Associer automatiquement chaque vol à un ou plusieurs carrousels disponibles."))
    elems.append(bullet("Appliquer des règles métier configurables (round-robin, multi-carrousel, réajustement…)."))
    elems.append(bullet("Générer des rapports de résultats : récapitulatif CSV, timeline et heatmap Excel, KPIs."))
    elems.append(sp(0.2))
    elems.append(Paragraph(
        "<i>L'outil fonctionne grâce à une application Python déployée en interne — "
        "aucune installation n'est requise de la part de l'utilisateur final.</i>",
        S_NOTE))
    elems.append(sp(0.4))

    elems.append(SectionBar("2.  Architecture générale"))
    elems.append(sp(0.3))
    elems.append(Paragraph(
        "L'outil se compose d'une interface web accessible via navigateur et d'un moteur de calcul "
        "côté serveur. L'utilisateur interagit uniquement avec l'interface — le traitement est réalisé "
        "en arrière-plan.",
        S_BODY))
    elems.append(sp(0.2))

    arch_data = [
        ["Couche",          "Rôle"],
        ["Interface web",   "Formulaire de saisie, affichage des résultats et téléchargement des fichiers"],
        ["Serveur API",     "Réception des fichiers, gestion des sessions, orchestration des calculs"],
        ["Moteur d'allocation", "Application des règles, calcul des affectations, génération des fichiers de sortie"],
    ]
    elems.append(col_table(arch_data, col_widths=[4.5 * cm, 11.5 * cm]))
    elems.append(sp(0.3))
    elems.append(PageBreak())
    return elems


# ── Section 3 – Données d'entrée ─────────────────────────────────────────────
def section_input():
    elems = []
    elems.append(SectionBar("3.  Données d'entrée"))
    elems.append(sp(0.3))

    # 3.1
    elems.append(Paragraph("3.1  Format de fichier accepté", S_H2))
    fmt_data = [
        ["Format",  "Extension",  "Remarques"],
        ["Excel",   ".xlsx",      "Format recommandé — feuille active lue par défaut"],
        ["CSV",     ".csv",       "Séparateur virgule ou point-virgule détecté automatiquement"],
    ]
    elems.append(col_table(fmt_data, col_widths=[3.5 * cm, 3 * cm, 9.5 * cm]))
    elems.append(sp(0.15))
    elems.append(Paragraph(
        "Le fichier doit contenir <b>une ligne d'en-tête</b> (noms de colonnes) en première ligne. "
        "Les colonnes peuvent être dans n'importe quel ordre — l'outil propose une étape de mapping "
        "pour les associer aux champs attendus.",
        S_BODY))

    elems.append(sp(0.3))
    # 3.2
    elems.append(Paragraph("3.2  Colonnes obligatoires", S_H2))
    elems.append(Paragraph(
        "Les quatre colonnes suivantes sont <b>indispensables</b>. Sans elles, l'allocation ne peut pas démarrer.",
        S_BODY))

    req_data = [
        ["Nom interne",       "Description",                                      "Exemple"],
        ["DepartureTime",     "Date et heure de départ du vol",                   "2024-06-15 08:30"],
        ["FlightNumber",      "Identifiant unique du vol",                        "AF1234"],
        ["Category",          "Catégorie de l'appareil : Wide body ou Narrow body","Wide"],
        ["Positions",         "Nombre de positions bagages requises",             "3"],
    ]
    elems.append(col_table(req_data, col_widths=[3.8 * cm, 8 * cm, 4.2 * cm]))

    elems.append(sp(0.3))
    # 3.3
    elems.append(Paragraph("3.3  Colonnes optionnelles", S_H2))
    elems.append(Paragraph(
        "Ces colonnes enrichissent l'allocation mais ne sont pas bloquantes si elles sont absentes.",
        S_BODY))

    opt_data = [
        ["Nom interne",       "Description",                                           "Comportement si absente"],
        ["Terminal",          "Terminal de l'aéroport (ex : T1, T2)",                  "Aucun filtrage par terminal"],
        ["MakeupOpening",     "Heure d'ouverture du tapis bagages",                    "Calculée via offset de temps"],
        ["MakeupClosing",     "Heure de fermeture du tapis bagages",                   "Calculée via offset de temps"],
    ]
    elems.append(col_table(opt_data, col_widths=[3.8 * cm, 6.5 * cm, 5.7 * cm]))

    elems.append(sp(0.3))
    # 3.4
    elems.append(Paragraph("3.4  Valeurs attendues par colonne", S_H2))

    val_data = [
        ["Colonne",        "Type",      "Format / Valeurs acceptées",                          "Remarques"],
        ["DepartureTime",  "Datetime",  "YYYY-MM-DD HH:MM  ou  DD/MM/YYYY HH:MM",              "Doit être parsable comme date"],
        ["FlightNumber",   "Texte",     "Chaîne libre (ex : AF1234, EK 505)",                  "Doit être unique par plage horaire"],
        ["Category",       "Texte",     "\"Wide\" / \"Narrow\"  (insensible à la casse)",      "Tout autre valeur génère une alerte"],
        ["Positions",      "Entier",    "Nombre entier positif ≥ 1",                           "Doit être ≤ capacité max du carrousel"],
        ["Terminal",       "Texte",     "Chaîne libre correspondant au nom de terminal configuré","Ignorée si non configurée"],
        ["MakeupOpening",  "Datetime",  "Même format que DepartureTime",                       "Optionnel — peut être calculé"],
        ["MakeupClosing",  "Datetime",  "Même format que DepartureTime",                       "Optionnel — peut être calculé"],
    ]
    elems.append(col_table(val_data, col_widths=[3.2 * cm, 2 * cm, 5.8 * cm, 5 * cm]))
    elems.append(sp(0.2))
    elems.append(Paragraph(
        "Toute colonne supplémentaire présente dans le fichier d'entrée est conservée et retransmise "
        "dans les fichiers de sortie sans modification.",
        S_NOTE))

    elems.append(PageBreak())
    return elems


# ── Section 4 – Configuration ─────────────────────────────────────────────────
def section_config():
    elems = []
    elems.append(SectionBar("4.  Configuration de l'outil"))
    elems.append(sp(0.3))

    # ── 4.1 ──
    elems.append(Paragraph("4.1  Paramètres des carrousels", S_H2))
    elems.append(Paragraph(
        "Pour chaque carrousel, l'utilisateur définit sa capacité en positions selon la catégorie d'appareil :",
        S_BODY))
    cap_data = [
        ["Paramètre",       "Description",                                                      "Exemple"],
        ["Identifiant",     "Nom ou numéro du carrousel (ex : C1, C2, Belt 3…)",                "C1"],
        ["Wide positions",  "Nombre de positions disponibles pour les appareils Wide body",     "4"],
        ["Narrow positions","Nombre de positions disponibles pour les appareils Narrow body",   "6"],
    ]
    elems.append(col_table(cap_data, col_widths=[4 * cm, 9 * cm, 3 * cm]))
    elems.append(sp(0.15))
    elems.append(Paragraph(
        "Un appareil <b>Wide body</b> peut utiliser des positions Wide <i>et</i> des positions Narrow "
        "(si configuré). Un appareil <b>Narrow body</b> n'utilise que des positions Narrow.",
        S_BODY))

    elems.append(sp(0.3))
    # ── 4.2 ──
    elems.append(Paragraph("4.2  Paramètres de temps", S_H2))
    time_data = [
        ["Paramètre",            "Description",                                                       "Défaut"],
        ["Time step",            "Granularité de la timeline (en minutes)",                           "5 min"],
        ["Makeup opening offset","Décalage avant le départ pour l'ouverture du tapis (en minutes)",  "–90 min"],
        ["Makeup closing offset","Décalage avant le départ pour la fermeture du tapis (en minutes)", "–30 min"],
    ]
    elems.append(col_table(time_data, col_widths=[4.8 * cm, 8.2 * cm, 3 * cm]))
    elems.append(sp(0.15))
    elems.append(Paragraph(
        "Exemple : pour un vol à 10h00 avec offset ouverture = –90 min et fermeture = –30 min, "
        "le carrousel sera occupé de 08h30 à 09h30.",
        S_NOTE))

    elems.append(PageBreak())

    # ── 4.3 ──
    elems.append(SectionBar("4.  Configuration de l'outil (suite) — Réajustement & Règles"))
    elems.append(sp(0.3))
    elems.append(Paragraph("4.3  Réajustement", S_H2))
    elems.append(Paragraph(
        "Le <b>réajustement</b> est une phase d'optimisation qui s'exécute <i>après</i> l'allocation initiale "
        "(round-robin). Il prend en charge les vols non assignés lors du premier passage et tente de leur "
        "trouver un carrousel en appliquant successivement les règles activées.",
        S_BODY))
    elems.append(Paragraph(
        "Lorsque la case <b>«&nbsp;Appliquer les règles de réajustement&nbsp;»</b> est décochée, "
        "aucune règle complémentaire n'est appliquée — seul le round-robin de base est utilisé. "
        "Les vols qui ne trouvent pas de place restent non assignés avec la raison NO_CAPACITY.",
        S_BODY))
    elems.append(Paragraph(
        "Chaque règle est indépendante. Pour chaque vol non assigné, l'outil essaie les règles "
        "dans l'ordre de priorité défini et s'arrête dès qu'une règle parvient à affecter le vol.",
        S_BODY))

    elems.append(sp(0.3))
    # ── 4.4 ──
    elems.append(Paragraph("4.4  Règle 1 – Multi-carrousels", S_H2))
    elems.append(Paragraph(
        "Par défaut, chaque vol est affecté à <b>un seul carrousel</b>. Si la demande en positions "
        "dépasse la capacité d'un carrousel seul, le vol reste non assigné. La règle Multi-carrousels "
        "autorise un vol à être <b>réparti sur plusieurs carrousels simultanément</b> pour absorber "
        "cette demande.",
        S_BODY))
    multi_data = [
        ["Paramètre",                        "Description",                                                                         "Valeur par défaut"],
        ["MAX_CAROUSELS_PER_FLIGHT_NARROW",   "Nombre maximum de carrousels utilisables pour un vol Narrow body",                   "3"],
        ["MAX_CAROUSELS_PER_FLIGHT_WIDE",     "Nombre maximum de carrousels utilisables pour un vol Wide body",                     "2"],
    ]
    elems.append(col_table(multi_data, col_widths=[6 * cm, 7 * cm, 3 * cm]))
    elems.append(sp(0.15))
    elems.append(Paragraph(
        "Exemple : un vol Narrow body nécessitant 7 positions peut être réparti sur 3 carrousels "
        "(ex : 3 + 3 + 1 positions). Le résultat est visible dans la colonne <b>CarouselList</b> "
        "du fichier CSV de sortie et affiché avec la couleur Split dans le planning.",
        S_NOTE))

    elems.append(sp(0.3))
    # ── 4.5 ──
    elems.append(Paragraph("4.5  Règle 2 – Narrow → Wide", S_H2))
    elems.append(Paragraph(
        "Lorsqu'un vol Narrow body ne peut pas être placé sur les positions Narrow disponibles, "
        "cette règle autorise l'outil à le traiter comme un vol <b>Wide body</b> pour l'allocation. "
        "Le vol peut alors occuper des positions Wide body libres.",
        S_BODY))
    nw_data = [
        ["Comportement",      "Description"],
        ["Détection",         "S'applique uniquement si aucune solution Narrow body n'a été trouvée"],
        ["Conversion",        "La catégorie du vol est temporairement changée en Wide pour trouver un carrousel"],
        ["Colonne CategoryChanged", "Marquée «&nbsp;YES&nbsp;» dans le CSV de sortie si la conversion a eu lieu"],
        ["Colonne FinalCategory",   "Indique «&nbsp;Wide&nbsp;» (catégorie après conversion)"],
        ["Couleur planning",  "Affiché en vert (#00B894) dans la timeline et la heatmap — couleur prioritaire"],
    ]
    elems.append(col_table(nw_data, col_widths=[4.5 * cm, 11.5 * cm]))
    elems.append(sp(0.15))
    elems.append(Paragraph(
        "Cette règle est désactivée par défaut. Elle est utile en cas de saturation des tapis "
        "Narrow body avec des tapis Wide body encore disponibles.",
        S_NOTE))

    elems.append(sp(0.3))
    # ── 4.6 ──
    elems.append(Paragraph("4.6  Règle 3 – Extras (Carrousels supplémentaires)", S_H2))
    elems.append(Paragraph(
        "Lorsqu'un vol ne peut être placé sur aucun des carrousels existants, la règle Extras crée "
        "dynamiquement des <b>carrousels supplémentaires temporaires</b> (nommés EXTRA1, EXTRA2, etc.) "
        "avec une capacité standard définie par l'utilisateur.",
        S_BODY))
    elems.append(Paragraph(
        "Ces carrousels extras ne font pas partie de la configuration initiale — ils représentent "
        "une capacité d'urgence ou de débordement. Ils apparaissent dans tous les fichiers de sortie "
        "comme des carrousels normaux.",
        S_BODY))
    elems.append(sp(0.15))

    extra_data = [
        ["Paramètre",         "Description",                                                                     "Valeur par défaut"],
        ["E-Wide capacity",   "Nombre de positions Wide de chaque carrousel extra",                              "Max Wide des carrousels existants (défaut : 8)"],
        ["E-Narrow capacity", "Nombre de positions Narrow de chaque carrousel extra",                            "Max Narrow des carrousels existants (défaut : 4)"],
        ["Nommage",           "Les extras sont créés à la demande : EXTRA1, EXTRA2…",                            "Automatique"],
        ["Par terminal",      "Si des terminaux sont configurés, la capacité extra peut être définie par terminal","Oui, configurable"],
    ]
    elems.append(col_table(extra_data, col_widths=[4 * cm, 7.5 * cm, 4.5 * cm]))
    elems.append(sp(0.15))
    elems.append(Paragraph(
        "La capacité par défaut des extras est calculée automatiquement comme le maximum des capacités "
        "des carrousels existants. Elle peut être ajustée manuellement dans l'interface avant de lancer "
        "l'allocation.",
        S_NOTE))

    elems.append(PageBreak())

    # ── suite section 4 ──
    elems.append(SectionBar("4.  Configuration de l'outil (suite) — Priorité & Couleurs"))
    elems.append(sp(0.3))

    # ── 4.7 ──
    elems.append(Paragraph("4.7  Ordre de priorité des règles", S_H2))
    elems.append(Paragraph(
        "Lorsque plusieurs règles sont activées, l'interface propose trois menus déroulants "
        "<b>Priorité 1 / Priorité 2 / Priorité 3</b> qui définissent l'ordre dans lequel les règles "
        "sont tentées pour chaque vol non assigné.",
        S_BODY))
    elems.append(Paragraph(
        "Pour chaque vol non assigné après le round-robin, l'outil tente la règle de Priorité 1 d'abord. "
        "Si elle réussit, les priorités 2 et 3 ne sont pas essayées. "
        "Si elle échoue, il passe à la Priorité 2, puis à la Priorité 3.",
        S_BODY))
    prio_data = [
        ["Priorité",    "Règle recommandée",        "Raisonnement"],
        ["Priorité 1",  "Multi-carrousels",         "Essaie d'abord de placer le vol sur les carrousels existants en le répartissant"],
        ["Priorité 2",  "Narrow → Wide",            "Si aucun carrousel Narrow n'est disponible, tente les carrousels Wide"],
        ["Priorité 3",  "Extras",                   "En dernier recours, crée un carrousel supplémentaire"],
    ]
    elems.append(col_table(prio_data, col_widths=[2.5 * cm, 4 * cm, 9.5 * cm]))
    elems.append(sp(0.15))
    elems.append(Paragraph(
        "L'ordre peut être modifié selon les contraintes opérationnelles. "
        "Seules les règles activées apparaissent dans les menus de priorité.",
        S_NOTE))

    elems.append(sp(0.3))
    # ── 4.8 ──
    elems.append(Paragraph("4.8  Couleurs de planning", S_H2))
    elems.append(Paragraph(
        "L'outil affecte une couleur à chaque vol dans la timeline et la heatmap selon son type "
        "d'affectation. Ces couleurs sont personnalisables dans l'interface.",
        S_BODY))

    COLOR_WIDE   = colors.HexColor("#D32F2F")
    COLOR_NARROW = colors.HexColor("#FFCDD2")
    COLOR_SPLIT  = colors.HexColor("#FFC107")
    COLOR_NW     = colors.HexColor("#00B894")

    def color_swatch(hex_color, label):
        swatch = Table([[""]], colWidths=[0.5 * cm], rowHeights=[0.35 * cm])
        swatch.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(hex_color)),
            ("GRID",       (0, 0), (-1, -1), 0.3, GREY_MID),
        ]))
        return swatch

    colors_data = [
        ["Couleur", "Code hex", "Signification",                                          "Priorité d'affichage"],
        ["Wide",    "#D32F2F",  "Vol Wide body affecté normalement",                      "Normale"],
        ["Narrow",  "#FFCDD2",  "Vol Narrow body affecté normalement",                    "Normale"],
        ["Split",   "#FFC107",  "Vol réparti sur plusieurs carrousels (multi-carrousel)", "Prioritaire — écrase Wide/Narrow"],
        ["Narrow → Wide", "#00B894", "Vol Narrow converti et placé sur un carrousel Wide","Prioritaire — écrase Wide/Narrow"],
    ]
    elems.append(col_table(colors_data, col_widths=[2.5 * cm, 2.5 * cm, 7.5 * cm, 3.5 * cm]))
    elems.append(sp(0.15))
    elems.append(Paragraph(
        "Les couleurs Split et Narrow → Wide ont la priorité sur les couleurs de base Wide et Narrow. "
        "Un vol split sera toujours affiché en jaune, même s'il est de catégorie Wide.",
        S_NOTE))

    elems.append(PageBreak())
    return elems


# ── Section 5 – Utilisation pas à pas ────────────────────────────────────────
def section_steps():
    elems = []
    elems.append(SectionBar("5.  Utilisation pas à pas"))
    elems.append(sp(0.3))
    elems.append(Paragraph(
        "L'interface guide l'utilisateur à travers un assistant en 5 étapes. "
        "Chaque étape doit être validée avant de passer à la suivante.",
        S_BODY))
    elems.append(sp(0.3))

    steps = [
        (
            "Étape 1 — Import du fichier",
            [
                "Cliquer sur <b>«&nbsp;Choisir un fichier&nbsp;»</b> et sélectionner le fichier Excel (.xlsx) ou CSV.",
                "L'outil lit automatiquement l'en-tête et affiche un aperçu des premières lignes.",
                "Vérifier que le fichier s'affiche correctement avant de continuer.",
            ]
        ),
        (
            "Étape 2 — Mapping des colonnes",
            [
                "L'outil affiche la liste des colonnes détectées dans le fichier.",
                "Pour chaque champ obligatoire (<b>DepartureTime, FlightNumber, Category, Positions</b>), "
                "sélectionner la colonne correspondante dans le fichier.",
                "Les colonnes optionnelles (Terminal, MakeupOpening, MakeupClosing) peuvent être mappées ou ignorées.",
                "Un message d'erreur apparaît si une colonne obligatoire n'est pas mappée.",
            ]
        ),
        (
            "Étape 3 — Configuration des carrousels",
            [
                "Renseigner pour chaque carrousel son identifiant, ses positions Wide et ses positions Narrow.",
                "Ajouter autant de carrousels que nécessaire via le bouton <b>«&nbsp;Ajouter un carrousel&nbsp;»</b>.",
                "Si des terminaux sont présents dans le fichier, associer chaque terminal à un groupe de carrousels.",
            ]
        ),
        (
            "Étape 4 — Paramètres & Règles",
            [
                "Définir le <b>time step</b> (granularité de la timeline, en minutes).",
                "Renseigner les offsets de temps pour les fenêtres makeup (ouverture / fermeture).",
                "Activer ou désactiver les règles de gestion selon les besoins opérationnels.",
                "Valider les paramètres pour lancer l'allocation.",
            ]
        ),
        (
            "Étape 5 — Résultats & Export",
            [
                "L'outil affiche les KPIs : nombre de vols traités, assignés, non assignés, taux d'utilisation.",
                "Un tableau récapitulatif liste chaque vol avec le carrousel affecté et les éventuelles alertes.",
                "Télécharger les fichiers générés via les boutons de téléchargement : "
                "<b>Summary CSV</b>, <b>Timeline Excel</b>, <b>Heatmap Excel</b>.",
                "En cas de vols non assignés, consulter la colonne <b>Raison</b> pour identifier la cause.",
            ]
        ),
    ]

    for i, (title, bullets) in enumerate(steps):
        # Step header row
        step_num = str(i + 1)
        header_data = [[
            Paragraph(f"<font color='white'><b>{step_num}</b></font>",
                      ParagraphStyle("sn", fontName="Helvetica-Bold", fontSize=13,
                                     textColor=WHITE, alignment=TA_CENTER)),
            Paragraph(f"<b>{title}</b>",
                      ParagraphStyle("sh", fontName="Helvetica-Bold", fontSize=11,
                                     textColor=WHITE)),
        ]]
        hts = TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), BLUE_MID),
            ("TOPPADDING",    (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ("LEFTPADDING",   (0, 0), (0, 0), 10),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ])
        ht = Table(header_data, colWidths=[1.2 * cm, PAGE_W - 2 * MARGIN - 1.2 * cm], style=hts)

        body_items = [ht]
        for b in bullets:
            body_items.append(Paragraph(f"&nbsp;&nbsp;&nbsp;• {b}", S_BULLET))
        body_items.append(sp(0.25))

        # wrap in light background
        inner = []
        for item in body_items[1:]:
            inner.append(item)

        body_data = [[inner]]
        bts = TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), BLUE_LIGHT),
            ("TOPPADDING",    (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING",   (0, 0), (-1, -1), 10),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
            ("LINEBELOW",     (0, -1), (-1, -1), 0.5, GREY_MID),
        ])
        bt = Table(body_data, colWidths=[PAGE_W - 2 * MARGIN], style=bts)

        elems.append(KeepTogether([ht, bt, sp(0.2)]))

    elems.append(PageBreak())
    return elems


# ── Section 6 – Capacités & contraintes ──────────────────────────────────────
def section_capacity():
    elems = []
    elems.append(SectionBar("6.  Capacités et contraintes"))
    elems.append(sp(0.3))

    elems.append(Paragraph("Limites de l'outil", S_H2))
    limits_data = [
        ["Paramètre",                    "Valeur / Comportement"],
        ["Nombre de vols",               "Pas de limite stricte — performances optimales jusqu'à plusieurs milliers de vols par fichier"],
        ["Nombre de carrousels",         "Pas de limite — autant que nécessaire"],
        ["Positions max par carrousel",  "Défini par l'utilisateur — pas de plafond technique"],
        ["Vols nécessitant + de positions que la capacité max", "Refusés avec le code NO_CAPACITY ou IMPOSSIBLE_DEMAND"],
        ["Vols hors fenêtre horaire valide", "Refusés avec le code BAD_TIME"],
        ["Taille du fichier d'entrée",   "Pas de limite fixe — les opérations sont vectorisées pour de bonnes performances"],
    ]
    elems.append(col_table(limits_data, col_widths=[7 * cm, 9 * cm]))
    elems.append(sp(0.3))

    elems.append(Paragraph("Contraintes de capacité", S_H2))
    elems.append(Paragraph(
        "La capacité d'un carrousel est modélisée avec deux compteurs indépendants :",
        S_BODY))
    elems.append(bullet("<b>Wide positions</b> : positions réservées aux appareils Wide body."))
    elems.append(bullet("<b>Narrow positions</b> : positions réservées aux appareils Narrow body."))
    elems.append(sp(0.15))
    elems.append(Paragraph(
        "À chaque instant (selon le time step), la somme des positions occupées ne peut pas dépasser "
        "la capacité déclarée du carrousel. Si la règle <b>Narrow-to-Wide</b> est activée, "
        "un vol Narrow peut consommer des positions Wide si les positions Narrow sont saturées.",
        S_BODY))
    elems.append(sp(0.3))

    elems.append(Paragraph("Contraintes temporelles", S_H2))
    elems.append(Paragraph(
        "Chaque vol occupe un carrousel pendant toute la durée de sa fenêtre makeup "
        "(de MakeupOpening à MakeupClosing). Deux vols ne peuvent pas occuper les mêmes positions "
        "sur le même carrousel pendant une même tranche horaire.",
        S_BODY))

    elems.append(PageBreak())
    return elems


# ── Section 7 – Outputs ───────────────────────────────────────────────────────
def section_outputs():
    elems = []
    elems.append(SectionBar("7.  Résultats générés (Outputs)"))
    elems.append(sp(0.3))

    # 7.1
    elems.append(Paragraph("7.1  Récapitulatif d'allocation (CSV)", S_H2))
    elems.append(Paragraph(
        "Fichier CSV téléchargeable listant tous les vols du fichier d'entrée avec les informations d'affectation.",
        S_BODY))
    csv_data = [
        ["Colonne ajoutée",   "Description"],
        ["Carousel",          "Identifiant du carrousel affecté (ex : C1, C2…)"],
        ["CarouselList",      "Liste des carrousels si affectation multi-carrousel (ex : C1;C3)"],
        ["AllocationStatus",  "ASSIGNED / UNASSIGNED"],
        ["UnassignedReason",  "Code de raison si non assigné (voir section 8)"],
        ["RuleApplied",       "Règle ayant permis l'affectation (round_robin, multi, extra…)"],
    ]
    elems.append(col_table(csv_data, col_widths=[5 * cm, 11 * cm]))
    elems.append(Paragraph("Toutes les colonnes du fichier d'entrée sont conservées.", S_NOTE))

    elems.append(sp(0.3))
    # 7.2
    elems.append(Paragraph("7.2  Timeline Excel", S_H2))
    elems.append(Paragraph(
        "Fichier Excel représentant l'occupation de chaque carrousel sur l'ensemble de la journée, "
        "découpée selon le time step configuré.",
        S_BODY))
    tl_data = [
        ["Contenu",             "Description"],
        ["Lignes",              "Un carrousel par ligne"],
        ["Colonnes",            "Une tranche horaire par colonne (selon le time step)"],
        ["Valeur de cellule",   "Nombre de positions occupées à cet instant"],
        ["Couleur de cellule",  "Code couleur indiquant le taux d'occupation (vert → orange → rouge)"],
        ["Onglet supplémentaire","Capacité libre restante par carrousel et par tranche horaire"],
    ]
    elems.append(col_table(tl_data, col_widths=[4.5 * cm, 11.5 * cm]))

    elems.append(sp(0.3))
    # 7.3
    elems.append(Paragraph("7.3  Heatmap Excel", S_H2))
    elems.append(Paragraph(
        "Fichier Excel de visualisation graphique de l'occupation globale de tous les carrousels. "
        "Permet d'identifier rapidement les pics de charge et les carrousels sous-utilisés.",
        S_BODY))
    hm_data = [
        ["Contenu",        "Description"],
        ["Heatmap globale","Vue d'ensemble de l'occupation sur la journée"],
        ["Graphiques",     "Courbes d'occupation par carrousel"],
        ["Taux d'utilisation","Pourcentage d'utilisation moyen par carrousel sur la journée"],
    ]
    elems.append(col_table(hm_data, col_widths=[4.5 * cm, 11.5 * cm]))

    elems.append(sp(0.3))
    # 7.4
    elems.append(Paragraph("7.4  KPIs affichés à l'écran", S_H2))
    kpi_data = [
        ["KPI",                         "Description"],
        ["Total vols",                  "Nombre total de vols dans le fichier d'entrée"],
        ["Vols assignés",               "Nombre de vols affectés à un carrousel avec succès"],
        ["Vols non assignés",           "Nombre de vols non affectés (avec raison)"],
        ["Taux d'assignation",          "Pourcentage de vols assignés sur le total"],
        ["Taux d'utilisation moyen",    "Occupation moyenne des carrousels sur la période"],
        ["Alertes & avertissements",    "Nombre de problèmes détectés dans les données ou l'allocation"],
    ]
    elems.append(col_table(kpi_data, col_widths=[5.5 * cm, 10.5 * cm]))

    elems.append(PageBreak())
    return elems


# ── Section 8 – Codes d'erreur ────────────────────────────────────────────────
def section_errors():
    elems = []
    elems.append(SectionBar("8.  Codes d'erreur et avertissements"))
    elems.append(sp(0.3))
    elems.append(Paragraph(
        "Lorsqu'un vol ne peut pas être assigné, un code de raison est renseigné dans la colonne "
        "<b>UnassignedReason</b> du fichier CSV de sortie. Ces codes permettent de comprendre "
        "rapidement la cause du problème.",
        S_BODY))
    elems.append(sp(0.2))

    err_data = [
        ["Code",                "Signification",                                                                  "Action recommandée"],
        ["NO_CAPACITY",         "Aucun carrousel n'avait de positions disponibles pendant la fenêtre du vol",     "Ajouter un carrousel ou activer la règle Extras"],
        ["IMPOSSIBLE_DEMAND",   "Le vol demande plus de positions que la capacité maximale de n'importe quel carrousel","Vérifier la valeur de la colonne Positions ou augmenter la capacité des carrousels"],
        ["BAD_TIME",            "La fenêtre horaire du vol est invalide (heure de fermeture ≤ heure d'ouverture)", "Vérifier les colonnes MakeupOpening et MakeupClosing"],
        ["MISSING_COLUMN",      "Une colonne obligatoire est absente ou non mappée",                              "Vérifier l'étape de mapping des colonnes"],
        ["INVALID_CATEGORY",    "La valeur de la colonne Category n'est pas reconnue",                           "Vérifier que les valeurs sont \"Wide\" ou \"Narrow\""],
    ]
    elems.append(col_table(err_data, col_widths=[3.5 * cm, 7 * cm, 5.5 * cm]))
    elems.append(sp(0.3))

    elems.append(Paragraph("Avertissements non bloquants", S_H2))
    elems.append(Paragraph(
        "Certaines anomalies génèrent un avertissement visible dans les KPIs mais ne bloquent pas "
        "l'allocation :",
        S_BODY))
    elems.append(bullet("Doublons de numéro de vol sur une même plage horaire."))
    elems.append(bullet("Colonnes optionnelles absentes (Terminal, MakeupOpening, MakeupClosing)."))
    elems.append(bullet("Valeurs manquantes (NaN) dans des colonnes non obligatoires."))

    elems.append(PageBreak())
    return elems


# ── Section 9 – Glossaire ─────────────────────────────────────────────────────
def section_glossary():
    elems = []
    elems.append(SectionBar("9.  Glossaire"))
    elems.append(sp(0.3))

    gloss_data = [
        ["Terme",                "Définition"],
        ["Carrousel",            "Tapis roulant bagages sur lequel les passagers récupèrent leurs bagages à l'arrivée ou sur lequel les bagages sont déposés au départ"],
        ["Wide body",            "Catégorie d'avion gros porteur (ex : Boeing 777, Airbus A330, A380) — généralement un grand volume de bagages"],
        ["Narrow body",          "Catégorie d'avion monocouloir (ex : Boeing 737, Airbus A320) — volume de bagages moindre"],
        ["Makeup / Tapis makeup","Période pendant laquelle les bagages d'un vol sont déposés sur le carrousel avant le départ"],
        ["MakeupOpening",        "Heure à laquelle le carrousel est ouvert pour commencer à recevoir les bagages du vol"],
        ["MakeupClosing",        "Heure à laquelle le carrousel est fermé (fin de dépôt des bagages)"],
        ["Positions",            "Nombre d'emplacements occupés par un vol sur un carrousel (lié à la taille de l'avion)"],
        ["Round-robin",          "Algorithme de distribution équitable qui alterne entre les carrousels disponibles"],
        ["Time step",            "Granularité temporelle utilisée pour découper la journée et vérifier les chevauchements"],
        ["KPI",                  "Key Performance Indicator — indicateur clé de performance (ex : taux d'assignation)"],
        ["Multi-carrousel",      "Affectation d'un seul vol sur plusieurs carrousels simultanément si ses besoins dépassent la capacité d'un seul carrousel"],
        ["Heatmap",              "Représentation visuelle par code couleur de l'intensité d'occupation des carrousels"],
        ["Timeline",             "Vue chronologique de l'occupation de chaque carrousel sur la journée"],
    ]
    elems.append(col_table(gloss_data, col_widths=[4 * cm, 12 * cm]))

    elems.append(sp(0.6))
    elems.append(hr())
    elems.append(Paragraph(
        "Document rédigé par Aik Sidi Ahmed — Carousel Allocation Tool v1.0 — Mars 2026",
        S_CAPTION))
    return elems


# ── Build PDF ────────────────────────────────────────────────────────────────
def build():
    output_path = "Carousel_Allocation_Tool_Documentation.pdf"
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=1.4 * cm, bottomMargin=1.2 * cm,
        title="Carousel Allocation Tool — Documentation Utilisateur",
        author="Aik Sidi Ahmed",
    )

    story = []
    story += cover_page()
    story += identity_page()
    story += toc()
    story += section_presentation()
    story += section_input()
    story += section_config()
    story += section_steps()
    story += section_capacity()
    story += section_outputs()
    story += section_errors()
    story += section_glossary()

    doc.build(story, onFirstPage=on_cover, onLaterPages=on_page)
    print(f"OK  PDF genere : {output_path}")


if __name__ == "__main__":
    build()
