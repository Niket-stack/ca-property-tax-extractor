"""
FastAPI application for property tax bill extraction
"""
import logging
import tempfile
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from extractors.base_extractor import PropertyTaxExtractor
from models.schemas import ExtractionResponse, PropertyTaxBillExtraction
from config.settings import settings

# Configure logging
logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="CA Property Tax Bill Extractor",
    description="AI-powered PDF field extractor for California property tax bills",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "name": "CA Property Tax Bill Extractor",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "extract": "/extract",
            "docs": "/docs",
            "openapi": "/openapi.json"
        }
    }


@app.post("/extract", response_model=ExtractionResponse)
async def extract_pdf(
    file: UploadFile = File(...),
    county: str = None
):
    """
    Extract data from a property tax bill PDF
    
    Parameters:
    - file: PDF file to extract from
    - county: Optional county name (auto-detected if not provided)
    
    Returns:
    - PropertyTaxBillExtraction object with extracted data
    """
    
    # Validate file type
    if not file.filename.lower().endswith('.pdf'):
        return ExtractionResponse(
            success=False,
            error="Invalid file type",
            error_details="Only PDF files are accepted"
        )
    
    # Check file size
    contents = await file.read()
    file_size_mb = len(contents) / (1024 * 1024)
    if file_size_mb > settings.max_upload_size_mb:
        return ExtractionResponse(
            success=False,
            error="File too large",
            error_details=f"Maximum file size is {settings.max_upload_size_mb}MB"
        )
    
    try:
        # Save uploaded file to temp location
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(contents)
            tmp_path = tmp.name
        
        logger.info(f"Processing uploaded file: {file.filename}")
        
        # Perform extraction
        extractor = PropertyTaxExtractor(api_key=settings.openai_api_key)
        result = extractor.extract_from_file(tmp_path, county=county)
        
        # Clean up temp file
        Path(tmp_path).unlink()
        
        return ExtractionResponse(
            success=True,
            data=result
        )
    
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        return ExtractionResponse(
            success=False,
            error="Extraction failed",
            error_details=str(e)
        )
    
    except Exception as e:
        logger.error(f"Extraction error: {e}", exc_info=True)
        return ExtractionResponse(
            success=False,
            error="Extraction failed",
            error_details=str(e)
        )


@app.get("/supported-counties")
async def supported_counties():
    """Get list of supported counties"""
    return {
        "counties": [
            {
                "name": "Alameda",
                "website": "https://treasurer.acgov.org/",
                "contact": "510-208-6500"
            },
            {
                "name": "Santa Clara",
                "website": "https://www.sccgov.org/sites/tax/Pages/Secured.aspx",
                "contact": "408-299-5555"
            },
            {
                "name": "Los Angeles",
                "website": "https://ttc.lacounty.gov/",
                "contact": "213-974-2111"
            }
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=settings.api_host,
        port=settings.api_port
    )
