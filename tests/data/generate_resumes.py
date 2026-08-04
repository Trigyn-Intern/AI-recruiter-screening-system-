"""Generate the sample resume PDFs used by the scenario matrix.

Each scenario expects a few resume files in ``tests/data/resumes``. This script
uses reportlab to write four realistic-but-synthetic candidates: a strong
Python/ML profile, a data engineer, a frontend engineer, and a junior
candidate. Run it once locally with ``python tests/data/generate_resumes.py``.
"""


import os
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas


RESUMES_DIR = os.path.join(os.path.dirname(__file__), "resumes")


def _draw_block(c, lines, start_y=740):
    """Draw a resume PDF with simple two-column headings and body text."""
    width, _ = LETTER
    text = c.beginText(72, start_y)
    text.setFont("Helvetica", 11)
    for line in lines:
        text.textLine(line)
    c.drawText(text)
    c.showPage()


def _write_resume(name, summary, skills, experience):
    path = os.path.join(RESUMES_DIR, name)
    c = canvas.Canvas(path, pagesize=LETTER)

    c.setFont("Helvetica-Bold", 18)
    c.drawString(72, 760, name.replace("_", " ").replace(".pdf", "").title())
    c.setFont("Helvetica", 10)
    c.drawString(72, 740, summary)

    _draw_block(
        c,
        ["Skills"] + ["- " + s for s in skills],
        start_y=700,
    )

    _draw_block(c, ["Experience"] + experience, start_y=520)

    c.save()
    return path


def main():
    os.makedirs(RESUMES_DIR, exist_ok=True)

    _write_resume(
        "resume_strong_python.pdf",
        "Senior ML engineer with 7 years of Python and deep-learning production experience.",
        [
            "Python",
            "FastAPI",
            "PyTorch",
            "TensorFlow",
            "scikit-learn",
            "FAISS",
            "sentence-transformers",
            "AWS",
            "Docker",
            "Kubernetes",
            "SQL",
            "PostgreSQL",
            "Terraform",
        ],
        [
            "Acme AI - Staff ML Engineer (2021-present)",
            "- Owned the ranking model that powers our recruiter search.",
            "- Built FastAPI inference service handling 4k req/sec on ECS Fargate.",
            "- Cut p99 latency from 900ms to 180ms with FAISS + ONNX optimisation.",
            "- Led migration from TensorFlow 1 to PyTorch 2.",
            "Globex Research - ML Engineer (2018-2021)",
            "- Trained and shipped recommendation models using PyTorch and LightGBM.",
            "- Authored the team's experimentation framework in Python.",
        ],
    )

    _write_resume(
        "resume_data_engineer.pdf",
        "Data engineer with 6 years of experience building batch and streaming pipelines.",
        [
            "Python",
            "SQL",
            "Spark",
            "Kafka",
            "Airflow",
            "dbt",
            "BigQuery",
            "Snowflake",
            "PostgreSQL",
            "AWS",
            "Terraform",
            "Great Expectations",
        ],
        [
            "Initech Data - Senior Data Engineer (2020-present)",
            "- Owns the ingestion layer that lands 4 TB/day into the warehouse.",
            "- Migrated nightly Airflow jobs to dbt + Spark on EMR, cutting cost 38%.",
            "- Introduced data contracts and Great Expectations for top 30 datasets.",
            "Hooli Analytics - Data Engineer (2017-2020)",
            "- Built Kafka + Flink streaming pipelines for product analytics.",
            "- Designed star schema and SCD2 models in Snowflake.",
        ],
    )

    _write_resume(
        "resume_frontend.pdf",
        "Frontend engineer with 6 years of React, TypeScript, and design system experience.",
        [
            "React",
            "TypeScript",
            "Next.js",
            "Tailwind CSS",
            "Redux Toolkit",
            "React Query",
            "Storybook",
            "Vite",
            "Vitest",
            "Playwright",
            "GraphQL",
            "Apollo",
        ],
        [
            "Vandelay UX - Senior Frontend Engineer (2021-present)",
            "- Lead engineer for the recruiter analytics dashboard.",
            "- Built the company's component library in Storybook with Tailwind.",
            "- Improved Lighthouse performance from 54 to 96 on the marketing site.",
            "Pied Piper - Frontend Engineer (2018-2021)",
            "- Shipped React Native features to the iOS and Android consumer apps.",
            "- Owned the migration from REST to Apollo + GraphQL.",
        ],
    )

    _write_resume(
        "resume_junior.pdf",
        "Recent computer science graduate with internship experience.",
        [
            "Python",
            "JavaScript",
            "React",
            "Git",
            "Jupyter",
        ],
        [
            "University of Somewhere - BS Computer Science (2024)",
            "- Coursework in algorithms, distributed systems, and databases.",
            "Brightcove - Software Engineering Intern (Summer 2023)",
            "- Built internal tooling in React and Node.",
            "- Wrote integration tests with pytest.",
        ],
    )

    print("Generated resumes in", RESUMES_DIR)


if __name__ == "__main__":
    main()
