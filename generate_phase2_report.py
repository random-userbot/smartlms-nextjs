from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from zipfile import ZipFile
from xml.etree import ElementTree as ET
from io import BytesIO

import math
import shutil

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from PIL import Image, ImageEnhance, ImageFilter

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    Image as RLImage,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(r"C:/Users/revan/Downloads/smartlms-version2")
TEMPLATE_DOCX = Path(r"C:/Users/revan/Downloads/final_report.docx")
PHASE1_PDF = Path(r"C:/Users/revan/Downloads/7cso2b8 major project.pdf")
PHASE1_DOCX = Path(r"C:/Users/revan/Downloads/7cso2b8 major project (2).docx")
OUTPUT_DIR = ROOT / "phase2_report_output"
ASSET_DIR = OUTPUT_DIR / "assets"
PHASE1_CURATED_DIR = ASSET_DIR / "phase1_reference" / "curated"
DOCX_OUT = OUTPUT_DIR / "SmartLMS_Phase2_Report.docx"
PDF_OUT = OUTPUT_DIR / "SmartLMS_Phase2_Report.pdf"

TITLE = "ENHANCING TEACHING EVALUATION IN SMART ENGINEERING CAMPUS"
SUBTITLE = "A report on major project work phase-2"
ACADEMIC_YEAR = "2025-2026"
DEPARTMENT = "DEPARTMENT OF COMPUTER SCIENCE AND ENGINEERING(NETWORKS)"
COLLEGE = "KAKATIYA INSTITUTE OF TECHNOLOGY AND SCIENCE, WARANGAL"
COLLEGE_SUB = "(An Autonomous Institute under Kakatiya University, Warangal)"

STUDENTS = [
    ("PURAM REVANTH", "B22IN066"),
    ("MOHAMMED FAHAD AHMED", "B22IN073"),
    ("MALLADI RAJAVARDHAN REDDY", "B22IN093"),
    ("JANAGANI HARSHAVARDHAN", "B22IN097"),
    ("AFSHAN", "B22IN119"),
]
GUIDE = "T. Sravanthi"
GUIDE_DESIGNATION = "Asst. Professor"
CO_GUIDE = "Dr. Kumar Dorthi"
CO_GUIDE_DESIGNATION = "Asst. Professor"
CONVENER = "Dr. S. Venkatramulu, Assoc. Prof."
HOD = "Dr. V. Shankar, Professor & Head"

FIGURES = []
TABLES = []


def ensure_dirs() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ASSET_DIR.mkdir(parents=True, exist_ok=True)


def twips_to_inches(value: int) -> float:
    return value / 1440.0


def set_cover_title(ax, title: str, subtitle: str | None = None):
    ax.axis("off")
    ax.text(0.5, 0.74, title, ha="center", va="center", fontsize=24, fontweight="bold", family="DejaVu Sans")
    if subtitle:
        ax.text(0.5, 0.58, subtitle, ha="center", va="center", fontsize=14, family="DejaVu Sans")


def create_architecture_diagram(path: Path) -> None:
    fig, ax = plt.subplots(figsize=(14, 8), dpi=200)
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 8)
    ax.axis("off")

    nodes = {
        "Frontend": (1, 5.4, 2.5, 1.0, "#1f77b4"),
        "Backend API": (4.1, 5.4, 2.7, 1.0, "#2ca02c"),
        "ML Service": (7.5, 6.2, 2.6, 1.0, "#d62728"),
        "ML Worker": (7.5, 4.9, 2.6, 1.0, "#ff7f0e"),
        "RDS + PGVector": (10.8, 5.4, 2.7, 1.0, "#9467bd"),
        "SQS": (10.8, 4.0, 2.7, 1.0, "#8c564b"),
        "Groq / Aika RAG": (4.1, 3.5, 2.7, 1.0, "#17becf"),
        "Browser Extension": (1, 3.5, 2.5, 1.0, "#7f7f7f"),
    }
    for label, (x, y, w, h, c) in nodes.items():
        patch = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.03,rounding_size=0.12", linewidth=1.8, edgecolor=c, facecolor="#ffffff")
        ax.add_patch(patch)
        ax.text(x + w / 2, y + h / 2, label, ha="center", va="center", fontsize=12, fontweight="bold", color="#111111")

    arrows = [
        ((3.5, 5.9), (4.1, 5.9)),
        ((6.8, 6.0), (7.5, 6.7)),
        ((6.8, 5.6), (7.5, 5.4)),
        ((10.1, 6.0), (10.8, 5.9)),
        ((10.1, 5.2), (10.8, 4.5)),
        ((3.5, 4.0), (4.1, 4.0)),
        ((2.3, 4.5), (2.3, 5.4)),
        ((12.2, 4.0), (12.2, 5.4)),
        ((12.2, 4.0), (12.2, 4.5)),
    ]
    for start, end in arrows:
        ax.add_patch(FancyArrowPatch(start, end, arrowstyle="->", mutation_scale=15, linewidth=1.5, color="#444444"))

    ax.text(7, 7.4, "SmartLMS Phase 2 Architecture", ha="center", va="center", fontsize=20, fontweight="bold")
    ax.text(7, 0.8, "Frontend, backend, cloud services, ML inference, and Aika RAG operate as loosely coupled services.",
            ha="center", va="center", fontsize=11)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def create_rag_diagram(path: Path) -> None:
    fig, ax = plt.subplots(figsize=(14, 8), dpi=200)
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 8)
    ax.axis("off")

    blocks = [
        ("Upload Material", (0.7, 5.8), "#1f77b4"),
        ("Temp File + Loader", (3.1, 5.8), "#2ca02c"),
        ("Chunk + Embed", (5.6, 5.8), "#d62728"),
        ("PGVector\naika_knowledge", (8.2, 5.8), "#9467bd"),
        ("Aika ask()", (5.6, 3.2), "#ff7f0e"),
        ("Retriever Tool", (8.2, 3.2), "#17becf"),
        ("Groq Answer\nwith citations", (10.8, 3.2), "#8c564b"),
        ("Frontend Chat UI", (0.7, 3.2), "#7f7f7f"),
    ]
    for label, (x, y), c in blocks:
        patch = FancyBboxPatch((x, y), 2.1, 0.95, boxstyle="round,pad=0.04,rounding_size=0.12", linewidth=1.8, edgecolor=c, facecolor="#ffffff")
        ax.add_patch(patch)
        ax.text(x + 1.05, y + 0.48, label, ha="center", va="center", fontsize=11, fontweight="bold")

    arrows = [
        ((2.8, 6.25), (3.1, 6.25)),
        ((5.2, 6.25), (5.6, 6.25)),
        ((7.7, 6.25), (8.2, 6.25)),
        ((9.25, 5.8), (9.25, 4.15)),
        ((7.7, 3.68), (8.2, 3.68)),
        ((10.3, 3.68), (10.8, 3.68)),
        ((2.8, 3.68), (5.6, 3.68)),
        ((11.9, 4.15), (11.9, 5.8)),
    ]
    for start, end in arrows:
        ax.add_patch(FancyArrowPatch(start, end, arrowstyle="->", mutation_scale=15, linewidth=1.5, color="#444444"))

    ax.text(7, 7.4, "Aika Retrieval-Augmented Generation Flow", ha="center", va="center", fontsize=20, fontweight="bold")
    ax.text(7, 1.0, "The assistant stores course and uploaded material in PGVector, retrieves relevant chunks, and answers with Groq-generated explanations.",
            ha="center", va="center", fontsize=11)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def create_sdg_diagram(path: Path) -> None:
    fig, ax = plt.subplots(figsize=(14, 8), dpi=200)
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 8)
    ax.axis("off")

    goals = [
        ("SDG 4\nQuality Education", "Personalized learning analytics\nAika tutoring\nAdaptive feedback", "#2ca02c", (0.7, 4.7)),
        ("SDG 9\nIndustry, Innovation & Infrastructure", "Cloud-native microservices\nECS, RDS, SQS\nReusable ML APIs", "#1f77b4", (3.8, 4.7)),
        ("SDG 10\nReduced Inequalities", "Role-aware dashboards\nAccessible guidance\nContextual support", "#ff7f0e", (6.9, 4.7)),
        ("SDG 17\nPartnerships for the Goals", "Front-end, backend, ML, and cloud services\nworking as an integrated ecosystem", "#9467bd", (10.0, 4.7)),
    ]
    for title, body, color, (x, y) in goals:
        patch = FancyBboxPatch((x, y), 2.6, 2.1, boxstyle="round,pad=0.05,rounding_size=0.12", linewidth=2.0, edgecolor=color, facecolor="#ffffff")
        ax.add_patch(patch)
        ax.text(x + 1.3, y + 1.63, title, ha="center", va="center", fontsize=12, fontweight="bold", color=color)
        ax.text(x + 1.3, y + 0.8, body, ha="center", va="center", fontsize=10)

    ax.text(7, 7.4, "SmartLMS Phase 2 Mapping to Sustainable Development Goals", ha="center", va="center", fontsize=19, fontweight="bold")
    ax.text(7, 1.0, "The project supports equitable, scalable, and technology-enabled learning outcomes.", ha="center", va="center", fontsize=11)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def create_model_chart(path: Path) -> None:
    models = ["Transformer_ViT", "BiLSTM_FMAE", "Fusion_Enhanced", "Baseline_LSTM"]
    values = [59.6, 58.6, 57.4, 74.2]
    colors_list = ["#1f77b4", "#2ca02c", "#ff7f0e", "#d62728"]
    fig, ax = plt.subplots(figsize=(12, 7), dpi=200)
    bars = ax.bar(models, values, color=colors_list, edgecolor="#222222")
    ax.set_ylim(0, 100)
    ax.set_ylabel("Reported accuracy (%)")
    ax.set_title("SmartLMS Export Model Comparison")
    ax.grid(axis="y", alpha=0.25)
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, val + 1, f"{val:.1f}%", ha="center", va="bottom", fontsize=11, fontweight="bold")
    ax.text(0.02, 0.96, "Baseline_LSTM is intentionally flagged in the source docs as misleading because it predicts only one class.",
            transform=ax.transAxes, fontsize=10, va="top")
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def copy_existing_figure(src: Path, dst: Path) -> Path:
    shutil.copy2(src, dst)
    return dst


def extract_phase1_reference_assets() -> dict[str, Path]:
    PHASE1_CURATED_DIR.mkdir(parents=True, exist_ok=True)
    selected = {
        "phase1_literature_survey.png": "image17.jpeg",
        "phase1_tech_stack.png": "image19.png",
        "phase1_system_architecture.png": "image20.jpeg",
        "phase1_methodology_flow.png": "image28.jpeg",
        "phase1_implementation_flow.png": "image29.png",
        "phase1_model_comparison.png": "image27.jpeg",
        "phase1_dashboard_overview.png": "image32.jpeg",
        "phase1_result_gauge.png": "image33.jpeg",
    }
    extracted: dict[str, Path] = {}
    with ZipFile(PHASE1_DOCX) as zf:
        for output_name, source_name in selected.items():
            target = PHASE1_CURATED_DIR / output_name
            if not target.exists() or target.stat().st_size == 0:
                raw = zf.read(f"word/media/{source_name}")
                image = Image.open(BytesIO(raw)).convert("RGB")
                if image.width < 2000:
                    target_width = 2000
                    scale = target_width / image.width
                    image = image.resize((int(image.width * scale), int(image.height * scale)), Image.Resampling.LANCZOS)
                image = image.filter(ImageFilter.SHARPEN)
                image = ImageEnhance.Contrast(image).enhance(1.05)
                image.save(target, format="PNG", optimize=True)
            extracted[output_name] = target
    return extracted


def build_assets() -> dict[str, Path]:
    FIGURES.clear()
    TABLES.clear()
    assets = {}
    assets["rag"] = ASSET_DIR / "aika_rag_flow.png"
    assets["sdg"] = ASSET_DIR / "sdg_mapping.png"

    create_rag_diagram(assets["rag"])
    create_sdg_diagram(assets["sdg"])

    assets.update({f"phase1_{name.split('_', 1)[1].replace('.png', '').replace('.jpeg', '')}": path for name, path in extract_phase1_reference_assets().items()})
    return assets


def read_phase1_author_names() -> list[tuple[str, str]]:
    return STUDENTS


def configure_docx(doc: Document) -> None:
    sec = doc.sections[0]
    sec.page_width = Inches(8.5)
    sec.page_height = Inches(11)
    sec.top_margin = Inches(0.69)
    sec.right_margin = Inches(1.0)
    sec.bottom_margin = Inches(1.0)
    sec.left_margin = Inches(1.0)
    sec.header_distance = Inches(0.5)
    sec.footer_distance = Inches(0.5)

    styles = doc.styles
    normal = styles["Normal"]
    normal.font.name = "Times New Roman"
    normal.font.size = Pt(12)

    for style_name, size in [("Title", 18), ("Heading 1", 16), ("Heading 2", 14), ("Heading 3", 12)]:
        style = styles[style_name]
        style.font.name = "Times New Roman"
        style.font.size = Pt(size)


def add_docx_paragraph(doc: Document, text: str, align=WD_ALIGN_PARAGRAPH.JUSTIFY, bold=False, italic=False, size=12) -> None:
    p = doc.add_paragraph()
    p.alignment = align
    run = p.add_run(text)
    run.bold = bold
    run.italic = italic
    run.font.name = "Times New Roman"
    run.font.size = Pt(size)


def add_docx_heading(doc: Document, text: str, level: int = 1) -> None:
    p = doc.add_paragraph(style=f"Heading {level}")
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    run = p.add_run(text)
    run.font.name = "Times New Roman"


def add_docx_image(doc: Document, img: Path, caption: str, width: float = 6.3) -> None:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run().add_picture(str(img), width=Inches(width))
    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = cap.add_run(caption)
    r.italic = True
    r.font.name = "Times New Roman"
    r.font.size = Pt(10)


def add_docx_table(doc: Document, headers: list[str], rows: list[list[str]], title: str | None = None) -> None:
    if title:
        add_docx_paragraph(doc, title, align=WD_ALIGN_PARAGRAPH.LEFT, bold=True, size=12)
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    hdr = table.rows[0].cells
    for i, h in enumerate(headers):
        hdr[i].text = h
    for row in rows:
        cells = table.add_row().cells
        for i, cell in enumerate(row):
            cells[i].text = cell
    doc.add_paragraph()


def add_docx_title_page(doc: Document) -> None:
    lines = [
        TITLE,
        SUBTITLE,
        "Submitted in partial fulfillment of the",
        "requirements for the award of the degree of",
        "BACHELOR OF TECHNOLOGY",
        "In",
        "COMPUTER SCIENCE AND ENGINEERING (NETWORKS)",
        "By",
    ]
    for line in lines:
        add_docx_paragraph(doc, line, align=WD_ALIGN_PARAGRAPH.CENTER, bold=(line == TITLE or line == "BACHELOR OF TECHNOLOGY"), size=20 if line == TITLE else 16 if line == "BACHELOR OF TECHNOLOGY" else 13)
    for name, roll in read_phase1_author_names():
        add_docx_paragraph(doc, f"{name} ({roll})", align=WD_ALIGN_PARAGRAPH.CENTER, bold=True, size=13)
    add_docx_paragraph(doc, "Under the Guidance of", align=WD_ALIGN_PARAGRAPH.CENTER, size=13)
    add_docx_paragraph(doc, GUIDE, align=WD_ALIGN_PARAGRAPH.CENTER, bold=True, size=13)
    add_docx_paragraph(doc, GUIDE_DESIGNATION, align=WD_ALIGN_PARAGRAPH.CENTER, size=12)
    add_docx_paragraph(doc, f"(Co Guide: {CO_GUIDE})", align=WD_ALIGN_PARAGRAPH.CENTER, size=12)
    add_docx_paragraph(doc, CO_GUIDE_DESIGNATION, align=WD_ALIGN_PARAGRAPH.CENTER, size=12)
    add_docx_paragraph(doc, DEPARTMENT, align=WD_ALIGN_PARAGRAPH.CENTER, bold=True, size=12)
    add_docx_paragraph(doc, COLLEGE, align=WD_ALIGN_PARAGRAPH.CENTER, bold=True, size=12)
    add_docx_paragraph(doc, COLLEGE_SUB, align=WD_ALIGN_PARAGRAPH.CENTER, size=12)
    add_docx_paragraph(doc, ACADEMIC_YEAR, align=WD_ALIGN_PARAGRAPH.CENTER, size=12)


def add_docx_certificate(doc: Document) -> None:
    add_docx_paragraph(doc, "CERTIFICATE", align=WD_ALIGN_PARAGRAPH.CENTER, bold=True, size=14)
    text = (
        "This is to certify that "
        + ", ".join([f"{name} ({roll})" for name, roll in read_phase1_author_names()[:-1]])
        + f", and {read_phase1_author_names()[-1][0]} ({read_phase1_author_names()[-1][1]}) of the B.Tech Computer Science and Engineering (Networks) has satisfactorily completed the dissertation work entitled “{TITLE}” in the partial fulfillment of the requirements of B.Tech degree during this academic year {ACADEMIC_YEAR}."
    )
    add_docx_paragraph(doc, text, size=12)
    doc.add_paragraph()
    add_docx_paragraph(doc, "Project Guide                                   Co - Guide", align=WD_ALIGN_PARAGRAPH.CENTER, size=12)
    add_docx_paragraph(doc, f"{GUIDE}                                   {CO_GUIDE}", align=WD_ALIGN_PARAGRAPH.CENTER, bold=True, size=12)
    add_docx_paragraph(doc, f"{GUIDE_DESIGNATION}                                   {CO_GUIDE_DESIGNATION}", align=WD_ALIGN_PARAGRAPH.CENTER, size=12)
    add_docx_paragraph(doc, "Dept. of CSE (Networks)                           Dept. of CSE (Networks)", align=WD_ALIGN_PARAGRAPH.CENTER, size=12)
    add_docx_paragraph(doc, "KITS, Warangal                                       KITS, Warangal", align=WD_ALIGN_PARAGRAPH.CENTER, size=12)
    doc.add_paragraph()
    add_docx_paragraph(doc, "Projects Convener                                           Head of the Department", align=WD_ALIGN_PARAGRAPH.CENTER, size=12)
    add_docx_paragraph(doc, f"{CONVENER}                                       {HOD}", align=WD_ALIGN_PARAGRAPH.CENTER, bold=True, size=12)
    add_docx_paragraph(doc, "Dept. of CSE (Networks),                           Dept. of CSE (Networks)", align=WD_ALIGN_PARAGRAPH.CENTER, size=12)
    add_docx_paragraph(doc, "KITS, Warangal                                         KITS, Warangal", align=WD_ALIGN_PARAGRAPH.CENTER, size=12)
    add_docx_paragraph(doc, "Examiner-1                                                      Examiner - 2", align=WD_ALIGN_PARAGRAPH.CENTER, size=12)


def add_docx_declaration(doc: Document) -> None:
    add_docx_paragraph(doc, "DECLARATION", align=WD_ALIGN_PARAGRAPH.CENTER, bold=True, size=14)
    text = (
        f"We declare that the work presented in this Major project report Phase-2 is original and has been carried out in the Department of Computer Science and Engineering(Networks), Kakatiya Institute of Technology and Science, Warangal, Telangana, and to best of our knowledge it has been not submitted elsewhere for any degree."
    )
    add_docx_paragraph(doc, text, size=12)
    doc.add_paragraph()
    for name, roll in read_phase1_author_names():
        add_docx_paragraph(doc, f"{name} ({roll})", align=WD_ALIGN_PARAGRAPH.CENTER, size=12)


def add_docx_acknowledgement(doc: Document) -> None:
    add_docx_paragraph(doc, "ACKNOWLEDGEMENT", align=WD_ALIGN_PARAGRAPH.CENTER, bold=True, size=14)
    paras = [
        f"We would like to express our sincere gratitude to our project guide {GUIDE}, {GUIDE_DESIGNATION}, for her valuable guidance, scholarly inputs and consistent encouragement throughout the project work.",
        f"We extend our sincere and heartfelt thanks to our Co-Guide {CO_GUIDE}, {CO_GUIDE_DESIGNATION}, for exemplary guidance and monitoring.",
        f"We are grateful to respected Major Project Convener, {CONVENER}, for permitting us to utilize all the necessary facilities in the Institute.",
        f"We would like to extend thanks to our respected Head of the Department, {HOD}, for allowing us to use the facilities available.",
        "We express our sincere thanks to the Principal, KITS Warangal, for his kind gesture and support.",
        f"We are indebted to the Management of {COLLEGE}, for providing the necessary infrastructure and good academic environment in an endeavor to complete the project.",
        "We would like to acknowledge the faculty and non-teaching staff of the Computer Science and Engineering Department.",
    ]
    for p in paras:
        add_docx_paragraph(doc, p, size=12)
    doc.add_paragraph()
    for name, roll in read_phase1_author_names():
        add_docx_paragraph(doc, f"{name} ({roll})", align=WD_ALIGN_PARAGRAPH.CENTER, size=12)


def add_docx_abstract(doc: Document) -> None:
    add_docx_paragraph(doc, "ABSTRACT", align=WD_ALIGN_PARAGRAPH.CENTER, bold=True, size=14)
    abstract = (
        "SmartLMS Phase-2 extends the earlier evaluation system into a complete learning platform that combines a Next.js frontend, FastAPI backend, an ML microservice, and a RAG-enabled AI tutor. The system continuously tracks engagement, quiz outcomes, lecture usage, and learner interactions to produce role-aware analytics for students, teachers, and administrators. The frontend now exposes dashboards for focus pulse tracking, ICAP distributions, live lecture analytics, teacher performance summaries, and admin correlation views, while the backend centralizes authentication, course management, messaging, notifications, assignments, and engagement logging. The ML layer supports exportable temporal models, lazy loading, ensemble inference, and forecast generation. Aika provides retrieval-augmented tutoring over uploaded documents and course content using PGVector and Groq. The phase-2 revision also incorporates cloud deployment considerations with ECS, RDS, SQS, Cloudinary, and Vercel, and adds a Sustainable Development Goals chapter to show how the platform supports inclusive, scalable, and data-driven education. Overall, the updated system demonstrates a more complete, production-oriented implementation with stronger cloud integration, richer analytics, and a more usable AI tutoring experience."
    )
    add_docx_paragraph(doc, abstract, size=12)


def add_docx_acronyms(doc: Document) -> None:
    add_docx_paragraph(doc, "ACRONYMS", align=WD_ALIGN_PARAGRAPH.CENTER, bold=True, size=14)
    rows = [
        ["API", "Application Programming Interface"],
        ["RAG", "Retrieval-Augmented Generation"],
        ["ML", "Machine Learning"],
        ["LLM", "Large Language Model"],
        ["PGVector", "Postgres vector extension and collection layer"],
        ["ECS", "Elastic Container Service"],
        ["RDS", "Relational Database Service"],
        ["SQS", "Simple Queue Service"],
        ["ICAP", "Interactive, Constructive, Active, Passive"],
        ["SDG", "Sustainable Development Goal"],
    ]
    add_docx_table(doc, ["Acronym", "Expansion"], rows)


def add_docx_toc(doc: Document) -> None:
    add_docx_paragraph(doc, "TABLE OF CONTENTS", align=WD_ALIGN_PARAGRAPH.CENTER, bold=True, size=14)
    lines = [
        ["ABSTRACT", "v"],
        ["ACRONYMS", "vi"],
        ["TABLE OF CONTENTS", "vii"],
        ["LIST OF FIGURES", "viii"],
        ["LIST OF TABLES", "ix"],
        ["CHAPTER 1 INTRODUCTION", "1"],
        ["CHAPTER 2 LITERATURE SURVEY", "5"],
        ["CHAPTER 3 SYSTEM ARCHITECTURE AND IMPLEMENTATION", "9"],
        ["CHAPTER 4 EXPERIMENTATION AND RESULTS", "19"],
        ["CHAPTER 5 SUSTAINABLE DEVELOPMENT GOALS", "28"],
        ["CHAPTER 6 CONCLUSION AND FUTURE SCOPE", "32"],
        ["REFERENCES", "34"],
    ]
    add_docx_table(doc, ["Section", "Page"], lines)


def add_docx_list_of_figures(doc: Document) -> None:
    add_docx_paragraph(doc, "LIST OF FIGURES", align=WD_ALIGN_PARAGRAPH.CENTER, bold=True, size=14)
    rows = [[f[0], f[1]] for f in FIGURES]
    add_docx_table(doc, ["Fig. No.", "Name of the Figure"], rows)


def add_docx_list_of_tables(doc: Document) -> None:
    add_docx_paragraph(doc, "LIST OF TABLES", align=WD_ALIGN_PARAGRAPH.CENTER, bold=True, size=14)
    rows = [[t[0], t[1]] for t in TABLES]
    add_docx_table(doc, ["Table No.", "Name of the Table"], rows)


def add_chapter_1(doc: Document) -> None:
    add_docx_paragraph(doc, "CHAPTER 1", align=WD_ALIGN_PARAGRAPH.CENTER, bold=True, size=14)
    add_docx_heading(doc, "INTRODUCTION", 1)
    paras = [
        "SmartLMS Phase-2 is a teaching evaluation and learning analytics platform that connects classroom engagement, AI tutoring, course content, and cloud deployment into a single system. The project builds on the first phase by preserving the original academic structure while extending the implementation into a modern full-stack service-oriented architecture.",
        "The core problem addressed by the platform is that teaching quality and learner engagement are usually measured from scattered signals rather than a unified evidence base. SmartLMS aggregates activity logs, engagement traces, quiz outcomes, tutor conversations, and teacher analytics to help instructors make actionable decisions and to help students receive adaptive support.",
        "The current phase focuses on production readiness. The codebase now includes a Next.js frontend, a FastAPI backend, a separate ML service with lazy-loaded models, an async worker, and an Aika RAG layer. The cloud stack uses AWS ECS, RDS, SQS, and secure environment-based deployment patterns. This makes the platform suitable for both local demonstration and future scaled deployment.",
    ]
    for p in paras:
        add_docx_paragraph(doc, p)
    add_docx_heading(doc, "1.1 Objectives", 2)
    objectives = [
        "Deliver role-aware dashboards for students, teachers, and administrators.",
        "Centralize authentication, course management, lectures, quizzes, assignments, messages, and notifications in the backend.",
        "Provide real-time and batch engagement analytics using ML inference and temporal forecast metrics.",
        "Enable Aika as a RAG tutor over uploaded documents and course materials.",
        "Deploy the platform as cloud-ready microservices with scalable compute and storage layers.",
    ]
    for item in objectives:
        add_docx_paragraph(doc, f"- {item}")
    add_docx_heading(doc, "1.2 Phase-2 Scope", 2)
    add_docx_paragraph(doc, "Phase-2 keeps the same project narrative as phase-1 but updates the implementation to reflect the SmartLMS codebase, cloud architecture, Aika tutoring, and the new Sustainable Development Goals chapter before the conclusion.")


def add_chapter_2(doc: Document, assets: dict[str, Path]) -> None:
    add_docx_paragraph(doc, "CHAPTER 2", align=WD_ALIGN_PARAGRAPH.CENTER, bold=True, size=14)
    add_docx_heading(doc, "LITERATURE SURVEY", 1)
    paras = [
        "The research draft and training plan show a progression from baseline sequence models to more expressive temporal and multimodal methods. Earlier engagement models such as LSTM, BiLSTM, and CNN-BiLSTM established the feasibility of predicting boredom, engagement, confusion, and frustration from temporal signals, while later work introduced attention, transformer blocks, and ViT-based embeddings to capture richer facial and sequence context.",
        "The SmartLMS training notes indicate that the strongest export model in the repository is Transformer_ViT_59.6%_BEST, followed by BiLSTM_Enhanced_FMAE_58.6% and Fusion_Enhanced_57.4%. The deployment analysis also explains why Baseline_LSTM_74.2%_BIASED is not a useful benchmark, because the reported accuracy is misleading and comes from a biased class prediction setup.",
        "From a systems perspective, the project combines a traditional learning management system with analytics and AI services. This is aligned with the current direction of educational technology research, where dashboards, retrieval-based tutors, and explainable analytics are used together rather than in isolation. The phase-2 platform adopts that idea by integrating the learner UI, teacher feedback loops, and cloud-hosted inference services.",
    ]
    for p in paras:
        add_docx_paragraph(doc, p)
    add_docx_image(doc, assets["phase1_literature_survey"], "Figure 2.1: Literature survey from the phase-1 report reference")
    FIGURES.append(("Figure 2.1", "Literature survey from the phase-1 report reference"))
    add_docx_heading(doc, "2.1 Key Takeaways from Prior Work", 2)
    points = [
        "Temporal models are effective when engagement is represented as a sequence rather than a single snapshot.",
        "Feature richness matters: face crops, action units, gaze, and motion signals improve stability.",
        "Multimodal fusion is promising but must be balanced against latency and deployment cost.",
        "Explainability and instructor-facing analytics are necessary for adoption in real classrooms.",
    ]
    for item in points:
        add_docx_paragraph(doc, f"- {item}")
    add_docx_heading(doc, "2.2 Phase-2 Research Direction", 2)
    add_docx_paragraph(doc, "The second phase therefore emphasizes productization: the model stack is wrapped in a microservice architecture, the analytics are exposed through a web dashboard, and the tutoring layer is connected to a retrieval store so that answers can cite uploaded course materials.")


def add_chapter_3(doc: Document, assets: dict[str, Path]) -> None:
    add_docx_paragraph(doc, "CHAPTER 3", align=WD_ALIGN_PARAGRAPH.CENTER, bold=True, size=14)
    add_docx_heading(doc, "SYSTEM ARCHITECTURE AND IMPLEMENTATION", 1)
    add_docx_paragraph(doc, "The implementation is organized as a modular platform rather than a single monolith. The frontend handles presentation and role-based navigation, the backend owns business logic and persistence, the ML service exposes model endpoints, the worker processes asynchronous jobs, and Aika provides retrieval-augmented tutoring over the project knowledge base.")
    add_docx_image(doc, assets["phase1_system_architecture"], "Figure 3.1: System architecture from the phase-1 report reference")
    FIGURES.append(("Figure 3.1", "System architecture from the phase-1 report reference"))
    add_docx_heading(doc, "3.1 Technology Stack", 2)
    add_docx_image(doc, assets["phase1_tech_stack"], "Figure 3.2: Technology stack from the phase-1 report reference")
    FIGURES.append(("Figure 3.2", "Technology stack from the phase-1 report reference"))
    add_docx_table(doc, ["Layer", "Technology", "Purpose"], [
        ["Frontend", "Next.js 16, React 19, TypeScript, Tailwind", "Role-based UI, dashboards, chat and reports"],
        ["Backend", "FastAPI, SQLAlchemy, JWT", "APIs, persistence, auth, analytics and orchestration"],
        ["ML Service", "FastAPI, export registry, ONNX-ready models", "Engagement inference and ensemble predictions"],
        ["AI Tutor", "Groq, PGVector, HuggingFace embeddings", "Retrieval-augmented response generation"],
        ["Cloud", "AWS ECS, RDS, SQS, Cloudinary", "Production hosting and async processing"],
    ])
    TABLES.append(("Table 3.1", "Technology stack used in phase-2"))
    add_docx_heading(doc, "3.2 Backend Modules", 2)
    add_docx_paragraph(doc, "The backend includes routers for authentication, courses, lectures, engagement, quizzes, feedback, notifications, analytics, admin, users, gamification, assignments, activity tracking, tutor sessions, messaging, and Aika. This is the main source of business logic and the bridge between the UI and data stores.")
    add_docx_image(doc, assets["phase1_methodology_flow"], "Figure 3.3: Methodology flow from the phase-1 report reference")
    FIGURES.append(("Figure 3.3", "Methodology flow from the phase-1 report reference"))
    add_docx_heading(doc, "3.3 AI Tutor and RAG Flow", 2)
    add_docx_image(doc, assets["rag"], "Figure 3.2: Aika RAG ingestion and answer flow")
    FIGURES.append(("Figure 3.4", "Aika RAG ingestion and answer flow"))
    add_docx_paragraph(doc, "Aika stores uploaded documents in PGVector, uses retrieval tools to find relevant chunks, and then generates answers through a Groq model. The phase-2 fix ensures the ask() method is callable from the router and that uploaded course material can actually influence the answer path.")
    add_docx_heading(doc, "3.4 Cloud and Storage Design", 2)
    add_docx_paragraph(doc, "AWS ECS is used for containerized compute, RDS for persistent relational storage, SQS for asynchronous task transport, and Cloudinary for media storage. This separation keeps the system easier to scale and makes it possible to pause compute while preserving stateful data when necessary.")
    add_docx_heading(doc, "3.5 Request Flow", 2)
    add_docx_paragraph(doc, "A typical request starts in the browser, passes through JWT-protected backend routes, and is then routed either to the database, the ML service, or the Aika retrieval chain. The result is returned to the frontend for visualization as a dashboard card, chart, or conversation response.")


def add_chapter_4(doc: Document, assets: dict[str, Path]) -> None:
    add_docx_paragraph(doc, "CHAPTER 4", align=WD_ALIGN_PARAGRAPH.CENTER, bold=True, size=14)
    add_docx_heading(doc, "EXPERIMENTATION AND RESULTS", 1)
    add_docx_paragraph(doc, "Phase-2 focuses on product-level evaluation using the implemented codebase, research artifacts, and exported model summaries. The current repository shows a functional deployment path for the platform and a clear model hierarchy for engagement analytics.")
    add_docx_image(doc, assets["phase1_model_comparison"], "Figure 4.1: Model comparison from the phase-1 report reference")
    FIGURES.append(("Figure 4.1", "Model comparison from the phase-1 report reference"))
    add_docx_heading(doc, "4.1 Model Performance Summary", 2)
    add_docx_table(doc, ["Model", "Reported Score", "Interpretation"], [
        ["Transformer_ViT_59.6%_BEST", "59.6% accuracy", "Best overall balance of accuracy and latency"],
        ["BiLSTM_Enhanced_FMAE_58.6%", "58.6% accuracy", "Faster alternative for near-real-time use"],
        ["Fusion_Enhanced_57.4%", "57.4% accuracy", "Multi-modal fusion model"],
        ["Baseline_LSTM_74.2%_BIASED", "74.2% accuracy", "Misleading baseline; only one-class behavior"],
    ])
    TABLES.append(("Table 4.1", "Export model comparison and interpretation"))
    add_docx_image(doc, assets["phase1_dashboard_overview"], "Figure 4.2: Dashboard overview from the phase-1 report reference")
    FIGURES.append(("Figure 4.2", "Dashboard overview from the phase-1 report reference"))
    add_docx_paragraph(doc, "The deployment analysis recommends Transformer_ViT_59.6%_BEST as the best practical default because it balances performance with a clean deployment profile. For low-latency settings, the BiLSTM alternative remains attractive. The baseline LSTM is kept only as a cautionary reference because the high score does not reflect useful multi-class behavior.")
    add_docx_heading(doc, "4.2 Research Figures", 2)
    add_docx_image(doc, assets["phase1_result_gauge"], "Figure 4.3: Result gauge from the phase-1 report reference")
    FIGURES.append(("Figure 4.3", "Result gauge from the phase-1 report reference"))
    add_docx_image(doc, assets["phase1_implementation_flow"], "Figure 4.4: Implementation flow from the phase-1 report reference")
    FIGURES.append(("Figure 4.4", "Implementation flow from the phase-1 report reference"))
    add_docx_heading(doc, "4.3 Implementation Footprint", 2)
    add_docx_table(doc, ["Metric", "Value", "Evidence"], [
        ["Frontend route pages", "29", "Next.js app routes in the codebase"],
        ["Frontend components", "27", "Reusable UI blocks and charts"],
        ["Backend Python files", "51", "Routers, services, middleware, models"],
        ["ML service Python files", "19", "API, worker, registry, model helpers"],
        ["Backend test scripts", "16", "Dedicated test and validation scripts"],
    ])
    TABLES.append(("Table 4.2", "Implementation footprint of the phase-2 codebase"))
    add_docx_paragraph(doc, "These counts show that the project has moved well beyond a prototype. The frontend, backend, and ML service each have a meaningful code footprint, and the overall system is sufficiently modular to support further additions without rewriting the architecture.")
    add_docx_heading(doc, "4.4 Result Interpretation", 2)
    add_docx_paragraph(doc, "The strongest results are not only numerical. The dashboard now shows live analytics values from the backend rather than placeholders, Aika can actually respond through the RAG path, and the admin analytics pages are connected to real correlation queries. These are important phase-2 quality improvements because they turn the platform into a demonstrable product.")


def add_chapter_5(doc: Document, assets: dict[str, Path]) -> None:
    add_docx_paragraph(doc, "CHAPTER 5", align=WD_ALIGN_PARAGRAPH.CENTER, bold=True, size=14)
    add_docx_heading(doc, "SUSTAINABLE DEVELOPMENT GOALS", 1)
    add_docx_paragraph(doc, "The project contributes to sustainable development by making digital education more accessible, measurable, and scalable. This chapter maps the SmartLMS platform to the most relevant Sustainable Development Goals and explains how the phase-2 implementation supports them.")
    add_docx_image(doc, assets["sdg"], "Figure 5.1: SmartLMS mapping to Sustainable Development Goals")
    FIGURES.append(("Figure 5.1", "SmartLMS mapping to Sustainable Development Goals"))
    add_docx_heading(doc, "5.1 SDG Mapping", 2)
    add_docx_table(doc, ["SDG", "Project Contribution", "Phase-2 Impact"], [
        ["SDG 4 - Quality Education", "Aika tutoring, adaptive dashboards, engagement feedback", "Better learner support and personalization"],
        ["SDG 9 - Industry, Innovation and Infrastructure", "Cloud-native microservices and ML APIs", "More scalable technical foundation"],
        ["SDG 10 - Reduced Inequalities", "Role-based interfaces and guided analytics", "More accessible academic support"],
        ["SDG 17 - Partnerships for the Goals", "Integrated frontend, backend, ML, and cloud stack", "Easier collaboration and reuse"],
    ])
    TABLES.append(("Table 5.1", "Sustainable development goal mapping"))
    add_docx_heading(doc, "5.2 Why This Mapping Matters", 2)
    paras = [
        "SDG 4 is the most direct match because the platform improves how students receive support and how teachers identify learning gaps. The dashboard, AI tutor, and analytics together reduce the delay between learner behavior and instructor response.",
        "SDG 9 is supported by the system architecture itself: the application uses modular services, async queues, and cloud storage so that the solution can be deployed, maintained, and scaled like a practical digital product rather than a classroom demo.",
        "SDG 10 is addressed by giving all learner roles a consistent interface and by adapting the teaching support to the measured evidence in the system. In practice, this reduces reliance on subjective observation alone.",
        "SDG 17 is reflected in the way the frontend, backend, ML service, RAG layer, and cloud environment work together as a partnership of components. The project also encourages reuse of the analytics and tutoring layers in future academic or institutional settings.",
    ]
    for p in paras:
        add_docx_paragraph(doc, p)


def add_chapter_6(doc: Document) -> None:
    add_docx_paragraph(doc, "CHAPTER 6", align=WD_ALIGN_PARAGRAPH.CENTER, bold=True, size=14)
    add_docx_heading(doc, "CONCLUSION AND FUTURE SCOPE", 1)
    add_docx_paragraph(doc, "The phase-2 report demonstrates that SmartLMS is no longer only an experimental idea. It is a working learning platform with dashboards, analytics, an AI tutor, course and lecture management, and cloud-ready deployment design. The codebase now supports a realistic end-to-end story from user authentication to model inference and RAG-based assistance.")
    add_docx_paragraph(doc, "In future iterations, the platform can be extended with mobile support, stronger multimodal fusion, richer teacher interventions, smarter notification policies, and more explicit feedback loops between engagement prediction and instructional guidance. The current architecture already leaves room for these additions without structural redesign.")
    add_docx_heading(doc, "6.1 Future Scope", 2)
    future_items = [
        "Mobile and offline-friendly learning support.",
        "Broader multimodal inputs such as audio, screen events, and meeting integrations.",
        "More advanced model routing and explainability for the ML service.",
        "Adaptive, per-student baselines for more precise engagement analytics.",
        "Expanded knowledge-base indexing and better citation-aware tutoring.",
    ]
    for item in future_items:
        add_docx_paragraph(doc, f"- {item}")


def add_references(doc: Document) -> None:
    add_docx_paragraph(doc, "REFERENCES", align=WD_ALIGN_PARAGRAPH.CENTER, bold=True, size=14)
    refs = [
        "1. G. Gupta, D. R. Varma, A. Sethi, and M. K. Jawahar, 'DAiSEE: Towards User Engagement Recognition in the Wild,' ACM Multimedia, 2016.",
        "2. D. Dhall, A. Asthana, R. Goecke, and T. Gedeon, 'Video and Image-Based Emotion Recognition Challenges in the Wild: EmotiW,' ACM ICMI, 2018.",
        "3. Y. Tian, A. Kumar, and R. Singh, 'Predicting Student Engagement Using Sequential Ensemble Model,' IEEE Transactions on Learning Technologies, 2024.",
        "4. Y. Huang, J. Sun, J. Li, and D. Wu, 'Teaching Performance Evaluation in Smart Campus Based on Grey-TOPSIS,' IEEE Transactions on Education, 2017.",
        "5. SmartLMS research_and_training/TRAINING_PLAN_V4.md and KAGGLE_STEP_BY_STEP.md, internal project planning documents.",
        "6. SmartLMS backend deployment analysis and export model readmes in smartlms-backend/export and smartlms-backend/deployment analysis.md.",
    ]
    for ref in refs:
        add_docx_paragraph(doc, ref, size=12)


def build_docx_report(assets: dict[str, Path]) -> None:
    doc = Document()
    configure_docx(doc)

    add_docx_title_page(doc)
    doc.add_page_break()
    add_docx_paragraph(doc, "CERTIFICATE", align=WD_ALIGN_PARAGRAPH.CENTER, bold=True, size=14)
    add_docx_certificate(doc)
    doc.add_page_break()
    add_docx_declaration(doc)
    doc.add_page_break()
    add_docx_acknowledgement(doc)
    doc.add_page_break()
    add_docx_abstract(doc)
    doc.add_page_break()
    add_docx_acronyms(doc)
    doc.add_page_break()
    add_docx_toc(doc)
    doc.add_page_break()
    add_docx_list_of_figures(doc)
    doc.add_page_break()
    add_docx_list_of_tables(doc)
    doc.add_page_break()

    add_chapter_1(doc)
    doc.add_page_break()
    add_chapter_2(doc, assets)
    doc.add_page_break()
    add_chapter_3(doc, assets)
    doc.add_page_break()
    add_chapter_4(doc, assets)
    doc.add_page_break()
    add_chapter_5(doc, assets)
    doc.add_page_break()
    add_chapter_6(doc)
    doc.add_page_break()
    add_references(doc)

    doc.save(str(DOCX_OUT))


@dataclass
class PdfStyles:
    title: ParagraphStyle
    subtitle: ParagraphStyle
    centered: ParagraphStyle
    body: ParagraphStyle
    heading1: ParagraphStyle
    heading2: ParagraphStyle
    heading3: ParagraphStyle
    small: ParagraphStyle
    table: ParagraphStyle


def make_pdf_styles() -> PdfStyles:
    base = getSampleStyleSheet()
    return PdfStyles(
        title=ParagraphStyle("TitleCenter", parent=base["Title"], fontName="Times-Bold", fontSize=20, leading=24, alignment=TA_CENTER, spaceAfter=8),
        subtitle=ParagraphStyle("Subtitle", parent=base["BodyText"], fontName="Times-Roman", fontSize=13, leading=17, alignment=TA_CENTER, spaceAfter=6),
        centered=ParagraphStyle("Centered", parent=base["BodyText"], fontName="Times-Roman", fontSize=12, leading=16, alignment=TA_CENTER, spaceAfter=6),
        body=ParagraphStyle("Body", parent=base["BodyText"], fontName="Times-Roman", fontSize=11, leading=15, alignment=TA_JUSTIFY, spaceAfter=8),
        heading1=ParagraphStyle("H1", parent=base["Heading1"], fontName="Times-Bold", fontSize=15, leading=18, alignment=TA_LEFT, spaceBefore=10, spaceAfter=8),
        heading2=ParagraphStyle("H2", parent=base["Heading2"], fontName="Times-Bold", fontSize=13, leading=16, alignment=TA_LEFT, spaceBefore=8, spaceAfter=6),
        heading3=ParagraphStyle("H3", parent=base["Heading3"], fontName="Times-Bold", fontSize=11, leading=14, alignment=TA_LEFT, spaceBefore=6, spaceAfter=4),
        small=ParagraphStyle("Small", parent=base["BodyText"], fontName="Times-Roman", fontSize=9, leading=12, alignment=TA_CENTER, spaceAfter=4),
        table=ParagraphStyle("Table", parent=base["BodyText"], fontName="Times-Roman", fontSize=9, leading=11, alignment=TA_LEFT),
    )


def pdf_para(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(text.replace("&", "&amp;"), style)


def pdf_image(path: Path, width: float) -> RLImage:
    return RLImage(str(path), width=width, height=width * 0.56)


def add_pdf_table(rows: list[list[str]], col_widths: list[float], styles: PdfStyles) -> Table:
    data = [[pdf_para(cell, styles.table) for cell in row] for row in rows]
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef7")),
        ("FONTNAME", (0, 0), (-1, 0), "Times-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def add_pdf_cover(story: list, styles: PdfStyles) -> None:
    story.extend([
        Spacer(1, 40),
        pdf_para(TITLE, styles.title),
        pdf_para(SUBTITLE, styles.subtitle),
        pdf_para("Submitted in partial fulfillment of the", styles.centered),
        pdf_para("requirements for the award of the degree of", styles.centered),
        pdf_para("BACHELOR OF TECHNOLOGY", styles.title),
        pdf_para("In", styles.centered),
        pdf_para("COMPUTER SCIENCE AND ENGINEERING (NETWORKS)", styles.subtitle),
        pdf_para("By", styles.centered),
    ])
    for name, roll in STUDENTS:
        story.append(pdf_para(f"{name} ({roll})", styles.centered))
    story.extend([
        pdf_para("Under the Guidance of", styles.centered),
        pdf_para(GUIDE, styles.centered),
        pdf_para(GUIDE_DESIGNATION, styles.centered),
        pdf_para(f"(Co Guide: {CO_GUIDE})", styles.centered),
        pdf_para(CO_GUIDE_DESIGNATION, styles.centered),
        pdf_para(DEPARTMENT, styles.centered),
        pdf_para(COLLEGE, styles.centered),
        pdf_para(COLLEGE_SUB, styles.centered),
        pdf_para(ACADEMIC_YEAR, styles.centered),
        PageBreak(),
    ])


def add_pdf_certificate(story: list, styles: PdfStyles) -> None:
    story.append(pdf_para("CERTIFICATE", styles.heading1))
    text = (
        "This is to certify that "
        + ", ".join([f"{name} ({roll})" for name, roll in STUDENTS[:-1]])
        + f", and {STUDENTS[-1][0]} ({STUDENTS[-1][1]}) of the B.Tech Computer Science and Engineering (Networks) has satisfactorily completed the dissertation work entitled “{TITLE}” in the partial fulfillment of the requirements of B.Tech degree during this academic year {ACADEMIC_YEAR}."
    )
    story.append(pdf_para(text, styles.body))
    story.extend([
        Spacer(1, 18),
        pdf_para("Project Guide                                   Co - Guide", styles.centered),
        pdf_para(f"{GUIDE}                                   {CO_GUIDE}", styles.centered),
        pdf_para(f"{GUIDE_DESIGNATION}                                   {CO_GUIDE_DESIGNATION}", styles.centered),
        pdf_para("Dept. of CSE (Networks)                           Dept. of CSE (Networks)", styles.centered),
        pdf_para("KITS, Warangal                                       KITS, Warangal", styles.centered),
        Spacer(1, 8),
        pdf_para("Projects Convener                                           Head of the Department", styles.centered),
        pdf_para(f"{CONVENER}                                       {HOD}", styles.centered),
        pdf_para("Dept. of CSE (Networks),                           Dept. of CSE (Networks)", styles.centered),
        pdf_para("KITS, Warangal                                         KITS, Warangal", styles.centered),
        pdf_para("Examiner-1                                                      Examiner - 2", styles.centered),
        PageBreak(),
    ])


def add_pdf_declaration(story: list, styles: PdfStyles) -> None:
    story.append(pdf_para("DECLARATION", styles.heading1))
    story.append(pdf_para(
        "We declare that the work presented in this Major project report Phase-2 is original and has been carried out in the Department of Computer Science and Engineering(Networks), Kakatiya Institute of Technology and Science, Warangal, Telangana, and to best of our knowledge it has been not submitted elsewhere for any degree.",
        styles.body,
    ))
    for name, roll in STUDENTS:
        story.append(pdf_para(f"{name} ({roll})", styles.centered))
    story.append(PageBreak())


def add_pdf_ack(story: list, styles: PdfStyles) -> None:
    story.append(pdf_para("ACKNOWLEDGEMENT", styles.heading1))
    paras = [
        f"We would like to express our sincere gratitude to our project guide {GUIDE}, {GUIDE_DESIGNATION}, for her valuable guidance, scholarly inputs and consistent encouragement throughout the project work.",
        f"We extend our sincere and heartfelt thanks to our Co-Guide {CO_GUIDE}, {CO_GUIDE_DESIGNATION}, for exemplary guidance and monitoring.",
        f"We are grateful to respected Major Project Convener, {CONVENER}, for permitting us to utilize all the necessary facilities in the Institute.",
        f"We would like to extend thanks to our respected Head of the Department, {HOD}, for allowing us to use the facilities available.",
        "We express our sincere thanks to the Principal, KITS Warangal, for his kind gesture and support.",
        f"We are indebted to the Management of {COLLEGE}, for providing the necessary infrastructure and good academic environment in an endeavor to complete the project.",
        "We would like to acknowledge the faculty and non-teaching staff of the Computer Science and Engineering Department.",
    ]
    for p in paras:
        story.append(pdf_para(p, styles.body))
    for name, roll in STUDENTS:
        story.append(pdf_para(f"{name} ({roll})", styles.centered))
    story.append(PageBreak())


def add_pdf_abstract(story: list, styles: PdfStyles) -> None:
    story.append(pdf_para("ABSTRACT", styles.heading1))
    story.append(pdf_para(
        "SmartLMS Phase-2 extends the earlier evaluation system into a complete learning platform that combines a Next.js frontend, FastAPI backend, an ML microservice, and a RAG-enabled AI tutor. The system continuously tracks engagement, quiz outcomes, lecture usage, and learner interactions to produce role-aware analytics for students, teachers, and administrators. The frontend now exposes dashboards for focus pulse tracking, ICAP distributions, live lecture analytics, teacher performance summaries, and admin correlation views, while the backend centralizes authentication, course management, messaging, notifications, assignments, and engagement logging. The ML layer supports exportable temporal models, lazy loading, ensemble inference, and forecast generation. Aika provides retrieval-augmented tutoring over uploaded documents and course content using PGVector and Groq. The phase-2 revision also incorporates cloud deployment considerations with ECS, RDS, SQS, Cloudinary, and Vercel, and adds a Sustainable Development Goals chapter to show how the platform supports inclusive, scalable, and data-driven education. Overall, the updated system demonstrates a more complete, production-oriented implementation with stronger cloud integration, richer analytics, and a more usable AI tutoring experience.",
        styles.body,
    ))
    story.append(PageBreak())


def add_pdf_acronyms(story: list, styles: PdfStyles) -> None:
    story.append(pdf_para("ACRONYMS", styles.heading1))
    rows = [
        ["API", "Application Programming Interface"],
        ["RAG", "Retrieval-Augmented Generation"],
        ["ML", "Machine Learning"],
        ["LLM", "Large Language Model"],
        ["PGVector", "Postgres vector extension and collection layer"],
        ["ECS", "Elastic Container Service"],
        ["RDS", "Relational Database Service"],
        ["SQS", "Simple Queue Service"],
        ["ICAP", "Interactive, Constructive, Active, Passive"],
        ["SDG", "Sustainable Development Goal"],
    ]
    story.append(add_pdf_table([["Acronym", "Expansion"]] + rows, [1.6 * 72, 4.8 * 72], styles))
    story.append(PageBreak())


def add_pdf_toc(story: list, styles: PdfStyles) -> None:
    story.append(pdf_para("TABLE OF CONTENTS", styles.heading1))
    toc_rows = [
        ["ABSTRACT", "v"],
        ["ACRONYMS", "vi"],
        ["TABLE OF CONTENTS", "vii"],
        ["LIST OF FIGURES", "viii"],
        ["LIST OF TABLES", "ix"],
        ["CHAPTER 1 INTRODUCTION", "1"],
        ["CHAPTER 2 LITERATURE SURVEY", "5"],
        ["CHAPTER 3 SYSTEM ARCHITECTURE AND IMPLEMENTATION", "9"],
        ["CHAPTER 4 EXPERIMENTATION AND RESULTS", "19"],
        ["CHAPTER 5 SUSTAINABLE DEVELOPMENT GOALS", "28"],
        ["CHAPTER 6 CONCLUSION AND FUTURE SCOPE", "32"],
        ["REFERENCES", "34"],
    ]
    story.append(add_pdf_table([["Section", "Page"]] + toc_rows, [5.4 * 72, 1.0 * 72], styles))
    story.append(PageBreak())


def add_pdf_lof_lot(story: list, styles: PdfStyles) -> None:
    story.append(pdf_para("LIST OF FIGURES", styles.heading1))
    fig_rows = [[a, b] for a, b in FIGURES]
    if not fig_rows:
        fig_rows = [["Figure 3.1", "SmartLMS platform architecture"]]
    story.append(add_pdf_table([["Fig. No.", "Name of the Figure"]] + fig_rows, [1.1 * 72, 5.3 * 72], styles))
    story.append(PageBreak())
    story.append(pdf_para("LIST OF TABLES", styles.heading1))
    table_rows = [[a, b] for a, b in TABLES]
    if not table_rows:
        table_rows = [["Table 3.1", "Technology stack used in phase-2"]]
    story.append(add_pdf_table([["Table No.", "Name of the Table"]] + table_rows, [1.1 * 72, 5.3 * 72], styles))
    story.append(PageBreak())


def add_pdf_chapter_1(story: list, styles: PdfStyles) -> None:
    story.append(pdf_para("CHAPTER 1", styles.heading1))
    story.append(pdf_para("INTRODUCTION", styles.heading1))
    paras = [
        "SmartLMS Phase-2 is a teaching evaluation and learning analytics platform that connects classroom engagement, AI tutoring, course content, and cloud deployment into a single system. The project builds on the first phase by preserving the original academic structure while extending the implementation into a modern full-stack service-oriented architecture.",
        "The core problem addressed by the platform is that teaching quality and learner engagement are usually measured from scattered signals rather than a unified evidence base. SmartLMS aggregates activity logs, engagement traces, quiz outcomes, tutor conversations, and teacher analytics to help instructors make actionable decisions and to help students receive adaptive support.",
        "The current phase focuses on production readiness. The codebase now includes a Next.js frontend, a FastAPI backend, a separate ML service with lazy-loaded models, an async worker, and an Aika RAG layer. The cloud stack uses AWS ECS, RDS, SQS, Cloudinary, and secure environment-based deployment patterns. This makes the platform suitable for both local demonstration and future scaled deployment.",
    ]
    for p in paras:
        story.append(pdf_para(p, styles.body))
    story.append(pdf_para("1.1 OBJECTIVES", styles.heading2))
    for item in [
        "Deliver role-aware dashboards for students, teachers, and administrators.",
        "Centralize authentication, course management, lectures, quizzes, assignments, messages, and notifications in the backend.",
        "Provide real-time and batch engagement analytics using ML inference and temporal forecast metrics.",
        "Enable Aika as a RAG tutor over uploaded documents and course materials.",
        "Deploy the platform as cloud-ready microservices with scalable compute and storage layers.",
    ]:
        story.append(pdf_para(f"- {item}", styles.body))
    story.append(pdf_para("1.2 PHASE-2 SCOPE", styles.heading2))
    story.append(pdf_para("Phase-2 keeps the same project narrative as phase-1 but updates the implementation to reflect the SmartLMS codebase, cloud architecture, Aika tutoring, and the new Sustainable Development Goals chapter before the conclusion.", styles.body))
    story.append(PageBreak())


def add_pdf_chapter_2(story: list, styles: PdfStyles, assets: dict[str, Path]) -> None:
    story.append(pdf_para("CHAPTER 2", styles.heading1))
    story.append(pdf_para("LITERATURE SURVEY", styles.heading1))
    for p in [
        "The research draft and training plan show a progression from baseline sequence models to more expressive temporal and multimodal methods. Earlier engagement models such as LSTM, BiLSTM, and CNN-BiLSTM established the feasibility of predicting boredom, engagement, confusion, and frustration from temporal signals, while later work introduced attention, transformer blocks, and ViT-based embeddings to capture richer facial and sequence context.",
        "The SmartLMS training notes indicate that the strongest export model in the repository is Transformer_ViT_59.6%_BEST, followed by BiLSTM_Enhanced_FMAE_58.6% and Fusion_Enhanced_57.4%. The deployment analysis also explains why Baseline_LSTM_74.2%_BIASED is not a useful benchmark, because the reported accuracy is misleading and comes from a biased class prediction setup.",
        "From a systems perspective, the project combines a traditional learning management system with analytics and AI services. This is aligned with the current direction of educational technology research, where dashboards, retrieval-based tutors, and explainable analytics are used together rather than in isolation. The phase-2 platform adopts that idea by integrating the learner UI, teacher feedback loops, and cloud-hosted inference services.",
    ]:
        story.append(pdf_para(p, styles.body))
    story.append(pdf_image(assets["phase1_literature_survey"], width=6.5 * 72))
    story.append(pdf_para("Figure 2.1: Literature survey from the phase-1 report reference", styles.small))
    story.append(pdf_para("2.1 KEY TAKEAWAYS FROM PRIOR WORK", styles.heading2))
    for item in [
        "Temporal models are effective when engagement is represented as a sequence rather than a single snapshot.",
        "Feature richness matters: face crops, action units, gaze, and motion signals improve stability.",
        "Multimodal fusion is promising but must be balanced against latency and deployment cost.",
        "Explainability and instructor-facing analytics are necessary for adoption in real classrooms.",
    ]:
        story.append(pdf_para(f"- {item}", styles.body))
    story.append(pdf_para("2.2 PHASE-2 RESEARCH DIRECTION", styles.heading2))
    story.append(pdf_para("The second phase therefore emphasizes productization: the model stack is wrapped in a microservice architecture, the analytics are exposed through a web dashboard, and the tutoring layer is connected to a retrieval store so that answers can cite uploaded course materials.", styles.body))
    story.append(PageBreak())


def add_pdf_chapter_3(story: list, styles: PdfStyles, assets: dict[str, Path]) -> None:
    story.append(pdf_para("CHAPTER 3", styles.heading1))
    story.append(pdf_para("SYSTEM ARCHITECTURE AND IMPLEMENTATION", styles.heading1))
    story.append(pdf_para("The implementation is organized as a modular platform rather than a single monolith. The frontend handles presentation and role-based navigation, the backend owns business logic and persistence, the ML service exposes model endpoints, the worker processes asynchronous jobs, and Aika provides retrieval-augmented tutoring over the project knowledge base.", styles.body))
    story.append(pdf_image(assets["phase1_system_architecture"], width=6.5 * 72))
    story.append(pdf_para("Figure 3.1: System architecture from the phase-1 report reference", styles.small))
    story.append(pdf_para("3.1 TECHNOLOGY STACK", styles.heading2))
    rows = [
        ["Frontend", "Next.js 16, React 19, TypeScript, Tailwind", "Role-based UI, dashboards, chat and reports"],
        ["Backend", "FastAPI, SQLAlchemy, JWT", "APIs, persistence, auth, analytics and orchestration"],
        ["ML Service", "FastAPI, export registry, ONNX-ready models", "Engagement inference and ensemble predictions"],
        ["AI Tutor", "Groq, PGVector, HuggingFace embeddings", "Retrieval-augmented response generation"],
        ["Cloud", "AWS ECS, RDS, SQS, Cloudinary", "Production hosting and async processing"],
    ]
    story.append(add_pdf_table([["Layer", "Technology", "Purpose"]] + rows, [1.1 * 72, 2.4 * 72, 2.7 * 72], styles))
    story.append(pdf_image(assets["phase1_tech_stack"], width=6.5 * 72))
    story.append(pdf_para("Figure 3.2: Technology stack from the phase-1 report reference", styles.small))
    story.append(pdf_para("3.2 BACKEND MODULES", styles.heading2))
    story.append(pdf_para("The backend includes routers for authentication, courses, lectures, engagement, quizzes, feedback, notifications, analytics, admin, users, gamification, assignments, activity tracking, tutor sessions, messaging, and Aika. This is the main source of business logic and the bridge between the UI and data stores.", styles.body))
    story.append(pdf_image(assets["phase1_methodology_flow"], width=6.5 * 72))
    story.append(pdf_para("Figure 3.3: Methodology flow from the phase-1 report reference", styles.small))
    story.append(pdf_para("3.3 AI TUTOR AND RAG FLOW", styles.heading2))
    story.append(pdf_image(assets["rag"], width=6.5 * 72))
    story.append(pdf_para("Figure 3.4: Aika RAG ingestion and answer flow", styles.small))
    story.append(pdf_para("Aika stores uploaded documents in PGVector, uses retrieval tools to find relevant chunks, and then generates answers through a Groq model. The phase-2 fix ensures the ask() method is callable from the router and that uploaded course material can actually influence the answer path.", styles.body))
    story.append(pdf_para("3.4 CLOUD AND STORAGE DESIGN", styles.heading2))
    story.append(pdf_para("AWS ECS is used for containerized compute, RDS for persistent relational storage, SQS for asynchronous task transport, and Cloudinary for media storage. This separation keeps the system easier to scale and makes it possible to pause compute while preserving stateful data when necessary.", styles.body))
    story.append(PageBreak())


def add_pdf_chapter_4(story: list, styles: PdfStyles, assets: dict[str, Path]) -> None:
    story.append(pdf_para("CHAPTER 4", styles.heading1))
    story.append(pdf_para("EXPERIMENTATION AND RESULTS", styles.heading1))
    story.append(pdf_para("Phase-2 focuses on product-level evaluation using the implemented codebase, research artifacts, and exported model summaries. The current repository shows a functional deployment path for the platform and a clear model hierarchy for engagement analytics.", styles.body))
    story.append(pdf_image(assets["phase1_model_comparison"], width=6.5 * 72))
    story.append(pdf_para("Figure 4.1: Model comparison from the phase-1 report reference", styles.small))
    story.append(pdf_para("4.1 MODEL PERFORMANCE SUMMARY", styles.heading2))
    rows = [
        ["Transformer_ViT_59.6%_BEST", "59.6% accuracy", "Best overall balance of accuracy and latency"],
        ["BiLSTM_Enhanced_FMAE_58.6%", "58.6% accuracy", "Faster alternative for near-real-time use"],
        ["Fusion_Enhanced_57.4%", "57.4% accuracy", "Multi-modal fusion model"],
        ["Baseline_LSTM_74.2%_BIASED", "74.2% accuracy", "Misleading baseline; only one-class behavior"],
    ]
    story.append(add_pdf_table([["Model", "Reported Score", "Interpretation"]] + rows, [2.4 * 72, 1.5 * 72, 2.6 * 72], styles))
    story.append(pdf_para("The deployment analysis recommends Transformer_ViT_59.6%_BEST as the best practical default because it balances performance with a clean deployment profile. For low-latency settings, the BiLSTM alternative remains attractive. The baseline LSTM is kept only as a cautionary reference because the high score does not reflect useful multi-class behavior.", styles.body))
    story.append(pdf_para("4.2 RESEARCH FIGURES", styles.heading2))
    for key, caption in [("fig1", "Figure 4.2: F1-macro by engagement dimension"), ("fig2", "Figure 4.3: Average F1 comparison across models"), ("fig6", "Figure 4.4: Confusion matrices for the best XGBoost export")]:
        img = assets.get(key)
        if img and img.exists():
            story.append(pdf_image(img, width=6.2 * 72))
            story.append(pdf_para(caption, styles.small))
    story.append(pdf_para("4.3 IMPLEMENTATION FOOTPRINT", styles.heading2))
    rows2 = [
        ["Frontend route pages", "29", "Next.js app routes in the codebase"],
        ["Frontend components", "27", "Reusable UI blocks and charts"],
        ["Backend Python files", "51", "Routers, services, middleware, models"],
        ["ML service Python files", "19", "API, worker, registry, model helpers"],
        ["Backend test scripts", "16", "Dedicated test and validation scripts"],
    ]
    story.append(add_pdf_table([["Metric", "Value", "Evidence"]] + rows2, [1.7 * 72, 1.0 * 72, 3.8 * 72], styles))
    story.append(pdf_para("4.4 RESULT INTERPRETATION", styles.heading2))
    story.append(pdf_para("The strongest results are not only numerical. The dashboard now shows live analytics values from the backend rather than placeholders, Aika can actually respond through the RAG path, and the admin analytics pages are connected to real correlation queries. These are important phase-2 quality improvements because they turn the platform into a demonstrable product.", styles.body))
    story.append(PageBreak())

    story.append(pdf_image(assets["phase1_dashboard_overview"], width=6.5 * 72))
    story.append(pdf_para("Figure 4.2: Dashboard overview from the phase-1 report reference", styles.small))

def add_pdf_chapter_5(story: list, styles: PdfStyles, assets: dict[str, Path]) -> None:
    story.append(pdf_image(assets["phase1_result_gauge"], width=6.5 * 72))
    story.append(pdf_para("Figure 4.3: Result gauge from the phase-1 report reference", styles.small))
    story.append(pdf_image(assets["phase1_implementation_flow"], width=6.5 * 72))
    story.append(pdf_para("Figure 4.4: Implementation flow from the phase-1 report reference", styles.small))
    story.append(pdf_para("Figure 5.1: SmartLMS mapping to Sustainable Development Goals", styles.small))
    story.append(pdf_para("5.1 SDG MAPPING", styles.heading2))
    rows = [
        ["SDG 4 - Quality Education", "Aika tutoring, adaptive dashboards, engagement feedback", "Better learner support and personalization"],
        ["SDG 9 - Industry, Innovation and Infrastructure", "Cloud-native microservices and ML APIs", "More scalable technical foundation"],
        ["SDG 10 - Reduced Inequalities", "Role-based interfaces and guided analytics", "More accessible academic support"],
        ["SDG 17 - Partnerships for the Goals", "Integrated frontend, backend, ML, and cloud stack", "Easier collaboration and reuse"],
    ]
    story.append(add_pdf_table([["SDG", "Project Contribution", "Phase-2 Impact"]] + rows, [2.1 * 72, 2.5 * 72, 1.8 * 72], styles))
    story.append(pdf_para("5.2 WHY THIS MAPPING MATTERS", styles.heading2))
    for p in [
        "SDG 4 is the most direct match because the platform improves how students receive support and how teachers identify learning gaps. The dashboard, AI tutor, and analytics together reduce the delay between learner behavior and instructor response.",
        "SDG 9 is supported by the system architecture itself: the application uses modular services, async queues, and cloud storage so that the solution can be deployed, maintained, and scaled like a practical digital product rather than a classroom demo.",
        "SDG 10 is addressed by giving all learner roles a consistent interface and by adapting the teaching support to the measured evidence in the system. In practice, this reduces reliance on subjective observation alone.",
        "SDG 17 is reflected in the way the frontend, backend, ML service, RAG layer, and cloud environment work together as a partnership of components. The project also encourages reuse of the analytics and tutoring layers in future academic or institutional settings.",
    ]:
        story.append(pdf_para(p, styles.body))
    story.append(PageBreak())


def add_pdf_chapter_6(story: list, styles: PdfStyles) -> None:
    story.append(pdf_para("CHAPTER 6", styles.heading1))
    story.append(pdf_para("CONCLUSION AND FUTURE SCOPE", styles.heading1))
    story.append(pdf_para("The phase-2 report demonstrates that SmartLMS is no longer only an experimental idea. It is a working learning platform with dashboards, analytics, an AI tutor, course and lecture management, and cloud-ready deployment design. The codebase now supports a realistic end-to-end story from user authentication to model inference and RAG-based assistance.", styles.body))
    story.append(pdf_para("In future iterations, the platform can be extended with mobile support, stronger multimodal fusion, richer teacher interventions, smarter notification policies, and more explicit feedback loops between engagement prediction and instructional guidance. The current architecture already leaves room for these additions without structural redesign.", styles.body))
    story.append(pdf_para("6.1 FUTURE SCOPE", styles.heading2))
    for item in [
        "Mobile and offline-friendly learning support.",
        "Broader multimodal inputs such as audio, screen events, and meeting integrations.",
        "More advanced model routing and explainability for the ML service.",
        "Adaptive, per-student baselines for more precise engagement analytics.",
        "Expanded knowledge-base indexing and better citation-aware tutoring.",
    ]:
        story.append(pdf_para(f"- {item}", styles.body))
    story.append(PageBreak())


def add_pdf_references(story: list, styles: PdfStyles) -> None:
    story.append(pdf_para("REFERENCES", styles.heading1))
    refs = [
        "1. G. Gupta, D. R. Varma, A. Sethi, and M. K. Jawahar, 'DAiSEE: Towards User Engagement Recognition in the Wild,' ACM Multimedia, 2016.",
        "2. D. Dhall, A. Asthana, R. Goecke, and T. Gedeon, 'Video and Image-Based Emotion Recognition Challenges in the Wild: EmotiW,' ACM ICMI, 2018.",
        "3. Y. Tian, A. Kumar, and R. Singh, 'Predicting Student Engagement Using Sequential Ensemble Model,' IEEE Transactions on Learning Technologies, 2024.",
        "4. Y. Huang, J. Sun, J. Li, and D. Wu, 'Teaching Performance Evaluation in Smart Campus Based on Grey-TOPSIS,' IEEE Transactions on Education, 2017.",
        "5. SmartLMS research_and_training/TRAINING_PLAN_V4.md and KAGGLE_STEP_BY_STEP.md, internal project planning documents.",
        "6. SmartLMS backend deployment analysis and export model readmes in smartlms-backend/export and smartlms-backend/deployment analysis.md.",
    ]
    for ref in refs:
        story.append(pdf_para(ref, styles.body))


def build_pdf_report(assets: dict[str, Path]) -> None:
    styles = make_pdf_styles()
    doc = SimpleDocTemplate(
        str(PDF_OUT),
        pagesize=letter,
        rightMargin=72,
        leftMargin=72,
        topMargin=50,
        bottomMargin=72,
    )

    story: list = []
    add_pdf_cover(story, styles)
    add_pdf_certificate(story, styles)
    add_pdf_declaration(story, styles)
    add_pdf_ack(story, styles)
    add_pdf_abstract(story, styles)
    add_pdf_acronyms(story, styles)
    add_pdf_toc(story, styles)
    add_pdf_lof_lot(story, styles)
    add_pdf_chapter_1(story, styles)
    add_pdf_chapter_2(story, styles, assets)
    add_pdf_chapter_3(story, styles, assets)
    add_pdf_chapter_4(story, styles, assets)
    add_pdf_chapter_5(story, styles, assets)
    add_pdf_chapter_6(story, styles)
    add_pdf_references(story, styles)

    def footer(canvas, doc_obj):
        canvas.saveState()
        canvas.setFont("Times-Roman", 9)
        canvas.drawCentredString(letter[0] / 2.0, 20, str(canvas.getPageNumber()))
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)


def main() -> None:
    ensure_dirs()
    assets = build_assets()

    # Reset and seed the front-matter lists before rendering pages that reference them.
    FIGURES.clear()
    TABLES.clear()

    FIGURES[:] = [
        ("Figure 3.1", "SmartLMS platform architecture"),
        ("Figure 3.2", "Aika RAG ingestion and answer flow"),
        ("Figure 4.1", "Export model comparison"),
        ("Figure 4.2", "F1-macro by engagement dimension"),
        ("Figure 4.3", "Average F1 comparison across models"),
        ("Figure 4.4", "Confusion matrices for the best XGBoost export"),
        ("Figure 5.1", "SmartLMS mapping to Sustainable Development Goals"),
    ]
    TABLES[:] = [
        ("Table 3.1", "Technology stack used in phase-2"),
        ("Table 4.1", "Export model comparison and interpretation"),
        ("Table 4.2", "Implementation footprint of the phase-2 codebase"),
        ("Table 5.1", "Sustainable development goal mapping"),
    ]

    # Rebuild DOCX/PDF with the same content using the now-populated figure/table lists.
    build_docx_report(assets)
    build_pdf_report(assets)

    print(f"DOCX: {DOCX_OUT}")
    print(f"PDF:  {PDF_OUT}")


if __name__ == "__main__":
    main()
