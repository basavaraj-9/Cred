from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from typing import List, Dict, Any
import os
import aiofiles
from services.document_parser import DocumentParser

router = APIRouter()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/upload-documents")
async def upload_documents(files: List[UploadFile] = File(...)):
    """Upload and parse multiple documents"""
    
    try:
        parser = DocumentParser()
        parsed_documents = []
        
        for file in files:
            # Save uploaded file
            file_path = os.path.join(UPLOAD_DIR, file.filename)
            
            async with aiofiles.open(file_path, 'wb') as f:
                content = await file.read()
                await f.write(content)
            
            # Parse document
            parsed_data = await parser.parse_document(
                content, file.content_type, file.filename
            )
            
            parsed_data['filename'] = file.filename
            parsed_data['file_type'] = file.content_type
            parsed_documents.append(parsed_data)
        
        return {
            "status": "success",
            "message": f"Successfully uploaded and parsed {len(files)} documents",
            "documents": parsed_documents
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@router.post("/analyze-company")
async def analyze_company(company_data: Dict[str, Any]):
    """Analyze company data from uploaded documents"""
    
    try:
        # Aggregate data from all documents
        aggregated_data = {
            'company': '',
            'revenue': 0,
            'existing_loans': 0,
            'liabilities': 0,
            'litigation': 0,
            'gst_revenue': 0,
            'assets': 0,
            'profit': 0,
            'documents_summary': []
        }
        
        # Process each document
        for doc in company_data.get('documents', []):
            # Aggregate financial data
            aggregated_data['revenue'] = max(aggregated_data['revenue'], doc.get('revenue', 0))
            aggregated_data['existing_loans'] += doc.get('existing_loans', 0)
            aggregated_data['liabilities'] += doc.get('liabilities', 0)
            aggregated_data['litigation'] += doc.get('litigation', 0)
            aggregated_data['gst_revenue'] = max(aggregated_data['gst_revenue'], doc.get('gst_revenue', 0))
            aggregated_data['assets'] = max(aggregated_data['assets'], doc.get('assets', 0))
            aggregated_data['profit'] += doc.get('profit', 0)
            
            # Use company name from first document with valid name
            if not aggregated_data['company'] and doc.get('company'):
                aggregated_data['company'] = doc['company']
            
            # Add document summary
            aggregated_data['documents_summary'].append({
                'filename': doc.get('filename', ''),
                'document_type': doc.get('document_type', ''),
                'revenue': doc.get('revenue', 0),
                'existing_loans': doc.get('existing_loans', 0)
            })
        
        return {
            "status": "success",
            "company_analysis": aggregated_data
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@router.get("/upload-status/{task_id}")
async def get_upload_status(task_id: str):
    """Get upload status (placeholder for async processing)"""
    
    return {
        "task_id": task_id,
        "status": "completed",
        "progress": 100
    }
