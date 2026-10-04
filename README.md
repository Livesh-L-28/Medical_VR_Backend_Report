# Medical VR Assessment & Report Generation Engine
python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload

A production-quality, deterministic assessment and educational report-generation backend for a **Medical VR Venipuncture Training Simulation**, integrated with a separate **Medical LLM Project** (supporting OpenBioLLM-8B, Llama 3.2 3B, and MedicalTransformerLM 110.04M).

> **AUTHORITATIVE PRINCIPLE:**
> **The deterministic assessment engine is authoritative. The LLM is intended only for natural-language feedback and explanation.**
> Under no circumstance can the LLM modify, override, or invent assessment scores, mistakes, or PASS/FAIL results.

---

## 1. Project Overview & Decoupled Architecture

The simulation environment consists of two independent projects communicating via HTTP APIs:

```
┌─────────────────────────────────────────────────────────────┐
│                      UNITY VR CLIENT                        │
│   StepManager • Veni • Annotator • Triggers • Telemetry     │
└──────────────────────────────┬──────────────────────────────┘
                               │ HTTP JSON (Bearer JWT)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│             PROJECT A: Medical VR Backend (:8001)           │
│   FastAPI • SQLite / PostgreSQL • SQLAlchemy ORM            │
│  ─────────────────────────────────────────────────────────  │
│   • Auth & Session Ownership Enforcement                    │
│   • Deterministic Assessment Engine (PASS/FAIL Authority)   │
│   • Weak Area & Cumulative Analytics Engine                 │
│   • User-Isolated Historical Telemetry Service              │
│   • LLM Evidence Preparation & Fallback Engine              │
│   • Professional PDF Report Generation (ReportLab)          │
└──────────────────────────────┬──────────────────────────────┘
                               │ HTTP POST /ask (:8000)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│               PROJECT B: Medical LLM (:8000)                │
│   FastAPI • RAG Pipeline • OpenBioLLM (8B) / Llama 3.2 (3B) │
│  ─────────────────────────────────────────────────────────  │
│   • Educational Explanation Only                            │
│   • Strict Grounding against Injected Evidence JSON         │
│   • ZERO Authority over Grading, PASS/FAIL, or Telemetry    │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Standardized 16-Step Venipuncture Protocol

The engine strictly codifies the standardized 16-step venipuncture clinical sequence (Step IDs 0–15):

| Step ID | Procedure Step Name | Expected Object | Target Zone / Trigger |
| :---: | :--- | :--- | :--- |
| `0` | **Wash Hands** | Trainee Hands | Sink / WaterTrigger |
| `1` | **Wear Gloves** | Gloves | Glove Box / Hands |
| `2` | **Apply Tourniquet** | Tourniquet | Upper Arm |
| `3` | **Take Cotton** | Cotton Swab | Cotton Box |
| `4` | **Dip Cotton in Spirit** | Cotton Swab | Spirit Bottle |
| `5` | **Clean Area** | Cotton with Spirit | Patient Puncture Site |
| `6` | **Dispose Cotton** | Used Cotton | Medical Dustbin |
| `7` | **Take Cannula** | Cannula / Needle | Tray / Packaging |
| `8` | **Insert Cannula** | Cannula | Vein Trigger Zone |
| `9` | **Remove Tourniquet** | Tourniquet | Arm Release |
| `10` | **Take Blood Collection Tube** | Vacuum Tube | Tube Rack |
| `11` | **Insert Tube** | Vacuum Tube | Tube Slot / SnapZone |
| `12` | **Blood Collection** | Vacuum Tube | Blood Trigger Mark |
| `13` | **Remove Tube** | Filled Tube | Tube Slot Release |
| `14` | **Remove Cannula** | Cannula | Vein Extraction |
| `15` | **Dispose Cannula** | Used Cannula | Sharps Disposal Dustbin |

---

## 3. Deterministic Assessment Rules & Scoring Logic

### A. Metric Calculations
$$\text{Accuracy} = \frac{\text{Correct Steps}}{\text{Total Steps (16)}} \times 100$$
$$\text{First Attempt Accuracy} = \frac{\text{First Attempt Correct Count}}{\text{Total Steps (16)}} \times 100$$
$$\text{Average Step Time} = \frac{\text{Total Time Seconds}}{\text{Completed Steps}}$$

### B. Mistake Classification
Mistakes are deterministically categorized into three types:
1. `WRONG_OBJECT`: Interacting with an incorrect tool/item for the current step.
2. `WRONG_ZONE`: Correct item held, but interaction attempted in the wrong trigger zone.
3. `INCORRECT_PLACEMENT`: Correct item and correct zone, but invalid orientation, depth, or angle.

### C. TEST Mode Pass/Fail Criteria (Authoritative)
A trainee achieves a **`PASS`** if and only if:
- `completed_steps == 16` **AND**
- `accuracy >= 80.0%` **AND**
- `total_mistakes == 0`

Any mistake or missing step results in an automatic, deterministic **`FAIL`**.

### D. TRAINING Mode Evaluation
- `EXCELLENT`: All 16 steps completed, accuracy $\ge 80\%$, and $0$ mistakes.
- `SATISFACTORY`: All 16 steps completed with accuracy $\ge 60\%$.
- `NEEDS_PRACTICE`: Accuracy $< 60\%$ or incomplete session with accuracy $< 50\%$.
- `INCOMPLETE`: Session ended prematurely but with accuracy $\ge 50\%$.

### E. Weak Area Ranking & Severity
$$\text{Mistake Ratio} = \left(\frac{\text{Mistakes}}{\text{Attempts}}\right) \times 100$$
- `HIGH`: $\text{Mistake Ratio} \ge 50\%$
- `MEDIUM`: $25\% \le \text{Mistake Ratio} < 50\%$
- `LOW`: $\text{Mistake Ratio} < 25\%$
Ranked primarily by total mistake count descending, then by mistake ratio descending.

---

## 4. Mandatory Evidence-Grounding LLM Rules

The `LLMFeedbackEngine` enforces 12 strict grounding directives:
1. **Only use provided data**: Never infer or assume facts outside the input payload.
2. **Never invent mistakes**: Only comment on steps present in the `mistakes` array.
3. **Never invent timings**: Use exact numerical durations from the telemetry.
4. **Never invent weak areas**: Rely strictly on the deterministic weak area ranking.
5. **Never invent historical performance**: Use only verified `historical_context`.
6. **No unfounded improvement claims**: Only state improvement when supported by prior accuracy trends.
7. **Timing Guard**: If duration metrics are absent, the LLM is strictly barred from discussing speed or pace.
8. **No non-standard clinical steps**: Confine all clinical commentary to the 16 venipuncture steps.
9. **Never alter assessment results**: The deterministic `result` is immutable.
10. **State insufficient evidence**: Explicitly state when conclusions cannot be drawn.
11. **Maintain professional clinical tone**: Focus on technique, asepsis, and patient safety.
12. **No patient-specific medical advice**: Confine scope strictly to procedural simulation feedback.

---

## 5. API Endpoints

| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :---: |
| `GET` | `/health` | Service health status | No |
| `POST`| `/api/auth/login` | Trainee login & JWT generation | No |
| `POST`| `/api/users/` | Create trainee profile | No |
| `PUT` | `/api/users/{user_id}/password` | Update user password | No |
| `POST`| `/api/sessions/` | Start a new `TRAINING` or `TEST` session | Yes |
| `GET` | `/api/sessions/{id}` | Get session details (owner only) | Yes |
| `PUT` | `/api/sessions/{id}/complete` | Complete session & log total duration | Yes |
| `GET` | `/api/sessions/user/{user_id}` | List user sessions | Yes |
| `POST`| `/api/step-performance/` | Ingest step telemetry from VR | Yes |
| `POST`| `/api/mistakes/` | Ingest classified mistake event | Yes |
| `GET` | `/api/performance/{id}` | Calculate session performance | Yes |
| `GET` | `/api/weak-areas/{id}` | Calculate session weak areas | Yes |
| `GET` | `/api/cumulative-weak-areas/{user_id}` | Calculate multi-session weak areas | Yes |
| `POST`| `/api/training-reports/{id}` | Generate deterministic training report | Yes |
| `POST`| `/api/test-assessment/{id}` | Run deterministic test assessment | Yes |
| `POST`| `/api/test-reports/{id}` | Generate deterministic test report | Yes |
| `POST`| `/api/guidance/generate` | Generate adaptive guidance profile | Yes |
| `GET` | `/api/guidance/{session_id}` | Retrieve active guidance for session | Yes |
| `GET` | `/api/progress/{user_id}` | Retrieve progress history | Yes |
| `GET` | `/api/comparison/{user_id}` | Compare latest session to history | Yes |
| `GET` | `/api/dashboard/{user_id}` | Retrieve dashboard summary | Yes |
| `POST`| `/api/reports/{id}/ai` | Generate evidence-grounded AI feedback | Yes |
| `GET` | `/api/reports/{id}/pdf` | Download formal clinical PDF evaluation | Yes |

---

## 6. Swagger UI & Test Credentials

Access the interactive API documentation at: **`http://127.0.0.1:8001/docs`**

To test authenticated endpoints, click **Authorize** at the top right:

| Field | Option 1 | Option 2 |
|---|---|---|
| **username** | `trainee@hospital.org` | `alex.rivera@medvr.org` |
| **password** | `Password123!` | `Pass1234!` |
| **client_id** | *(leave blank)* | *(leave blank)* |
| **client_secret** | *(leave blank)* | *(leave blank)* |
| **Sample Session ID** | `1` | `2` |

---

## 7. Running Tests & Verification

### Run the Full Automated Test Suite (45 tests):
```bash
python3 -m pytest tests -v
```

### Run Live End-to-End PDF & LLM Verification:
```bash
python3 verify_pdf_e2e.py
```

### Start the Backend Server:
```bash
python3 run.py
# Server runs on http://127.0.0.1:8001
```
