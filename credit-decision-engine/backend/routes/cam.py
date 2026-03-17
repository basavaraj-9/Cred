from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Dict, Any
import os
from services.cam_generator import CAMGenerator

router = APIRouter()

class CAMRequest(BaseModel):
    company_data: Dict[str, Any]
    financial_data: Dict[str, Any]
    risk_analysis: Dict[str, Any]
    research_data: Dict[str, Any]
    recommendation: Dict[str, Any]

@router.post("/generate-cam")
async def generate_cam(request: CAMRequest):
    """Generate Credit Appraisal Memo"""
    
    try:
        cam_generator = CAMGenerator()

        # Build the CAMContent dataclass from the incoming request fields.
        # The service's generate_cam() requires a CAMContent object, not raw dicts.
        cam_content = cam_generator.create_cam_content(
            borrower_info=request.company_data,
            industry_analysis=request.research_data.get("industry_analysis", {}),
            financial_analysis=request.financial_data,
            risk_assessment=request.risk_analysis,
            research_insights=request.research_data,
            recommendation=request.recommendation,
            five_cs_analysis=request.research_data.get("five_cs_analysis", {}),
            compliance_notes=request.research_data.get("compliance_notes", [])
        )

        # Generate CAM (returns dict of file paths)
        cam_result = cam_generator.generate_cam(cam_content)
        
        return {
            "status": "success",
            "message": "CAM generated successfully",
            "cam_files": cam_result
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CAM generation failed: {str(e)}")

@router.get("/download-cam/{filename}")
async def download_cam(filename: str, file_type: str = "word"):
    """Download generated CAM file"""
    
    try:
        # Determine file path
        if file_type.lower() == "pdf":
            file_path = f"generated_cams/{filename}.pdf"
        else:
            file_path = f"generated_cams/{filename}.docx"
        
        # Check if file exists
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="CAM file not found")
        
        # Return file
        media_type = "application/pdf" if file_type.lower() == "pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        
        return FileResponse(
            path=file_path,
            media_type=media_type,
            filename=f"{filename}.{file_type}"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")

@router.get("/cam-preview/{filename}")
async def get_cam_preview(filename: str):
    """Get CAM preview data"""
    
    try:
        # For now, return a structured preview
        # In production, this would parse the actual CAM file
        
        preview_data = {
            "filename": filename,
            "sections": [
                {
                    "title": "Borrower Overview",
                    "content": "Company details and business overview",
                    "status": "completed"
                },
                {
                    "title": "Industry Analysis",
                    "content": "Sector outlook and market position",
                    "status": "completed"
                },
                {
                    "title": "Financial Analysis",
                    "content": "Financial metrics and ratios analysis",
                    "status": "completed"
                },
                {
                    "title": "Risk Assessment",
                    "content": "Risk factors and mitigation strategies",
                    "status": "completed"
                },
                {
                    "title": "Five Cs of Credit",
                    "content": "Character, Capacity, Capital, Collateral, Conditions",
                    "status": "completed"
                },
                {
                    "title": "Recommendation",
                    "content": "Final lending decision and terms",
                    "status": "completed"
                }
            ],
            "generation_date": "2024-03-09",
            "status": "completed"
        }
        
        return {
            "status": "success",
            "preview": preview_data
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Preview generation failed: {str(e)}")

@router.delete("/delete-cam/{filename}")
async def delete_cam(filename: str):
    """Delete generated CAM file"""
    
    try:
        # Delete both Word and PDF versions
        word_path = f"generated_cams/{filename}.docx"
        pdf_path = f"generated_cams/{filename}.pdf"
        
        deleted_files = []
        
        if os.path.exists(word_path):
            os.remove(word_path)
            deleted_files.append("Word document")
        
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
            deleted_files.append("PDF document")
        
        if not deleted_files:
            raise HTTPException(status_code=404, detail="CAM file not found")
        
        return {
            "status": "success",
            "message": f"Deleted {', '.join(deleted_files)} for {filename}"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Deletion failed: {str(e)}")

@router.get("/cam-list")
async def list_cam_files():
    """List all generated CAM files"""
    
    try:
        cam_dir = "generated_cams"
        
        if not os.path.exists(cam_dir):
            return {
                "status": "success",
                "files": []
            }
        
        files = []
        for filename in os.listdir(cam_dir):
            if filename.endswith(('.docx', '.pdf')):
                file_path = os.path.join(cam_dir, filename)
                stat = os.stat(file_path)
                
                files.append({
                    "filename": filename,
                    "size": stat.st_size,
                    "created_date": stat.st_ctime,
                    "type": "Word" if filename.endswith('.docx') else "PDF"
                })
        
        # Sort by creation date (newest first)
        files.sort(key=lambda x: x['created_date'], reverse=True)
        
        return {
            "status": "success",
            "files": files
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list files: {str(e)}")

@router.get("/cam-template")
async def get_cam_template():
    """Get CAM template structure"""
    
    template_structure = {
        "sections": [
            {
                "name": "borrower_overview",
                "title": "Borrower Overview",
                "fields": [
                    "company_name",
                    "business_nature",
                    "years_in_operation",
                    "annual_revenue",
                    "existing_loans"
                ]
            },
            {
                "name": "industry_analysis",
                "title": "Industry Analysis",
                "fields": [
                    "sector",
                    "sector_outlook",
                    "market_sentiment",
                    "key_trends"
                ]
            },
            {
                "name": "financial_analysis",
                "title": "Financial Analysis",
                "fields": [
                    "revenue",
                    "assets",
                    "liabilities",
                    "profit",
                    "financial_ratios"
                ]
            },
            {
                "name": "risk_assessment",
                "title": "Risk Assessment",
                "fields": [
                    "risk_score",
                    "risk_category",
                    "risk_factors",
                    "component_scores"
                ]
            },
            {
                "name": "five_cs",
                "title": "Five Cs of Credit",
                "fields": [
                    "character",
                    "capacity",
                    "capital",
                    "collateral",
                    "conditions"
                ]
            },
            {
                "name": "recommendation",
                "title": "Recommendation",
                "fields": [
                    "decision",
                    "loan_amount",
                    "interest_rate",
                    "tenure",
                    "conditions"
                ]
            }
        ]
    }
    
    return {
        "status": "success",
        "template": template_structure
    }
