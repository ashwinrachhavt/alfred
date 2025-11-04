"""
FastAPI endpoint for autocomplete suggestions powered by Searxng.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional
import logging

from alfred.services.searxng_agent import (
    get_autocomplete_suggestions,
    get_instant_facts,
    AutocompleteResult,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(title="Alfred Autocomplete Service")

# CORS middleware for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "https://*.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AutocompleteRequest(BaseModel):
    """Request model for autocomplete."""
    query: str = Field(..., min_length=1, max_length=200)
    context: str = Field(default="", max_length=500)
    max_suggestions: int = Field(default=5, ge=1, le=10)


class AutocompleteResponse(BaseModel):
    """Response model for autocomplete."""
    suggestions: List[AutocompleteResult]
    instant_answer: Optional[str] = None


@app.post("/autocomplete", response_model=AutocompleteResponse)
async def autocomplete(request: AutocompleteRequest):
    """
    Get autocomplete suggestions based on query and context.

    Args:
        request: AutocompleteRequest with query, context, and max_suggestions

    Returns:
        AutocompleteResponse with suggestions and optional instant answer
    """
    try:
        logger.info(f"Autocomplete request: query='{request.query}', context_len={len(request.context)}")

        # Get instant facts for common queries (optional)
        instant_answer = None
        if len(request.query) > 5:
            instant_answer = get_instant_facts(request.query)

        # Get autocomplete suggestions
        suggestions = get_autocomplete_suggestions(
            context=request.context,
            query=request.query,
            max_suggestions=request.max_suggestions,
        )

        logger.info(f"Returning {len(suggestions)} suggestions")

        return AutocompleteResponse(
            suggestions=suggestions,
            instant_answer=instant_answer,
        )

    except Exception as e:
        logger.error(f"Autocomplete error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "service": "autocomplete"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
