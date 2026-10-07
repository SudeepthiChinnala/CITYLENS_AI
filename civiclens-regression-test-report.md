# CivicLens AI — End-to-End Regression Test Report

**Test date:** 2026-10-07
**Scope:** Existing application regression testing only
**Code/database changes during testing:** None

## Overall Result

# FAIL — Backend runtime/API availability is blocked

The frontend build and source-level feature checks passed. The database remained unchanged. However, the FastAPI backend imported successfully but did not become reachable on `127.0.0.1:8000`, so live API and complete browser workflow testing could not be completed.

## Tests Executed

1. Repository and architecture inspection

1. Database baseline inspection

1. Python environment/import validation

1. Backend direct-import validation

1. FastAPI/Uvicorn startup validation

1. Frontend production build

1. Frontend route/API wiring checks

1. Authentication/authorization implementation inspection

1. Non-destructive API regression attempts

1. Area-detection regression test

1. Final database-integrity verification

## Passed

### Frontend production build

**PASS**

The Vite production build completed successfully. React compilation, imports, routes, worker pages, admin workforce pages, citizen portal pages, and map dependencies compiled successfully.

A non-blocking Vite CJS API deprecation warning was emitted.

### Python environment and dependencies

**PASS**

Project interpreter:

```
D:\CITYLENS_AI\.venv\Scripts\python.exe
Python 3.13.12
```

Validated imports:

- `ssl`

- `fastapi`

- `uvicorn`

- `sqlalchemy`

- `sklearn`

- `numpy`

- `PIL`

### Backend direct import

**PASS**

`backend.main` imported successfully.

Warnings observed:

```
Pydantic V2: orm_mode has been renamed to from_attributes
Spacy load failed: No module named 'spacy'
```

### Area detection

**PASS**

Test coordinates:

```
Latitude: 17.437700
Longitude: 78.448500
```

Detected area:

```
Ameerpet
```

### Source-level role and feature coverage

**PASS**

The code contains:

- Citizen, Admin, and Worker authentication

- Protected role routes

- Worker assignment and reassignment

- Assignment history

- Worker progress history

- Evidence/photo uploads

- Admin completion verification

- Citizen resolution confirmation

- Citizen unresolved/reopen flow

## Failed

### FastAPI backend does not become reachable

**FAIL — Severity: High**

The backend was started with:

```
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

The process remained active but never opened port `8000`. Requests to `/` returned:

```
Unable to connect to the remote server
```

No Uvicorn listening/startup-complete message appeared.

**Likely cause:** The exact blocking point was not exposed by the available output. Possible areas include Uvicorn/Python 3.13 interaction, startup/database initialization, or runtime process state. No speculative source change was made.

### Live API regression suite blocked

**FAIL / BLOCKED — Severity: High**

Starlette `TestClient` and HTTPX `ASGITransport` attempts blocked before returning even the root endpoint. The stalled test processes were stopped safely.

Consequently, live HTTP behavior was not confirmed for:

- Valid citizen/admin/worker login

- Session persistence and logout

- Complaint listing

- Dashboard APIs

- Worker dashboard

- Role isolation

- Evidence uploads

- Resolution confirmation

- Full worker lifecycle

## Warnings

### Complaint-count discrepancy

The project instruction states **73 complaints**, but the actual database contains **74 complaints with IDs 1–74**. This discrepancy existed before testing and was not changed.

### Complaint #1 historical inconsistency

Complaint #1 currently has:

- Current status: `Assigned`

- Active assignment: worker `1234`, `Assigned`, `0%`

- Existing authority update: `Resolved`

- Later authority update: `In Progress`

- Existing worker assignment event: `Assigned`

This produces a historical sequence that appears inconsistent:

```
Resolved → In Progress → Assigned
```

It was not modified.

### Missing SpaCy

The backend reports:

```
Spacy load failed: No module named 'spacy'
```

The NLP service appears to have a fallback, but the intended SpaCy-backed behavior is unavailable.

### Schema warning

The backend emits a Pydantic warning because schemas still use `orm_mode` instead of `from_attributes`.

### Destructive existing test script

`backend/test_backend.py` creates a complaint and changes status without safe cleanup. It was not run.

## Not Verified

Because the backend did not become reachable, the following were not fully executed live:

- Citizen registration/login/logout/session refresh

- Admin login/logout/session refresh

- Worker login/logout/session refresh

- Complaint submission and upload validation

- My Reports live loading and timeline refresh

- Admin dashboard and analytics API values

- Admin assignment/reassignment

- Worker status/progress transitions

- Progress and completion photo uploads

- Admin completion verification

- Citizen confirmation/reopen behavior

- Full Admin → Worker → Citizen end-to-end flow

## Fixed During Testing

None. This was a testing-only pass.

No source files, database records, uploads, assignments, statuses, priorities, clusters, or evidence were changed.

## Final Database Integrity

| Item | Final state |
| --- | --- |
| Complaints | 74 |
| Complaint ID range | 1–74 |
| Null priority scores | 0 |
| Non-null DBSCAN cluster IDs | 7 |
| Worker accounts | 1 |
| Assignments | 1 |
| Worker progress updates | 1 |
| Authority work updates | 2 |
| Citizen evidence records | 0 |
| Citizen confirmations | 0 |
| Citizen accounts | 1 |

Complaint status totals:

| Status | Count |
| --- | --- |
| Reported | 35 |
| Assigned | 13 |
| In Progress | 8 |
| Under Review | 2 |
| Resolved | 16 |
| **Total** | **74** |

## Recommended Next Step

Diagnose and fix the backend startup/listener problem first. Then rerun live authentication, authorization, API, upload, worker-lifecycle, and citizen-resolution tests before changing application functionality.