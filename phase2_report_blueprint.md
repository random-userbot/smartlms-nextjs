# SmartLMS Phase-2 Report Blueprint

This document is the source blueprint for the phase-2 official report. It is aligned to the phase-1 report structure in `major project report.pdf` and the external layout reference in `FINAL_EXTERNAL_REPORT_DRFT.pdf`, while updating the project data, figures, and chapter content for SmartLMS phase-2.

## 1. Source References

- Phase-1 report reference: `C:/Users/revan/Downloads/major project report.pdf`
- Layout and structure reference: `C:/Users/revan/Downloads/FINAL_EXTERNAL_REPORT_DRFT.pdf`
- Existing phase-2 generated artifacts:
  - `C:/Users/revan/Downloads/smartlms-version2/phase2_report_output/SmartLMS_Phase2_Report.docx`
  - `C:/Users/revan/Downloads/smartlms-version2/phase2_report_output/SmartLMS_Phase2_Report.pdf`
- Curated phase-1 figure assets extracted from the reference Word report:
  - `C:/Users/revan/Downloads/smartlms-version2/phase2_report_output/assets/phase1_reference/curated/phase1_literature_survey.png`
  - `C:/Users/revan/Downloads/smartlms-version2/phase2_report_output/assets/phase1_reference/curated/phase1_system_architecture.png`
  - `C:/Users/revan/Downloads/smartlms-version2/phase2_report_output/assets/phase1_reference/curated/phase1_tech_stack.png`
  - `C:/Users/revan/Downloads/smartlms-version2/phase2_report_output/assets/phase1_reference/curated/phase1_implementation_flow.png`
  - `C:/Users/revan/Downloads/smartlms-version2/phase2_report_output/assets/phase1_reference/curated/phase1_methodology_flow.png`
  - `C:/Users/revan/Downloads/smartlms-version2/phase2_report_output/assets/phase1_reference/curated/phase1_model_comparison.png`
  - `C:/Users/revan/Downloads/smartlms-version2/phase2_report_output/assets/phase1_reference/curated/phase1_dashboard_overview.png`
  - `C:/Users/revan/Downloads/smartlms-version2/phase2_report_output/assets/phase1_reference/curated/phase1_result_gauge.png`

## 2. Title Page Data

### Report Title

ENHANCING TEACHING EVALUATION IN SMART ENGINEERING CAMPUS

### Subtitle

A report on major project work phase-2

### Degree

BACHELOR OF TECHNOLOGY

### Branch

COMPUTER SCIENCE AND ENGINEERING (NETWORKS)

### Academic Year

2025-2026

### Students

- PURAM REVANTH (B22IN066)
- MOHAMMED FAHAD AHMED (B22IN073)
- MALLADI RAJAVARDHAN REDDY (B22IN093)
- JANAGANI HARSHAVARDHAN (B22IN097)
- AFSHAN (B22IN119)

### Guide and Academic Staff

- Guide: T. Sravanthi
- Designation: Asst. Professor
- Co-Guide: Dr. Kumar Dorthi
- Co-Guide Designation: Asst. Professor
- Projects Convener: Dr. S. Venkatramulu, Assoc. Prof.
- Head of the Department: Dr. V. Shankar, Professor & Head

### Department and College

- Department of Computer Science and Engineering(Networks)
- Kakatiya Institute of Technology and Science, Warangal
- (An Autonomous Institute under Kakatiya University, Warangal)

## 3. Front Matter Order

The report should follow this order:

1. Cover page
2. Certificate
3. Declaration
4. Acknowledgement
5. Abstract
6. Acronyms
7. Table of Contents
8. List of Figures
9. List of Tables
10. Chapter 1: Introduction
11. Chapter 2: Literature Survey
12. Chapter 3: System Architecture and Implementation
13. Chapter 4: Experimentation and Results
14. Chapter 5: Sustainable Development Goals
15. Chapter 6: Conclusion and Future Scope
16. References

## 4. Chapter Blueprint

### Chapter 1: Introduction

Purpose: introduce the SmartLMS phase-2 system, explain the problem, and define the objectives.

Key content:

- SmartLMS phase-2 as a full learning analytics and teaching evaluation platform
- Focus on role-aware dashboards for students, teachers, and administrators
- System scope: frontend, backend, ML service, worker, and Aika RAG
- Production-readiness and cloud deployment emphasis

Subsections:

- 1.1 Objectives
- 1.2 Phase-2 Scope

### Chapter 2: Literature Survey

Purpose: summarize research direction and model progression behind the engagement analytics stack.

Key content:

- Baseline sequence models: LSTM, BiLSTM, CNN-BiLSTM
- Improved methods: attention, transformers, ViT, multimodal fusion
- Relevance of explainable analytics and retrieval-based tutoring in education
- Phase-2 direction toward productized deployment

Subsections:

- 2.1 Key Takeaways from Prior Work
- 2.2 Phase-2 Research Direction

### Chapter 3: System Architecture and Implementation

Purpose: document the actual codebase architecture and implementation layers.

Key content:

- Next.js frontend for role-based UI and analytics pages
- FastAPI backend for auth, courses, lectures, engagement, quizzes, feedback, notifications, admin, users, gamification, assignments, activity, tutor, messaging, and Aika
- Separate ML service for inference and export model registry
- AWS-ready cloud stack with ECS, RDS, SQS, Cloudinary
- Aika RAG ingestion and answer flow with PGVector and Groq

Subsections:

- 3.1 Technology Stack
- 3.2 Backend Modules
- 3.3 AI Tutor and RAG Flow
- 3.4 Cloud and Storage Design
- 3.5 Request Flow

### Chapter 4: Experimentation and Results

Purpose: present the evidence from the current codebase, model outputs, and implementation footprint.

Key content:

- Export model comparison and interpretation
- Research figures from the repository
- Implementation footprint of the codebase
- Behavioral impact of replacing placeholder UI with live backend data

Subsections:

- 4.1 Model Performance Summary
- 4.2 Research Figures
- 4.3 Implementation Footprint
- 4.4 Result Interpretation

### Chapter 5: Sustainable Development Goals

Purpose: add the new SDG chapter before the conclusion.

Key content:

- SDG 4: Quality Education
- SDG 9: Industry, Innovation and Infrastructure
- SDG 10: Reduced Inequalities
- SDG 17: Partnerships for the Goals
- Explain why the platform contributes to equitable and scalable digital learning

Subsections:

- 5.1 SDG Mapping
- 5.2 Why This Mapping Matters

### Chapter 6: Conclusion and Future Scope

Purpose: summarize the current implementation and state next-step enhancements.

Key content:

- SmartLMS as a working end-to-end learning platform
- Production-oriented architecture and analytics
- Future scope for mobile support, stronger multimodal inputs, improved explainability, and expanded tutoring

Subsections:

- 6.1 Future Scope

## 5. Figure Blueprint

The official report should prefer the curated phase-1 figures below because they are extracted directly from the phase-1 Word document and cleaned for readability. These are the report assets to reuse in the phase-2 document.

### Preferred phase-1 report figures

![Phase-1 literature survey figure](C:/Users/revan/Downloads/smartlms-version2/phase2_report_output/assets/phase1_reference/curated/phase1_literature_survey.png)

![Phase-1 system architecture figure](C:/Users/revan/Downloads/smartlms-version2/phase2_report_output/assets/phase1_reference/curated/phase1_system_architecture.png)

![Phase-1 technology stack table](C:/Users/revan/Downloads/smartlms-version2/phase2_report_output/assets/phase1_reference/curated/phase1_tech_stack.png)

![Phase-1 implementation flow figure](C:/Users/revan/Downloads/smartlms-version2/phase2_report_output/assets/phase1_reference/curated/phase1_implementation_flow.png)

![Phase-1 methodology flow figure](C:/Users/revan/Downloads/smartlms-version2/phase2_report_output/assets/phase1_reference/curated/phase1_methodology_flow.png)

![Phase-1 model comparison table](C:/Users/revan/Downloads/smartlms-version2/phase2_report_output/assets/phase1_reference/curated/phase1_model_comparison.png)

![Phase-1 dashboard overview](C:/Users/revan/Downloads/smartlms-version2/phase2_report_output/assets/phase1_reference/curated/phase1_dashboard_overview.png)

![Phase-1 result gauge](C:/Users/revan/Downloads/smartlms-version2/phase2_report_output/assets/phase1_reference/curated/phase1_result_gauge.png)

### Optional supporting figures from the project repository

If additional phase-2-only visuals are needed, keep them as supporting material rather than primary blueprint assets.

![Aika RAG ingestion and answer flow](C:/Users/revan/Downloads/smartlms-version2/phase2_report_output/assets/aika_rag_flow.png)

![SmartLMS mapping to Sustainable Development Goals](C:/Users/revan/Downloads/smartlms-version2/phase2_report_output/assets/sdg_mapping.png)

![Export model comparison](C:/Users/revan/Downloads/smartlms-version2/phase2_report_output/assets/model_comparison.png)

![SmartLMS platform architecture](C:/Users/revan/Downloads/smartlms-version2/phase2_report_output/assets/smartlms_architecture.png)

## 6. Table Blueprint

### Chapter 3

- Technology stack used in phase-2

### Chapter 4

- Export model comparison and interpretation
- Implementation footprint of the phase-2 codebase

### Chapter 5

- Sustainable development goal mapping

## 7. Formatting Notes

Use the following as the report style target:

- Same overall academic structure as the phase-1 report
- Updated title and content for phase-2
- SDG chapter inserted before conclusion
- Centered cover-page text and formal certificate/declaration pages
- Times New Roman styling for the report body
- Clear chapter numbering and subsection numbering
- Consistent figure captions and table numbering
- Margins aligned to the reference template report

## 8. Content Notes For Official Report

- The report should describe the current SmartLMS codebase, not only the research idea.
- The report should reuse phase-1 figures where possible, using the curated extracted images as the primary visuals.
- The Aika RAG flow should be explained as an implemented feature.
- The model comparison should keep the reported scores and the warning about the biased baseline model.
- The SDG chapter should be positioned immediately before the conclusion chapter.
- The conclusion should mention both current capabilities and future scope.

## 9. Suggested Final Artifacts

- Master blueprint: this markdown file
- Official report DOCX
- Official report PDF
