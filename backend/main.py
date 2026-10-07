from fastapi import FastAPI
from .routes import complaints, dashboard, impact_priority, workforce
from .auth import router as auth_router

app = FastAPI(title="CityLens AI Backend")

# Include routers
app.include_router(complaints.router, prefix="/api/complaints", tags=["complaints"])
app.include_router(impact_priority.router, prefix="/api/complaints", tags=["impact-priority"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(auth_router, prefix="/api")
app.include_router(workforce.router, prefix="/api")

@app.get("/", response_model=dict)
async def read_root():
    return {"message": "CityLens AI backend is running"}
