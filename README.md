# 🏙️ CITYLENS AI

### Turning Civic Complaints into Smart Action

**CityLens AI** is an AI-powered civic intelligence platform that transforms citizen complaints into structured, prioritized, location-aware workflows for faster response, better resource allocation, transparent field operations, and data-driven urban governance.

Instead of treating a civic complaint as a simple ticket, CityLens AI creates an end-to-end intelligence pipeline:

> **Report → Understand → Prioritize → Act → Verify**

Citizens report problems with evidence and location.
AI helps classify and assess the issue.
City authorities understand patterns and hotspots.
Complaints are prioritized and assigned to field workers.
Workers update progress with evidence.
Authorities verify completion.
Citizens get the final say on whether the problem was actually resolved.

---

## ✨ Why CityLens AI?

Traditional civic complaint systems often stop at:

**Citizen → Complaint → Status**

CityLens AI goes further:

```text
Citizen Report
      │
      ▼
📷 Image + Description + Location
      │
      ▼
🤖 AI-Assisted Classification
      │
      ├── Problem Type
      ├── Confidence
      └── Severity
      │
      ▼
📍 Geographic Area Detection
      │
      ▼
🧠 Spatial Clustering
      │
      ▼
📊 Priority Scoring
      │
      ▼
🗺️ City Intelligence
      │
      ▼
👨‍💼 Admin Decision Center
      │
      ▼
👷 Worker Assignment
      │
      ▼
📈 Field Progress + Evidence
      │
      ▼
✅ Admin Verification
      │
      ▼
👤 Citizen Confirmation
      │
      ├── ✔ Fixed
      │
      └── ✖ Still unresolved → Reopened
```

This creates a closed-loop civic intelligence system rather than a basic complaint-management application.

---

# 🚀 Core Features

## 👤 1. Citizen Portal

Citizens get a dedicated portal for reporting and tracking civic problems.

### Citizen capabilities

* Secure citizen registration
* Citizen login/logout
* Personal complaint dashboard
* Submit new civic complaints
* Upload problem photographs
* Optional written description
* AI-based problem detection
* Manual problem-type selection
* Browser geolocation support
* Manual latitude/longitude entry
* AI confidence display
* Severity classification
* Priority score
* Area identification
* Complaint status tracking
* Complete complaint timeline
* Authority work updates
* Worker assignment/progress visibility
* Resolution evidence viewing
* Resolution confirmation
* Complaint reopening when the issue remains unresolved
* Optional citizen evidence upload after resolution

The citizen dashboard also provides a citywide map so users can understand what is happening around Hyderabad.

---

# 📷 2. Intelligent Civic Reporting

A citizen can submit:

* 📸 A photograph
* 📝 Optional description
* 📍 Latitude
* 📍 Longitude

The reporting interface supports automatic browser location capture or manual coordinates.

### Supported problem categories

| Category         | Examples                             |
| ---------------- | ------------------------------------ |
| 🕳️ Pothole      | Road holes, damaged pavement         |
| 🗑️ Garbage      | Waste, trash, litter                 |
| 💡 Streetlight   | Broken/non-functional lighting       |
| 🛣️ Damaged Road | Cracks and road damage               |
| 🌧️ Drainage     | Drainage, flooding, waterlogging     |
| ❓ Other          | Problems outside the main categories |

The user can leave the system in **Auto Detect (AI)** mode or manually choose the problem type.

---

# 🤖 3. AI-Assisted Image Understanding

CityLens AI uses **OpenAI CLIP (`clip-vit-base-patch32`)** for zero-shot image classification across civic-problem categories.

The model compares the submitted image against the supported problem categories and produces a confidence score.

```text
Citizen Image
     │
     ▼
CLIP Processor
     │
     ▼
CLIP Vision-Language Model
     │
     ▼
Category Probabilities
     │
     ▼
Highest-confidence Problem Type
     │
     ▼
Confidence + Severity
```

The implementation lazily loads the model so application startup does not depend on downloading model weights. If the required AI dependencies/model are unavailable, the system falls back safely instead of crashing.

### AI output

* Problem type
* Confidence score
* Initial severity signal

The application intentionally presents the result as **AI-assisted analysis**, rather than pretending that the model is infallible.

---

# 🧠 4. Description / NLP Analysis

Citizen descriptions can provide additional context.

The NLP layer supports:

* Optional SpaCy processing
* Problem-keyword detection
* Severity-keyword detection
* Text-based classification clues

Examples include:

```text
"large pothole blocking traffic"
        ↓
Problem: Pothole
Severity clue: HIGH
```

```text
"small crack near the road"
        ↓
Problem: Damaged Road
Severity clue: LOW
```

The NLP layer can supplement the image analysis when image confidence is low or when the description provides stronger contextual information.

---

# 🚦 5. Severity Intelligence

CityLens combines image confidence and textual severity clues to determine:

* `LOW`
* `MEDIUM`
* `HIGH`

The current severity logic starts with image confidence and can increase severity when high/medium severity clues are detected in the description.

This allows the system to consider both:

**What the image appears to show**

and

**What the citizen says is happening.**

---

# 📍 6. Geographic Area Detection

Complaints are automatically associated with a supported Hyderabad area using geographic distance calculations.

Current supported area centers include:

* Kukatpally
* Madhapur
* Ameerpet
* Gachibowli
* LB Nagar
* Secunderabad
* Miyapur
* Hitech City

The system uses a nearest-area approach with a maximum supported distance of 5 km. Complaints outside the covered region are labelled `Unknown`.

> The current implementation uses representative area centers rather than official administrative ward polygons.

---

# 🧩 7. Spatial Hotspot Detection with DBSCAN

CityLens AI automatically identifies geographically concentrated complaint clusters.

The clustering engine uses **DBSCAN** from scikit-learn.

### Current configuration

```text
Algorithm: DBSCAN
Minimum samples: 3
Approximate radius: 100 m
```

Complaints that form meaningful spatial concentrations receive a cluster ID, while isolated complaints remain unclustered.

Each detected cluster can expose:

* Cluster ID
* Complaint count
* Centroid
* Dominant problem type
* Average severity

Clusters are also exposed as GeoJSON for map visualization.

---

# 🎯 8. Intelligent Priority Scoring

Every complaint receives a CityLens priority score from **0–100**.

The current individual priority model combines:

| Signal             | Weight |
| ------------------ | -----: |
| Severity           |    40% |
| Nearby reports     |    25% |
| Recency            |    20% |
| Hotspot membership |    15% |

```text
Priority Score
      │
      ├── Severity
      ├── Nearby complaints
      ├── Recency
      └── Hotspot membership
             │
             ▼
          0–100
```

The nearby-report component uses logarithmic normalization, while newer complaints receive a stronger recency signal.

For area-level prioritization, CityLens additionally considers:

* Total complaints
* High-severity complaints
* Hotspots
* Recent complaints

Areas are then categorized into:

```text
80–100 → CRITICAL
60–79  → HIGH
40–59  → MEDIUM
0–39   → LOW
```

This allows the administration to focus attention where the combined civic signal is strongest.

---

# 🗺️ 9. Live Civic Intelligence Map

CityLens includes an interactive **Leaflet / React-Leaflet** map.

### Citizen view

Citizens can see a public citywide view of civic problems and spatial concentrations.

### Admin view

Administrators get a richer operational map containing:

* Complaint locations
* Hotspot clusters
* Area information
* Concentration levels
* Priority/impact information

The map uses Hyderabad as the current geographic focus and dynamically loads complaint and cluster data from the backend.

---

# 🧑‍💼 10. Admin Command Center

The Admin portal is designed as the operational brain of CityLens AI.

### Admin navigation

```text
MONITOR
├── Overview
├── Live Map
└── Urban Risk

UNDERSTAND
├── Complaints
└── Problem Fusion

PRIORITIZE
├── Priority Areas
├── Impact Analysis
└── Decision Center

VERIFY
├── Resolution Verification
└── Recurring Problems

ANALYZE
├── Analytics
└── AI Insights
```

The main command center combines complaint statistics, severity, hotspots, priority signals, area intelligence, city health, observed patterns, AI insights, maps, and workforce capacity.

---

# 📊 11. City Intelligence Dashboard

The Admin dashboard provides a high-level operational picture.

### Key metrics

* Total reports
* High-severity reports
* Active hotspots
* Priority signals
* Resolution/verification indicators
* Active workforce assignments
* Completed work
* Overdue work

### Intelligence views

* City health indicator
* Priority areas
* Master urban problems
* Observed risk areas
* Workflow status
* AI-generated insights
* Workforce response capacity
* Live urban signal map

The dashboard explicitly distinguishes observed patterns from future prediction, keeping the interpretation grounded in the current complaint dataset.

---

# 🔎 12. Complaint Intelligence & Management

Administrators can:

* Browse all complaints
* Filter by problem type
* Filter by status
* Open individual complaint details
* View citizen information
* View complaint photographs
* View coordinates
* View AI confidence
* View severity
* View priority score
* Update complaint status
* View authority work updates
* Assign workers
* Reassign workers
* Review worker progress
* Verify completed work
* Review evidence authenticity information
* Review citizen resolution responses

The complaint detail interface acts as a complete operational case file rather than just a database row.

---

# 👷 13. Workforce Management

CityLens AI contains a complete field-workforce workflow.

Administrators can:

* Create worker accounts
* Activate/deactivate workers
* View workforce statistics
* View worker profiles
* View worker assignment history
* Assign complaints
* Reassign complaints
* Set deadlines
* Add assignment notes
* Monitor progress
* Identify overdue work
* Identify overloaded workers
* Verify completion

The system also maintains historical assignment records instead of simply overwriting the previous assignment.

---

# 📈 14. Worker Portal

Field workers receive their own protected portal.

### Worker dashboard

Workers can see:

* Total assigned cases
* Pending work
* Accepted cases
* Work started
* In-progress work
* Completed work
* Overdue cases
* Completion rate
* Current assignments
* Deadlines
* Priority scores
* Progress percentages

Each complaint can be opened as a dedicated field-work case.

---

# 🔄 15. Controlled Field-Work Lifecycle

Workers cannot arbitrarily jump between statuses.

The workflow follows controlled transitions:

```text
Assigned
   ↓
Accepted
   ↓
Work Started
   ↓
In Progress
   ↓
Work Completed
```

Progress percentages cannot move backwards.

`Work Completed` requires:

```text
100% progress
        +
completion photo
```

This creates a more reliable operational workflow than a simple free-form status dropdown.

---

# 📸 16. Evidence & Photo Integrity

CityLens AI treats field evidence as an important part of the workflow.

Uploaded evidence is checked for:

* Supported image format
* Valid image structure
* Image dimensions
* File size
* SHA-256 hash
* EXIF metadata
* C2PA/content-credential markers
* Known AI-generation metadata indicators

Supported evidence formats include:

```text
JPG
PNG
WEBP
```

The system deliberately describes these checks as **heuristic provenance checks**, not cryptographic proof of authenticity.

This is an important design choice because:

> **"No suspicious metadata detected" does not mean "the photograph is guaranteed authentic."**

---

# ✅ 17. Admin Resolution Verification

A worker cannot directly turn a complaint into a final city resolution.

The workflow is:

```text
Worker
  │
  ├── Completes work
  ├── Reaches 100%
  └── Uploads evidence
          │
          ▼
       Admin
          │
          ├── Reviews evidence
          ├── Reviews progress history
          └── Verifies completion
                  │
                  ▼
              Resolved
```

Only after administrative verification does the complaint enter the citizen confirmation stage.

---

# 👤 18. Citizen Resolution Confirmation

This is one of the strongest parts of the system.

When an authority marks a complaint resolved, the citizen is asked:

> **Is this problem fixed?**

The citizen can choose:

### ✅ Yes, it is fixed

The resolution is confirmed.

### ❌ No, the problem is still there

The complaint is reopened for review.

Citizens can also upload optional evidence supporting their response.

This creates a feedback loop:

```text
Authority says:
        RESOLVED
           │
           ▼
Citizen verifies
      /        \
    YES         NO
     │           │
     ▼           ▼
Confirmed     Reopened
```

The system keeps resolution confirmation history so previous responses are not silently overwritten.

---

# 📊 19. Analytics

The Admin Analytics page provides current dataset-level views for:

* Complaints by problem type
* Complaints by severity
* Complaints by status
* Complaints by area
* Stored priority score distribution
* DBSCAN hotspot criticality

This gives administrators both **operational status** and **spatial/problem distribution** views.

---

# 🧠 20. AI Insights

The command center includes an AI Insights layer that summarizes the current civic situation.

Insights are generated from the complaint dataset and surfaced alongside:

* Severity
* Hotspots
* Priority
* Unresolved complaints
* Areas
* Recent activity

The UI also labels observed-risk analysis carefully rather than presenting it as guaranteed future prediction.

---

# 🔐 21. Role-Based Authentication

CityLens AI separates the system into three protected roles:

| Role        | Purpose                                |
| ----------- | -------------------------------------- |
| 👤 Citizen  | Report and track civic problems        |
| 👷 Worker   | Execute assigned field work            |
| 🧑‍💼 Admin | Monitor, prioritize, assign and verify |

The frontend protects role-specific routes and redirects unauthorized users to the appropriate portal login.

### Authentication design

The backend uses:

* PBKDF2-SHA256 password hashing
* Salted password storage
* Opaque server-side sessions
* HttpOnly cookies
* SameSite cookie protection
* Session expiration
* Server-side role validation
* Portal-specific authorization

The session cookie is configured as:

```text
HttpOnly
SameSite=Strict
Secure when HTTPS is used
```

---

# 🛡️ 22. Security-Oriented Design

CityLens includes several defensive implementation details:

### Authentication

* Password hashing with PBKDF2-SHA256
* Session expiration
* Revocable sessions
* Protected role routes
* Server-side authorization

### File handling

* MIME/type validation
* Image signature validation
* Size limits
* Dimension limits
* Safe upload paths
* SHA-256 hashes
* Metadata inspection

### Authorization

Citizens can access their own complaints.

Workers can access complaints assigned to them.

Administrators have management-level access.

These ownership checks are enforced on the backend rather than relying solely on frontend visibility.

---

# 🏗️ System Architecture

```text
┌─────────────────────────────────────────────────────┐
│                    CITYLENS AI                      │
└─────────────────────────────────────────────────────┘

                     FRONTEND
              React + Vite + Leaflet
                        │
                        │ Axios / JSON / FormData
                        ▼
                 ┌──────────────┐
                 │   FastAPI    │
                 │   Backend    │
                 └──────┬───────┘
                        │
       ┌────────────────┼─────────────────┐
       │                │                 │
       ▼                ▼                 ▼
 Authentication     Complaint API     Workforce API
       │                │                 │
       │                ▼                 │
       │        ┌────────────────┐         │
       │        │ AI / NLP Layer │         │
       │        └───────┬────────┘         │
       │                │                  │
       │        ┌───────┼────────┐         │
       │        ▼       ▼        ▼         │
       │      CLIP     NLP    Severity     │
       │                                  │
       │                ▼                  │
       │        Area Detection             │
       │                │                  │
       │                ▼                  │
       │          DBSCAN Clustering        │
       │                │                  │
       │                ▼                  │
       │          Priority Engine          │
       │                │                  │
       └────────────────┼──────────────────┘
                        ▼
                  SQLite Database
                        │
                        ▼
                 City Intelligence
```

The backend exposes separate routers for complaints, dashboard intelligence, authentication, impact/priority analysis, and workforce operations.

---

# 🗄️ Data Model

CityLens AI uses SQLite with SQLAlchemy.

The data model includes dedicated records for:

```text
Complaint
CitizenAccount
WorkerAccount
ComplaintAssignment
WorkerProgressUpdate
ComplaintWorkUpdate
CitizenResolutionEvidence
CitizenResolutionConfirmation
OSMExposureCache
```

This allows the system to maintain not only the current complaint state, but also:

* Assignment history
* Worker progress history
* Authority updates
* Resolution cycles
* Citizen confirmations
* Evidence metadata
* File hashes

---

# 🧰 Tech Stack

## Frontend

| Technology    | Purpose                   |
| ------------- | ------------------------- |
| React 18      | UI                        |
| Vite          | Development/build tooling |
| React Router  | Role-based navigation     |
| Axios         | API communication         |
| Leaflet       | Interactive maps          |
| React-Leaflet | React map integration     |

## Backend

| Technology       | Purpose                    |
| ---------------- | -------------------------- |
| Python           | Backend language           |
| FastAPI          | REST API                   |
| Uvicorn          | ASGI server                |
| SQLAlchemy       | ORM                        |
| SQLite           | Database                   |
| Pydantic         | Validation                 |
| Pillow           | Image inspection           |
| PyTorch          | AI inference               |
| Transformers     | CLIP model                 |
| scikit-learn     | DBSCAN clustering          |
| NumPy            | Numerical processing       |
| python-multipart | File uploads               |
| Alembic          | Database migration support |

---

# 📁 Project Structure

```text
CITYLENS_AI/
│
├── backend/
│   ├── main.py
│   ├── auth.py
│   ├── database.py
│   ├── models.py
│   ├── schemas.py
│   │
│   ├── routes/
│   │   ├── complaints.py
│   │   ├── dashboard.py
│   │   ├── impact_priority.py
│   │   └── workforce.py
│   │
│   └── services/
│       ├── ai_service.py
│       ├── nlp_service.py
│       ├── severity_service.py
│       ├── area_service.py
│       ├── clustering_service.py
│       ├── priority_service.py
│       └── insights_service.py
│
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   │
│   └── src/
│       ├── App.jsx
│       ├── contexts/
│       │   └── AuthContext.jsx
│       │
│       ├── services/
│       │   ├── api.js
│       │   ├── areaIntelligence.js
│       │   ├── criticality.js
│       │   └── uiIntelligence.js
│       │
│       └── pages/
│           ├── PortalLanding.jsx
│           ├── PortalLogin.jsx
│           ├── PortalRegister.jsx
│           ├── UserDashboard.jsx
│           ├── Report.jsx
│           ├── MyReports.jsx
│           ├── Dashboard.jsx
│           ├── Complaints.jsx
│           ├── Areas.jsx
│           ├── Map.jsx
│           ├── Analytics.jsx
│           ├── Workforce.jsx
│           ├── WorkerDashboard.jsx
│           └── WorkerComplaintDetail.jsx
│
├── citylens.db
├── civiclens-regression-test-report.md
└── README.md
```

---

# 🔌 API Overview

### Authentication

```text
POST /api/auth/citizen/login
POST /api/auth/citizen/register
POST /api/auth/admin/login
POST /api/auth/worker/login
GET  /api/auth/me
POST /api/auth/logout
```

### Complaints

```text
POST  /api/complaints/
GET   /api/complaints/
GET   /api/complaints/public
PATCH /api/complaints/{id}
```

### Intelligence

```text
GET  /api/dashboard/summary
GET  /api/dashboard/areas
GET  /api/dashboard/clusters
POST /api/dashboard/clusters/update
GET  /api/dashboard/insights
GET  /api/complaints/{id}/impact-priority
```

### Workforce

```text
GET   /api/workforce/admin/summary
GET   /api/workforce/admin/workers
POST  /api/workforce/admin/workers
PATCH /api/workforce/admin/workers/{worker_id}/status

POST /api/workforce/admin/complaints/{id}/assignments
POST /api/workforce/admin/complaints/{id}/verify-completion

GET  /api/workforce/my
GET  /api/workforce/complaints/{id}/progress
POST /api/workforce/assignments/{id}/updates
```

### Resolution

```text
GET  /api/complaints/{id}/resolution-confirmation
POST /api/complaints/{id}/resolution-confirmation
POST /api/complaints/{id}/resolution-confirmation/evidence
```

The frontend centralizes these calls through an Axios API client using the Vite `/api` proxy.

---

# ⚙️ Local Setup

## 1. Clone

```bash
git clone https://github.com/SudeepthiChinnala/CITYLENS_AI.git
cd CITYLENS_AI
```

## 2. Backend

Create and activate a Python environment:

```bash
python -m venv .venv
```

### Windows

```bash
.venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r backend/requirements.txt
```

## 3. Configure backend credentials

Create:

```text
backend/.env
```

Configure the required CityLens portal credentials and password hashes according to the authentication configuration used by the application.

Do **not** commit `.env` or plaintext credentials.

## 4. Start FastAPI

From the project root:

```bash
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

The backend exposes:

```text
http://127.0.0.1:8000
```

## 5. Start frontend

Open another terminal:

```bash
cd frontend
npm install
npm run dev
```

Vite serves the frontend and proxies `/api` requests to the FastAPI backend.

---

# 🧪 Production Build

To build the frontend:

```bash
cd frontend
npm run build
```

To preview the production build:

```bash
npm run preview
```

---

# 🔄 End-to-End Example

A typical Ci
