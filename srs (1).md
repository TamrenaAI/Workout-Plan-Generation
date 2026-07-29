# CareFlow Decision Support Service (CIS)
## Software Requirements Specification (SRS)

**Version:** 1.0  
**Project:** CareFlow AI Platform  
**Microservice:** Clinical Decision Support Service  
**Repository:** `careflow-clinical-intelligence-service`

---

# 1. Overview

## 1.1 Purpose

The Clinical Intelligence Service is the final reasoning layer of the CareFlow platform.

Unlike previous services that perform information extraction, OCR, summarization, transcription, or interpretation, this service correlates all available patient information to provide physicians with an intelligent clinical dashboard and an AI-powered assistant.

The service should never replace physician judgment. It should function as an intelligent clinical copilot that highlights important findings, correlates evidence, assists clinical reasoning, and answers questions grounded in patient data.

---

# 2. Position inside CareFlow

```
                     Patient
                        │
                        ▼
         History Conversation Service
                        │
                        ▼
           Structured Medical History
                        │
        ┌───────────────┴───────────────┐
        │                               │
        ▼                               ▼
 Laboratory Interpretation      Radiology Interpretation
        │                               │
        ▼                               ▼
 Laboratory Summary            Radiology Summary
        │                               │
        └───────────────┬───────────────┘
                        │
                        ▼
        Clinical Intelligence Service
                        │
        ┌───────────────┴────────────────┐
        │                                │
        ▼                                ▼
 Doctor Clinical Dashboard      AI Physician Assistant
```

---

# 3. Goals

The service shall:

- Correlate findings from all services.
- Generate an intelligent physician dashboard.
- Highlight critical clinical findings.
- Generate evidence-based differential diagnoses.
- Suggest possible investigations.
- Generate physician notes.
- Provide conversational AI for physicians.
- Ground every answer in patient evidence.
- Minimize hallucinations.

---

# 4. Inputs

The service receives a single payload containing outputs from previous services.

## 4.1 History Service

```json
{
    "conversation_transcript": "...",
    "structured_history": {},
    "symptoms": [],
    "medications": [],
    "allergies": [],
    "risk_factors": [],
    "medical_history": [],
    "family_history": [],
    "social_history": []
}
```

---

## 4.2 Laboratory Service

```json
{
    "summary": "...",
    "critical_findings": [],
    "structured_results": {},
    "original_report": "...",
    "confidence": 0.95
}
```

---

## 4.3 Radiology Service

```json
{
    "summary": "...",
    "findings": [],
    "measurements": [],
    "structured_results": {},
    "original_report": "...",
    "confidence": 0.94
}
```

---

## 4.4 Previous Patient Records (Optional)

```json
{
    "previous_visits": [],
    "previous_diagnosis": [],
    "previous_lab_results": [],
    "previous_radiology": [],
    "previous_medications": []
}
```

---

# 5. Outputs

The service exposes two independent products.

---

# Product A

# Intelligent Clinical Dashboard

---

## 5.1 Patient Overview

Display

- Age
- Gender
- Chief complaint
- Visit type
- Urgency
- Allergies
- Current medications

---

## 5.2 Chief Complaint

Extract

- Main complaint
- Duration
- Severity
- Progression

---

## 5.3 Timeline

Generate chronological timeline.

Example

```
3 days ago
↓

Fever

↓

Dry cough

↓

Chest pain

↓

Visited clinic

↓

CBC

↓

Chest CT
```

---

## 5.4 Symptoms

Display

- symptom
- duration
- severity
- evidence source

---

## 5.5 Laboratory Insights

Instead of showing numbers:

❌

```
WBC = 18000
CRP = 48
Hb = 10
```

Generate

✅

```
🔴 Significant leukocytosis

🔴 Elevated inflammatory markers

🟡 Mild anemia

🟢 Kidney function preserved
```

---

## 5.6 Radiology Insights

Highlight

- abnormalities
- anatomical locations
- severity
- clinically important findings

Example

```
Right lower lobe consolidation

Small pleural effusion

No pneumothorax
```

---

## 5.7 Clinical Correlations

Example

```
Persistent fever

+

High CRP

+

Leukocytosis

+

Lobar consolidation

↓

Evidence strongly supports bacterial pneumonia.
```

---

## 5.8 Red Flags

Always prioritize

Examples

- Sepsis indicators
- Stroke indicators
- ACS indicators
- Severe electrolyte imbalance
- Respiratory failure
- Active bleeding
- High-risk lab values

---

## 5.9 Clinical Impression

Generate concise physician-oriented summary.

Example

> Patient presents with progressive fever and productive cough associated with elevated inflammatory markers and right lower lobe consolidation, most consistent with bacterial pneumonia.

---

## 5.10 Differential Diagnosis

Generate ranked list.

Example

| Diagnosis | Confidence | Evidence |
|------------|------------|----------|
| Community Acquired Pneumonia | High | Fever + CRP + CT |
| Viral Pneumonia | Medium | Fever |
| Pulmonary Embolism | Low | Chest pain |

---

## 5.11 Supporting Evidence

Each diagnosis MUST include

Positive evidence

Negative evidence

Missing evidence

Example

```
Diagnosis

Community Acquired Pneumonia

Positive

✔ Fever

✔ Productive cough

✔ WBC

✔ CRP

✔ Consolidation

Negative

✖ No hypoxia

Missing

Blood culture
```

---

## 5.12 Suggested Investigations

Examples

- Blood culture
- ABG
- ECG
- Troponin
- Repeat CBC
- Sputum culture

---

## 5.13 Suggested Clinical Actions

Examples

- Evaluate for admission
- Consider CURB-65
- Monitor oxygen saturation
- Sepsis screening

---

# Product B

# AI Physician Assistant

The assistant is a conversational interface over all patient information.

---

Supported Questions

Examples

```
What medications is the patient taking?

Summarize previous visits.

Compare today's CBC to last month.

When did symptoms begin?

Show every mention of chest pain.

Did the patient mention smoking?

What evidence supports pneumonia?

Generate SOAP note.

Generate discharge summary.

Generate referral letter.

Generate insurance report.
```

---

# 6. AI Assistant Knowledge Base

The assistant MUST retrieve from original sources.

Never answer solely using summaries.

Knowledge Sources

- Original conversation transcript
- Structured history
- Original laboratory report
- Structured laboratory extraction
- Original radiology report
- Structured radiology extraction
- Previous clinic records

---

# 7. System Architecture

```
                         Incoming Request
                                │
                                ▼
                     Validation Layer
                                │
                                ▼
                    Data Normalization
                                │
                                ▼
                Clinical Evidence Builder
                                │
            ┌───────────────────┴────────────────────┐
            ▼                                        ▼
    Dashboard Generator                  Patient Index Builder
            │                                        │
            ▼                                        ▼
 Dashboard JSON Output               Vector Database Update
                                                     │
                                                     ▼
                                          AI Assistant
```

---

# 8. Internal Modules

---

## Module 1

Input Validation

Responsibilities

- Validate payload
- Validate schema
- Missing field detection

---

## Module 2

Normalizer

Responsibilities

Normalize

- lab outputs
- radiology outputs
- history outputs

into unified internal schema.

---

## Module 3

Clinical Evidence Builder

Convert every input into standardized evidence objects.

Example

```python
Evidence

type

source

confidence

clinical_importance

timestamp

supporting_text
```

---

## Module 4

Clinical Correlation Engine

Responsibilities

Correlate

Symptoms

+

Labs

+

Radiology

+

History

Detect

- patterns
- contradictions
- missing information

---

## Module 5

Clinical Reasoning Engine

Generate

- clinical impression
- differential diagnosis
- supporting evidence
- confidence

---

## Module 6

Guideline Retrieval Engine

Retrieve relevant clinical guidelines based on generated differential diagnosis.

Pipeline

```
Diagnosis

↓

Retrieve Guideline

↓

Relevant Sections

↓

Inject into LLM

↓

Improve reasoning
```

Knowledge sources should be trusted medical references indexed offline.

---

## Module 7

Dashboard Generator

Produces structured JSON.

Frontend is responsible for visualization.

---

## Module 8

Patient Knowledge Index

Indexes

History

Labs

Radiology

Previous visits

Conversation

for RAG.

---

## Module 9

Physician Assistant

Pipeline

```
Doctor Question

↓

Intent Detection

↓

Retriever

↓

Relevant Documents

↓

LLM

↓

Grounded Answer

↓

Evidence Citations
```

---

# 9. Clinical Evidence Graph

Internal representation

```
Patient

├── Symptoms

├── Medications

├── Allergies

├── Lab Findings

├── Radiology Findings

├── Diagnoses

├── Procedures

├── Timeline

├── Risk Factors

└── Previous Visits
```

Each node contains

- source
- confidence
- timestamp
- supporting evidence

---

# 10. RAG Architecture

Collections

```
patient-history

patient-labs

patient-radiology

patient-visits

patient-medications

patient-allergies
```

Every chunk stores

```
patient_id

visit_id

document_type

metadata

embedding

raw_text
```

---

# 11. LLM Pipelines

---

## Dashboard Pipeline

```
Normalize

↓

Evidence Builder

↓

Clinical Correlation

↓

Guideline Retrieval

↓

Reasoning

↓

Dashboard JSON
```

---

## Assistant Pipeline

```
Question

↓

Retriever

↓

Ranker

↓

Context Builder

↓

LLM

↓

Grounded Response
```

---

# 12. REST API

## POST

```
/dashboard/generate
```

Returns

Dashboard JSON

---

## POST

```
/assistant/chat
```

Returns

Grounded answer

---

## POST

```
/patient/index
```

Indexes patient documents.

---

## GET

```
/health
```

Health check.

---

# 13. Technology Stack

Backend

- Python 3.12
- FastAPI
- Pydantic

AI

- LangGraph
- LangChain (optional)
- OpenAI / Claude / Gemini (configurable)

Vector Database

- Qdrant

Database

- PostgreSQL

Cache

- Redis

Queue

- RabbitMQ or Kafka

Storage

- MinIO / S3

Observability

- Langfuse
- OpenTelemetry
- Prometheus
- Grafana

---

# 14. Non-Functional Requirements

## Performance

Dashboard generation

< 8 seconds

Assistant response

< 5 seconds

---

## Scalability

Support

- horizontal scaling
- stateless API
- asynchronous indexing

---

## Security

JWT authentication

Encrypted storage

Encrypted communication

Audit logging

Role-based authorization

---

## Explainability

Every diagnosis must include

- supporting evidence
- confidence
- retrieved guideline references
- original evidence source

---

# 15. Future Features

- Multi-agent clinical reasoning
- Drug interaction engine
- Treatment recommendation engine
- ICD-10 coding
- CPT coding
- Automatic physician documentation
- Medical literature search
- Longitudinal patient analytics
- Predictive risk scoring
- Follow-up recommendation engine
- Hospital integration (FHIR/HL7)
- Real-time clinical alerts