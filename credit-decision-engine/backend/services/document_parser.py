import pdfplumber
import fitz
import pytesseract
from PIL import Image
import pandas as pd
import re
import io
from typing import Dict, List, Any, Optional
import json

class DocumentParser:
    def __init__(self):
        self.financial_keywords = {
            'revenue': ['revenue', 'sales', 'turnover', 'income', 'total revenue'],
            'liabilities': ['liabilities', 'debt', 'borrowings', 'loans', 'credit'],
            'assets': ['assets', 'property', 'equipment', 'investments'],
            'profit': ['profit', 'earnings', 'net income', 'ebitda'],
            'expenses': ['expenses', 'costs', 'expenditure']
        }
    
    async def parse_document(self, file_content: bytes, file_type: str, filename: str) -> Dict[str, Any]:
        """Parse document and extract financial information"""
        
        if file_type == 'application/pdf':
            return await self._parse_pdf(file_content, filename)
        elif file_type in ['application/vnd.ms-excel', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet']:
            return await self._parse_excel(file_content, filename)
        elif file_type == 'text/csv':
            return await self._parse_csv(file_content, filename)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")
    
    async def _parse_pdf(self, file_content: bytes, filename: str) -> Dict[str, Any]:
        """Parse PDF document with OCR fallback"""
        extracted_data = {
            'company': '',
            'revenue': 0,
            'existing_loans': 0,
            'liabilities': 0,
            'litigation': 0,
            'gst_revenue': 0,
            'assets': 0,
            'profit': 0,
            'raw_text': '',
            'document_type': self._classify_document(filename)
        }
        
        try:
            # Try pdfplumber first (better for structured PDFs)
            with pdfplumber.open(io.BytesIO(file_content)) as pdf:
                text = ""
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
                
                if text.strip():
                    extracted_data['raw_text'] = text
                    extracted_data.update(self._extract_financial_entities(text))
                else:
                    # Fallback to OCR
                    extracted_data = await self._ocr_pdf(file_content, extracted_data)
        
        except Exception as e:
            # Fallback to OCR if pdfplumber fails
            extracted_data = await self._ocr_pdf(file_content, extracted_data)
        
        # Extract company name
        extracted_data['company'] = self._extract_company_name(extracted_data['raw_text'])
        
        return extracted_data
    
    async def _ocr_pdf(self, file_content: bytes, extracted_data: Dict) -> Dict[str, Any]:
        """Perform OCR on PDF using PyMuPDF and Tesseract"""
        try:
            doc = fitz.open(stream=file_content, filetype="pdf")
            text = ""
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                pix = page.get_pixmap()
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                
                ocr_text = pytesseract.image_to_string(img)
                text += ocr_text + "\n"
            
            extracted_data['raw_text'] = text
            extracted_data.update(self._extract_financial_entities(text))
            
        except Exception as e:
            print(f"OCR failed: {str(e)}")
        
        return extracted_data
    
    async def _parse_excel(self, file_content: bytes, filename: str) -> Dict[str, Any]:
        """Parse Excel/CSV files"""
        extracted_data = {
            'company': '',
            'revenue': 0,
            'existing_loans': 0,
            'liabilities': 0,
            'litigation': 0,
            'gst_revenue': 0,
            'assets': 0,
            'profit': 0,
            'raw_text': '',
            'document_type': self._classify_document(filename)
        }
        
        try:
            df = pd.read_excel(io.BytesIO(file_content))
            
            # Convert DataFrame to text for analysis
            text = df.to_string()
            extracted_data['raw_text'] = text
            
            # Look for specific columns in GST returns
            if 'gst' in filename.lower():
                extracted_data['gst_revenue'] = self._extract_gst_revenue(df)
            
            extracted_data.update(self._extract_financial_entities(text))
            extracted_data['company'] = self._extract_company_name(text)
            
        except Exception as e:
            print(f"Excel parsing failed: {str(e)}")
        
        return extracted_data
    
    async def _parse_csv(self, file_content: bytes, filename: str) -> Dict[str, Any]:
        """Parse CSV files"""
        return await self._parse_excel(file_content, filename)
    
    def _extract_financial_entities(self, text: str) -> Dict[str, float]:
        """Extract financial entities from text using regex patterns"""
        entities = {
            'revenue': 0,
            'existing_loans': 0,
            'liabilities': 0,
            'litigation': 0,
            'assets': 0,
            'profit': 0
        }
        
        # Pattern to find amounts (including lakhs, crores)
        amount_pattern = r'(?:(?:₹|Rs\.?|INR)\s*)?(\d+(?:,\d{3})*(?:\.\d{2})?)\s*(?:lakh|crore|million|billion|k|cr)?'
        
        for entity_type, keywords in self.financial_keywords.items():
            for keyword in keywords:
                # Look for keyword followed by amount
                pattern = rf'{keyword}[^.]*?{amount_pattern}'
                matches = re.findall(pattern, text, re.IGNORECASE)
                
                for match in matches:
                    amount = self._parse_amount(match)
                    if amount > entities[entity_type]:
                        entities[entity_type] = amount
        
        return entities
    
    def _parse_amount(self, amount_str: str) -> float:
        """Parse amount string to float"""
        try:
            # Remove commas and convert to float
            amount = float(amount_str.replace(',', ''))
            
            # Check for multipliers in the surrounding text
            if 'lakh' in amount_str.lower() or 'lac' in amount_str.lower():
                amount *= 100000
            elif 'crore' in amount_str.lower() or 'cr' in amount_str.lower():
                amount *= 10000000
            elif 'million' in amount_str.lower():
                amount *= 1000000
            elif 'billion' in amount_str.lower():
                amount *= 1000000000
            
            return amount
        except:
            return 0.0
    
    def _extract_company_name(self, text: str) -> str:
        """Extract company name from document text"""
        # Look for common patterns
        patterns = [
            r'(?:M/s|Ms\.|M/s\.)\s*([A-Z][a-zA-Z\s&]+?)(?:\n|,|\.|$)',
            r'([A-Z][a-zA-Z\s&]+?)(?:Limited|Ltd\.|Pvt\.|Private|Corporation|Corp\.|Inc\.|LLC)',
            r'Name[:\s]*([A-Z][a-zA-Z\s&]+?)(?:\n|,|\.|$)'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                company = matches[0].strip()
                if len(company) > 3 and len(company) < 100:
                    return company
        
        return ""
    
    def _classify_document(self, filename: str) -> str:
        """Classify document type based on filename"""
        filename_lower = filename.lower()
        
        if 'annual' in filename_lower or 'financial' in filename_lower:
            return 'annual_report'
        elif 'bank' in filename_lower or 'statement' in filename_lower:
            return 'bank_statement'
        elif 'gst' in filename_lower:
            return 'gst_return'
        elif 'legal' in filename_lower or 'notice' in filename_lower:
            return 'legal_notice'
        elif 'sanction' in filename_lower:
            return 'sanction_letter'
        else:
            return 'other'
    
    def _extract_gst_revenue(self, df: pd.DataFrame) -> float:
        """Extract GST revenue from DataFrame"""
        try:
            # Look for common column names
            revenue_columns = ['turnover', 'revenue', 'taxable_value', 'total_taxable_value']
            
            for col in df.columns:
                if any(keyword in col.lower() for keyword in revenue_columns):
                    # Get the last non-null value (usually the total)
                    revenue_values = df[col].dropna()
                    if not revenue_values.empty:
                        return float(revenue_values.iloc[-1])
            
            return 0.0
        except:
            return 0.0
