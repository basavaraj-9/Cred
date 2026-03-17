"""
Data Ingestor Module - Comprehensive Document Processing
Handles PDF processing, OCR, NER, and financial data extraction
"""

import os
import re
import json
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from pathlib import Path
import pandas as pd
import numpy as np

# PDF Processing Libraries
try:
    import pdfplumber
    import fitz  # PyMuPDF
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    logging.warning("PDF libraries not available. Install: pip install pdfplumber PyMuPDF")

# OCR Library
try:
    import pytesseract
    from PIL import Image
    import cv2
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    logging.warning("OCR libraries not available. Install: pip install pytesseract pillow opencv-python")

# NLP Libraries
try:
    import spacy
    NLP_AVAILABLE = True
except ImportError:
    NLP_AVAILABLE = False
    logging.warning("NLP libraries not available. Install: pip install spacy")

# Excel Processing
try:
    import openpyxl
    import xlrd
    EXCEL_AVAILABLE = True
except ImportError:
    EXCEL_AVAILABLE = False
    logging.warning("Excel libraries not available. Install: pip install openpyxl xlrd")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class FinancialData:
    """Structured financial data extracted from documents"""
    company_name: str = ""
    revenue: float = 0.0
    net_profit: float = 0.0
    total_assets: float = 0.0
    total_liabilities: float = 0.0
    equity: float = 0.0
    cash_flow: float = 0.0
    existing_loans: float = 0.0
    litigation_amount: float = 0.0
    gst_revenue: float = 0.0
    bank_deposits: float = 0.0
    industry: str = ""
    year: int = 0
    document_type: str = ""
    confidence_score: float = 0.0
    extraction_method: str = ""

@dataclass
class DocumentEntity:
    """Named entities extracted from documents"""
    text: str
    label: str
    confidence: float
    start_char: int
    end_char: int

class DataIngestor:
    """Comprehensive data ingestion and processing service"""
    
    def __init__(self):
        self.nlp = None
        if NLP_AVAILABLE:
            try:
                self.nlp = spacy.load("en_core_web_sm")
            except OSError:
                logger.warning("spaCy model not found. Install: python -m spacy download en_core_web_sm")
        
        # Financial patterns for extraction
        self.patterns = {
            'revenue': [
                r'(?:total\s+)?revenue[:\s]+₹?[\s,]*([\d,]+\.?\d*)\s*(?:cr|crore|lakh|million|billion)?',
                r'(?:sales|turnover)[:\s]+₹?[\s,]*([\d,]+\.?\d*)\s*(?:cr|crore|lakh|million|billion)?',
                r'revenue\s+from\s+operations[:\s]+₹?[\s,]*([\d,]+\.?\d*)'
            ],
            'profit': [
                r'(?:net\s+)?profit[:\s]+₹?[\s,]*([\d,]+\.?\d*)\s*(?:cr|crore|lakh|million|billion)?',
                r'(?:profit\s+after\s+tax|PAT)[:\s]+₹?[\s,]*([\d,]+\.?\d*)',
                r'(?:net\s+income|earnings)[:\s]+₹?[\s,]*([\d,]+\.?\d*)'
            ],
            'assets': [
                r'(?:total\s+)?assets[:\s]+₹?[\s,]*([\d,]+\.?\d*)\s*(?:cr|crore|lakh|million|billion)?',
                r'(?:balance\s+sheet\s+)?total\s+assets[:\s]+₹?[\s,]*([\d,]+\.?\d*)'
            ],
            'liabilities': [
                r'(?:total\s+)?liabilities[:\s]+₹?[\s,]*([\d,]+\.?\d*)\s*(?:cr|crore|lakh|million|billion)?',
                r'(?:total\s+)?borrowings[:\s]+₹?[\s,]*([\d,]+\.?\d*)',
                r'(?:outstanding\s+)?loans[:\s]+₹?[\s,]*([\d,]+\.?\d*)'
            ],
            'equity': [
                r'(?:share\s+)?(?:capital|equity)[:\s]+₹?[\s,]*([\d,]+\.?\d*)\s*(?:cr|crore|lakh|million|billion)?',
                r'(?:total\s+)?equity[:\s]+₹?[\s,]*([\d,]+\.?\d*)',
                r'(?:shareholders\s+)?funds[:\s]+₹?[\s,]*([\d,]+\.?\d*)'
            ]
        }

    def process_document(self, file_path: str) -> FinancialData:
        """Main method to process any document type"""
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        file_extension = file_path.suffix.lower()
        
        try:
            if file_extension == '.pdf':
                return self._process_pdf(file_path)
            elif file_extension in ['.xlsx', '.xls']:
                return self._process_excel(file_path)
            elif file_extension == '.csv':
                return self._process_csv(file_path)
            elif file_extension in ['.jpg', '.jpeg', '.png', '.tiff']:
                return self._process_image(file_path)
            else:
                logger.warning(f"Unsupported file type: {file_extension}")
                return FinancialData()
        except Exception as e:
            logger.error(f"Error processing document {file_path}: {str(e)}")
            return FinancialData()

    def _process_pdf(self, file_path: Path) -> FinancialData:
        """Process PDF documents with multiple extraction methods"""
        text = ""
        confidence = 0.0
        method = ""
        
        # Try text extraction first
        if PDF_AVAILABLE:
            try:
                # Method 1: pdfplumber (better for tables)
                with pdfplumber.open(file_path) as pdf:
                    pdf_text = ""
                    for page in pdf.pages:
                        page_text = page.extract_text()
                        if page_text:
                            pdf_text += page_text + "\n"
                    
                    if pdf_text.strip():
                        text = pdf_text
                        confidence = 0.8
                        method = "pdfplumber"
                
                # Method 2: PyMuPDF (better for scanned PDFs)
                if not text or confidence < 0.6:
                    doc = fitz.open(file_path)
                    pymupdf_text = ""
                    for page_num in range(doc.page_count):
                        page = doc.load_page(page_num)
                        pymupdf_text += page.get_text() + "\n"
                    
                    if pymupdf_text.strip() and len(pymupdf_text) > len(text):
                        text = pymupdf_text
                        confidence = 0.7
                        method = "PyMuPDF"
                
                # Method 3: OCR if text extraction failed
                if not text or confidence < 0.5:
                    ocr_text = self._ocr_pdf(file_path)
                    if ocr_text:
                        text = ocr_text
                        confidence = 0.6
                        method = "OCR"
                
            except Exception as e:
                logger.error(f"PDF processing error: {str(e)}")
        
        # Extract financial data
        financial_data = self._extract_financial_data(text)
        financial_data.confidence_score = confidence
        financial_data.extraction_method = method
        financial_data.document_type = "PDF"
        
        return financial_data

    def _ocr_pdf(self, file_path: Path) -> str:
        """Perform OCR on PDF documents"""
        if not OCR_AVAILABLE:
            return ""
        
        try:
            doc = fitz.open(file_path)
            full_text = ""
            
            for page_num in range(doc.page_count):
                page = doc.load_page(page_num)
                
                # Convert page to image
                pix = page.get_pixmap()
                img_data = pix.tobytes("png")
                image = Image.open(io.BytesIO(img_data))
                
                # Preprocess image for better OCR
                image_array = np.array(image)
                gray = cv2.cvtColor(image_array, cv2.COLOR_RGB2GRAY)
                
                # Apply thresholding
                _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                
                # Perform OCR
                text = pytesseract.image_to_string(thresh)
                full_text += text + "\n"
            
            return full_text
        except Exception as e:
            logger.error(f"OCR processing error: {str(e)}")
            return ""

    def _process_excel(self, file_path: Path) -> FinancialData:
        """Process Excel files"""
        if not EXCEL_AVAILABLE:
            logger.error("Excel libraries not available")
            return FinancialData()
        
        try:
            # Try with openpyxl first (for .xlsx)
            if file_path.suffix == '.xlsx':
                df = pd.read_excel(file_path, engine='openpyxl')
            else:
                df = pd.read_excel(file_path, engine='xlrd')
            
            # Convert DataFrame to text
            text = df.to_string()
            
            financial_data = self._extract_financial_data(text)
            financial_data.document_type = "Excel"
            financial_data.confidence_score = 0.7
            financial_data.extraction_method = "pandas"
            
            return financial_data
        except Exception as e:
            logger.error(f"Excel processing error: {str(e)}")
            return FinancialData()

    def _process_csv(self, file_path: Path) -> FinancialData:
        """Process CSV files"""
        try:
            df = pd.read_csv(file_path)
            text = df.to_string()
            
            financial_data = self._extract_financial_data(text)
            financial_data.document_type = "CSV"
            financial_data.confidence_score = 0.7
            financial_data.extraction_method = "pandas"
            
            return financial_data
        except Exception as e:
            logger.error(f"CSV processing error: {str(e)}")
            return FinancialData()

    def _process_image(self, file_path: Path) -> FinancialData:
        """Process image files with OCR"""
        if not OCR_AVAILABLE:
            logger.error("OCR libraries not available")
            return FinancialData()
        
        try:
            image = Image.open(file_path)
            
            # Preprocess image
            image_array = np.array(image)
            if len(image_array.shape) == 3:
                gray = cv2.cvtColor(image_array, cv2.COLOR_RGB2GRAY)
            else:
                gray = image_array
            
            # Apply thresholding
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # Perform OCR
            text = pytesseract.image_to_string(thresh)
            
            financial_data = self._extract_financial_data(text)
            financial_data.document_type = "Image"
            financial_data.confidence_score = 0.5
            financial_data.extraction_method = "OCR"
            
            return financial_data
        except Exception as e:
            logger.error(f"Image processing error: {str(e)}")
            return FinancialData()

    def _extract_financial_data(self, text: str) -> FinancialData:
        """Extract financial data using pattern matching and NLP"""
        financial_data = FinancialData()
        
        # Clean text
        text = re.sub(r'\s+', ' ', text)
        
        # Extract company name using NLP
        if self.nlp:
            entities = self._extract_entities(text)
            for entity in entities:
                if entity.label in ['ORG', 'PERSON']:
                    if not financial_data.company_name:
                        financial_data.company_name = entity.text
        
        # Extract financial figures using patterns
        for category, patterns in self.patterns.items():
            for pattern in patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    value_str = match.group(1)
                    value = self._parse_financial_value(value_str)
                    
                    if value > 0:
                        if category == 'revenue':
                            financial_data.revenue = max(financial_data.revenue, value)
                        elif category == 'profit':
                            financial_data.net_profit = max(financial_data.net_profit, value)
                        elif category == 'assets':
                            financial_data.total_assets = max(financial_data.total_assets, value)
                        elif category == 'liabilities':
                            financial_data.total_liabilities = max(financial_data.total_liabilities, value)
                        elif category == 'equity':
                            financial_data.equity = max(financial_data.equity, value)
        
        # Extract industry information
        industries = ['technology', 'manufacturing', 'healthcare', 'finance', 'retail', 'construction', 'agriculture']
        for industry in industries:
            if industry.lower() in text.lower():
                financial_data.industry = industry.capitalize()
                break
        
        # Extract year
        year_matches = re.findall(r'\b(19|20)\d{2}\b', text)
        if year_matches:
            financial_data.year = int(max(year_matches))
        
        # Calculate derived metrics
        if financial_data.total_assets > 0 and financial_data.total_liabilities > 0:
            financial_data.equity = financial_data.total_assets - financial_data.total_liabilities
        
        return financial_data

    def _extract_entities(self, text: str) -> List[DocumentEntity]:
        """Extract named entities using spaCy"""
        if not self.nlp:
            return []
        
        doc = self.nlp(text)
        entities = []
        
        for ent in doc.ents:
            entity = DocumentEntity(
                text=ent.text,
                label=ent.label_,
                confidence=0.8,  # spaCy doesn't provide confidence by default
                start_char=ent.start_char,
                end_char=ent.end_char
            )
            entities.append(entity)
        
        return entities

    def _parse_financial_value(self, value_str: str) -> float:
        """Parse financial value string to float"""
        # Remove commas and whitespace
        value_str = re.sub(r'[,\s]', '', value_str)
        
        # Extract number
        number_match = re.search(r'([\d.]+)', value_str)
        if not number_match:
            return 0.0
        
        number = float(number_match.group(1))
        
        # Handle multipliers
        if 'cr' in value_str.lower() or 'crore' in value_str.lower():
            number *= 10000000  # 1 crore = 10 million
        elif 'lakh' in value_str.lower():
            number *= 100000  # 1 lakh = 100,000
        elif 'billion' in value_str.lower():
            number *= 1000000000
        elif 'million' in value_str.lower():
            number *= 1000000
        
        return number

    def validate_extracted_data(self, data: FinancialData) -> Dict[str, Any]:
        """Validate extracted financial data"""
        validation_results = {
            'is_valid': True,
            'warnings': [],
            'errors': [],
            'confidence_score': data.confidence_score
        }
        
        # Check for reasonable values
        if data.revenue < 0:
            validation_results['errors'].append("Revenue cannot be negative")
            validation_results['is_valid'] = False
        
        if data.total_assets < data.total_liabilities:
            validation_results['warnings'].append("Liabilities exceed assets - potential financial distress")
        
        if data.revenue > 0 and data.net_profit > data.revenue:
            validation_results['warnings'].append("Net profit exceeds revenue - possible data extraction error")
        
        # Check for data completeness
        if data.revenue == 0:
            validation_results['warnings'].append("Revenue not found in document")
        
        if not data.company_name:
            validation_results['warnings'].append("Company name not identified")
        
        # Adjust confidence based on validation
        if validation_results['errors']:
            validation_results['confidence_score'] *= 0.5
        elif validation_results['warnings']:
            validation_results['confidence_score'] *= 0.8
        
        return validation_results

    def batch_process_documents(self, file_paths: List[str]) -> List[FinancialData]:
        """Process multiple documents in batch"""
        results = []
        
        for file_path in file_paths:
            try:
                data = self.process_document(file_path)
                validation = self.validate_extracted_data(data)
                
                # Add validation info
                data.validation_results = validation
                
                results.append(data)
                logger.info(f"Processed: {file_path} - Confidence: {data.confidence_score:.2f}")
                
            except Exception as e:
                logger.error(f"Failed to process {file_path}: {str(e)}")
                results.append(FinancialData())
        
        return results

# Usage example and testing
if __name__ == "__main__":
    # Initialize the data ingestor
    ingestor = DataIngestor()
    
    # Example usage
    test_file = "sample_document.pdf"
    if os.path.exists(test_file):
        result = ingestor.process_document(test_file)
        print(f"Company: {result.company_name}")
        print(f"Revenue: ₹{result.revenue:,.2f}")
        print(f"Confidence: {result.confidence_score:.2f}")
        print(f"Method: {result.extraction_method}")
    else:
        print("Test file not found")
