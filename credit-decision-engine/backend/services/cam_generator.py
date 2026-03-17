"""
CAM Generator Module - Credit Appraisal Memo Generation
Automatically generates comprehensive Credit Appraisal Memos in PDF and Word formats
"""

import os
import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import logging
from pathlib import Path

# PDF Generation Libraries
try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.pdfgen import canvas
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    logging.warning("PDF libraries not available. Install: pip install reportlab")

# Word Document Libraries  
try:
    from docx import Document
    from docx.shared import Inches, Pt
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_TABLE_ALIGNMENT
    WORD_AVAILABLE = True
except ImportError:
    WORD_AVAILABLE = False
    logging.warning("Word libraries not available. Install: pip install python-docx")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class CAMContent:
    """Content structure for Credit Appraisal Memo"""
    borrower_info: Dict[str, Any]
    industry_analysis: Dict[str, Any]
    financial_analysis: Dict[str, Any]
    risk_assessment: Dict[str, Any]
    research_insights: Dict[str, Any]
    recommendation: Dict[str, Any]
    five_cs_analysis: Dict[str, Any]
    compliance_notes: List[str]
    generated_at: datetime

class CAMGenerator:
    """Comprehensive Credit Appraisal Memo Generator"""
    
    def __init__(self, output_dir: str = "cam_outputs"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # CAM template structure
        self.cam_sections = [
            "borrower_profile",
            "industry_analysis", 
            "financial_analysis",
            "risk_assessment",
            "research_insights",
            "five_cs_analysis",
            "recommendation_summary",
            "compliance_notes",
            "appendices"
        ]
        
        # Initialize document styles
        self.styles = self._initialize_styles()
    
    def generate_cam(self, cam_content: CAMContent, 
                    output_format: str = "both", 
                    filename: Optional[str] = None) -> Dict[str, str]:
        """
        Generate Credit Appraisal Memo in specified format(s)
        
        Args:
            cam_content: Structured CAM content
            output_format: 'pdf', 'word', or 'both'
            filename: Optional custom filename
            
        Returns:
            Dictionary with file paths of generated documents
        """
        
        logger.info(f"Generating CAM in format: {output_format}")
        
        # Generate filename if not provided
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            company_name = cam_content.borrower_info.get('company_name', 'Unknown').replace(' ', '_')
            filename = f"CAM_{company_name}_{timestamp}"
        
        output_files = {}
        
        # Generate PDF
        if output_format in ['pdf', 'both'] and PDF_AVAILABLE:
            pdf_path = self._generate_pdf_cam(cam_content, filename)
            if pdf_path:
                output_files['pdf'] = pdf_path
        
        # Generate Word document
        if output_format in ['word', 'both'] and WORD_AVAILABLE:
            word_path = self._generate_word_cam(cam_content, filename)
            if word_path:
                output_files['word'] = word_path
        
        # Generate JSON for API integration
        json_path = self._generate_json_cam(cam_content, filename)
        if json_path:
            output_files['json'] = json_path
        
        logger.info(f"CAM generation completed. Files: {list(output_files.keys())}")
        
        return output_files
    
    def _initialize_styles(self) -> Dict[str, Any]:
        """Initialize document styles for CAM formatting"""
        
        styles = {}
        
        if PDF_AVAILABLE:
            pdf_styles = getSampleStyleSheet()
            
            # Custom styles for CAM
            styles['title'] = ParagraphStyle(
                'CAMTitle',
                parent=pdf_styles['Heading1'],
                fontSize=16,
                spaceAfter=30,
                alignment=1,  # Center
                textColor=colors.darkblue
            )
            
            styles['heading'] = ParagraphStyle(
                'CAMHeading',
                parent=pdf_styles['Heading2'],
                fontSize=14,
                spaceAfter=12,
                spaceBefore=20,
                textColor=colors.darkblue
            )
            
            styles['subheading'] = ParagraphStyle(
                'CAMSubheading',
                parent=pdf_styles['Heading3'],
                fontSize=12,
                spaceAfter=8,
                spaceBefore=12,
                textColor=colors.black
            )
            
            styles['body'] = ParagraphStyle(
                'CAMBody',
                parent=pdf_styles['Normal'],
                fontSize=10,
                spaceAfter=6,
                leading=14
            )
            
            styles['highlight'] = ParagraphStyle(
                'CAMHighlight',
                parent=pdf_styles['Normal'],
                fontSize=10,
                spaceAfter=6,
                leading=14,
                textColor=colors.red,
                fontName='Helvetica-Bold'
            )
        
        return styles
    
    def _generate_pdf_cam(self, cam_content: CAMContent, filename: str) -> Optional[str]:
        """Generate CAM in PDF format"""
        
        if not PDF_AVAILABLE:
            return None
        
        try:
            pdf_path = self.output_dir / f"{filename}.pdf"
            doc = SimpleDocTemplate(str(pdf_path), pagesize=A4)
            
            # Build PDF content
            story = []
            
            # Title page
            story.extend(self._create_pdf_title_page(cam_content))
            story.append(PageBreak())
            
            # Main sections
            for section in self.cam_sections:
                section_content = getattr(self, f"_create_pdf_{section}")(cam_content)
                if section_content:
                    story.extend(section_content)
                    story.append(Spacer(1, 12))
            
            # Build PDF
            doc.build(story)
            
            logger.info(f"PDF CAM generated: {pdf_path}")
            return str(pdf_path)
            
        except Exception as e:
            logger.error(f"Error generating PDF CAM: {str(e)}")
            return None
    
    def _generate_word_cam(self, cam_content: CAMContent, filename: str) -> Optional[str]:
        """Generate CAM in Word format"""
        
        if not WORD_AVAILABLE:
            return None
        
        try:
            word_path = self.output_dir / f"{filename}.docx"
            doc = Document()
            
            # Title page
            self._create_word_title_page(doc, cam_content)
            
            # Main sections
            for section in self.cam_sections:
                self._create_word_section(doc, section, cam_content)
            
            # Save document
            doc.save(str(word_path))
            
            logger.info(f"Word CAM generated: {word_path}")
            return str(word_path)
            
        except Exception as e:
            logger.error(f"Error generating Word CAM: {str(e)}")
            return None
    
    def _generate_json_cam(self, cam_content: CAMContent, filename: str) -> Optional[str]:
        """Generate CAM in JSON format for API integration"""
        
        try:
            json_path = self.output_dir / f"{filename}.json"
            
            # Convert CAM content to JSON-serializable format
            cam_data = {
                'borrower_info': cam_content.borrower_info,
                'industry_analysis': cam_content.industry_analysis,
                'financial_analysis': cam_content.financial_analysis,
                'risk_assessment': cam_content.risk_assessment,
                'research_insights': cam_content.research_insights,
                'recommendation': cam_content.recommendation,
                'five_cs_analysis': cam_content.five_cs_analysis,
                'compliance_notes': cam_content.compliance_notes,
                'generated_at': cam_content.generated_at.isoformat(),
                'cam_version': '1.0'
            }
            
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(cam_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"JSON CAM generated: {json_path}")
            return str(json_path)
            
        except Exception as e:
            logger.error(f"Error generating JSON CAM: {str(e)}")
            return None
    
    def _create_pdf_title_page(self, cam_content: CAMContent) -> List[Any]:
        """Create title page for PDF CAM"""
        
        content = []
        
        # Main title
        content.append(Paragraph("CREDIT APPRAISAL MEMORANDUM", self.styles['title']))
        content.append(Spacer(1, 20))
        
        # Subtitle
        borrower_name = cam_content.borrower_info.get('company_name', 'Unknown Company')
        content.append(Paragraph(f"Borrower: {borrower_name}", self.styles['heading']))
        
        # Generation details
        content.append(Spacer(1, 30))
        content.append(Paragraph(f"Generated on: {cam_content.generated_at.strftime('%d %B %Y')}", self.styles['body']))
        content.append(Paragraph(f"Generated by: AI Credit Decisioning Engine", self.styles['body']))
        content.append(Paragraph(f"Version: 1.0", self.styles['body']))
        
        # Confidential notice
        content.append(Spacer(1, 50))
        content.append(Paragraph("CONFIDENTIAL & PROPRIETARY", self.styles['highlight']))
        content.append(Paragraph("This document contains confidential information and is intended for internal use only.", 
                              self.styles['body']))
        
        return content
    
    def _create_word_title_page(self, doc: Any, cam_content: CAMContent) -> None:
        """Create title page for Word CAM"""
        
        # Main title
        title = doc.add_heading('CREDIT APPRAISAL MEMORANDUM', 0)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # Subtitle
        borrower_name = cam_content.borrower_info.get('company_name', 'Unknown Company')
        subtitle = doc.add_heading(f'Borrower: {borrower_name}', 1)
        subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # Generation details
        doc.add_paragraph()
        doc.add_paragraph(f'Generated on: {cam_content.generated_at.strftime("%d %B %Y")}')
        doc.add_paragraph('Generated by: AI Credit Decisioning Engine')
        doc.add_paragraph('Version: 1.0')
        
        # Confidential notice
        doc.add_paragraph()
        conf_para = doc.add_paragraph('CONFIDENTIAL & PROPRIETARY')
        conf_para.runs[0].bold = True
        conf_para.runs[0].font.color.rgb = (255, 0, 0)  # Red color
        
        doc.add_paragraph('This document contains confidential information and is intended for internal use only.')
        
        # Page break
        doc.add_page_break()
    
    def _create_pdf_borrower_profile(self, cam_content: CAMContent) -> List[Any]:
        """Create borrower profile section for PDF"""
        
        content = []
        content.append(Paragraph("1. BORROWER PROFILE", self.styles['heading']))
        
        borrower = cam_content.borrower_info
        
        # Company information table
        company_data = [
            ['Company Name', borrower.get('company_name', 'N/A')],
            ['Legal Structure', borrower.get('legal_structure', 'N/A')],
            ['Industry', borrower.get('industry', 'N/A')],
            ['Year Established', borrower.get('year_established', 'N/A')],
            ['Registered Office', borrower.get('registered_office', 'N/A')],
            ['Promoter(s)', ', '.join(borrower.get('promoters', []))],
            ['Authorized Capital', f"₹{borrower.get('authorized_capital', 0):,.0f}"],
            ['Paid-up Capital', f"₹{borrower.get('paid_up_capital', 0):,.0f}"]
        ]
        
        company_table = Table(company_data, colWidths=[2.5*inch, 4*inch])
        company_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.lightblue),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        content.append(company_table)
        content.append(Spacer(1, 12))
        
        # Business overview
        content.append(Paragraph("Business Overview", self.styles['subheading']))
        business_desc = borrower.get('business_description', 'No business description available.')
        content.append(Paragraph(business_desc, self.styles['body']))
        
        return content
    
    def _create_word_section(self, doc: Any, section: str, cam_content: CAMContent) -> None:
        """Create a section in Word document"""
        
        section_titles = {
            'borrower_profile': '1. BORROWER PROFILE',
            'industry_analysis': '2. INDUSTRY ANALYSIS',
            'financial_analysis': '3. FINANCIAL ANALYSIS',
            'risk_assessment': '4. RISK ASSESSMENT',
            'research_insights': '5. RESEARCH INSIGHTS',
            'five_cs_analysis': '6. FIVE CS OF CREDIT',
            'recommendation_summary': '7. RECOMMENDATION SUMMARY',
            'compliance_notes': '8. COMPLIANCE NOTES',
            'appendices': '9. APPENDICES'
        }
        
        # Add section heading
        doc.add_heading(section_titles.get(section, section.upper()), 1)
        
        # Add section content based on section type
        if section == 'borrower_profile':
            self._add_word_borrower_profile(doc, cam_content)
        elif section == 'industry_analysis':
            self._add_word_industry_analysis(doc, cam_content)
        elif section == 'financial_analysis':
            self._add_word_financial_analysis(doc, cam_content)
        elif section == 'risk_assessment':
            self._add_word_risk_assessment(doc, cam_content)
        elif section == 'research_insights':
            self._add_word_research_insights(doc, cam_content)
        elif section == 'five_cs_analysis':
            self._add_word_five_cs_analysis(doc, cam_content)
        elif section == 'recommendation_summary':
            self._add_word_recommendation(doc, cam_content)
        elif section == 'compliance_notes':
            self._add_word_compliance_notes(doc, cam_content)
        
        doc.add_paragraph()
    
    def _add_word_borrower_profile(self, doc: Any, cam_content: CAMContent) -> None:
        """Add borrower profile to Word document"""
        
        borrower = cam_content.borrower_info
        
        # Company information table
        table = doc.add_table(rows=8, cols=2)
        table.style = 'Table Grid'
        
        company_data = [
            ('Company Name', borrower.get('company_name', 'N/A')),
            ('Legal Structure', borrower.get('legal_structure', 'N/A')),
            ('Industry', borrower.get('industry', 'N/A')),
            ('Year Established', borrower.get('year_established', 'N/A')),
            ('Registered Office', borrower.get('registered_office', 'N/A')),
            ('Promoter(s)', ', '.join(borrower.get('promoters', []))),
            ('Authorized Capital', f"₹{borrower.get('authorized_capital', 0):,.0f}"),
            ('Paid-up Capital', f"₹{borrower.get('paid_up_capital', 0):,.0f}")
        ]
        
        for i, (label, value) in enumerate(company_data):
            table.cell(i, 0).text = label
            table.cell(i, 1).text = str(value)
            table.cell(i, 0).paragraphs[0].runs[0].bold = True
        
        # Business overview
        doc.add_heading('Business Overview', level=2)
        business_desc = borrower.get('business_description', 'No business description available.')
        doc.add_paragraph(business_desc)
    
    def _add_word_industry_analysis(self, doc: Any, cam_content: CAMContent) -> None:
        """Add industry analysis to Word document"""
        
        industry = cam_content.industry_analysis
        
        # Industry overview
        doc.add_heading('Industry Overview', level=2)
        doc.add_paragraph(industry.get('overview', 'No industry overview available.'))
        
        # Market position
        doc.add_heading('Market Position', level=2)
        doc.add_paragraph(industry.get('market_position', 'No market position data available.'))
        
        # Industry risks
        doc.add_heading('Industry Risks', level=2)
        risks = industry.get('risks', [])
        if risks:
            for risk in risks:
                doc.add_paragraph(f"• {risk}", style='List Bullet')
        else:
            doc.add_paragraph('No specific industry risks identified.')
    
    def _add_word_financial_analysis(self, doc: Any, cam_content: CAMContent) -> None:
        """Add financial analysis to Word document"""
        
        financial = cam_content.financial_analysis
        
        # Key financial metrics
        doc.add_heading('Key Financial Metrics', level=2)
        
        # Create financial metrics table
        metrics = financial.get('key_metrics', {})
        if metrics:
            table = doc.add_table(rows=len(metrics), cols=2)
            table.style = 'Table Grid'
            
            for i, (metric, value) in enumerate(metrics.items()):
                table.cell(i, 0).text = metric.replace('_', ' ').title()
                table.cell(i, 1).text = str(value)
                table.cell(i, 0).paragraphs[0].runs[0].bold = True
        
        # Financial performance
        doc.add_heading('Financial Performance', level=2)
        performance = financial.get('performance_analysis', 'No performance analysis available.')
        doc.add_paragraph(performance)
        
        # Financial ratios
        doc.add_heading('Financial Ratios', level=2)
        ratios = financial.get('ratios', {})
        if ratios:
            for ratio, value in ratios.items():
                doc.add_paragraph(f"{ratio.replace('_', ' ').title()}: {value}")
    
    def _add_word_risk_assessment(self, doc: Any, cam_content: CAMContent) -> None:
        """Add risk assessment to Word document"""
        
        risk = cam_content.risk_assessment
        
        # Overall risk score
        doc.add_heading('Overall Risk Assessment', level=2)
        doc.add_paragraph(f"Risk Score: {risk.get('overall_score', 'N/A')}/100")
        doc.add_paragraph(f"Risk Category: {risk.get('risk_category', 'N/A')}")
        doc.add_paragraph(f"Default Probability: {risk.get('default_probability', 'N/A'):.2%}")
        
        # Risk factors
        doc.add_heading('Key Risk Factors', level=2)
        risk_factors = risk.get('risk_factors', [])
        if risk_factors:
            for factor in risk_factors:
                doc.add_paragraph(f"• {factor}", style='List Bullet')
        
        # Positive factors
        doc.add_heading('Positive Factors', level=2)
        positive_factors = risk.get('positive_factors', [])
        if positive_factors:
            for factor in positive_factors:
                doc.add_paragraph(f"• {factor}", style='List Bullet')
    
    def _add_word_research_insights(self, doc: Any, cam_content: CAMContent) -> None:
        """Add research insights to Word document"""
        
        research = cam_content.research_insights
        
        # Market sentiment
        doc.add_heading('Market Sentiment', level=2)
        doc.add_paragraph(f"News Sentiment: {research.get('news_sentiment', 'N/A')}")
        doc.add_paragraph(f"Litigation Cases: {research.get('litigation_cases', 0)}")
        
        # Promoter assessment
        doc.add_heading('Promoter Assessment', level=2)
        doc.add_paragraph(f"Promoter Risk: {research.get('promoter_risk', 'N/A')}")
        
        # ESG assessment
        doc.add_heading('ESG Assessment', level=2)
        doc.add_paragraph(f"ESG Score: {research.get('esg_score', 'N/A')}/100")
    
    def _add_word_five_cs_analysis(self, doc: Any, cam_content: CAMContent) -> None:
        """Add Five Cs of Credit analysis to Word document"""
        
        five_cs = cam_content.five_cs_analysis
        
        for c_category, c_data in five_cs.items():
            doc.add_heading(c_category.upper(), level=2)
            doc.add_paragraph(c_data.get('analysis', f'No analysis available for {c_category}.'))
            doc.add_paragraph(f"Score: {c_data.get('score', 'N/A')}/10")
    
    def _add_word_recommendation(self, doc: Any, cam_content: CAMContent) -> None:
        """Add recommendation summary to Word document"""
        
        recommendation = cam_content.recommendation
        
        # Decision
        doc.add_heading('Credit Decision', level=2)
        decision = recommendation.get('decision', 'N/A')
        doc.add_paragraph(decision)
        
        # Make the decision stand out
        if 'Approved' in decision:
            doc.add_paragraph('DECISION: APPROVED').bold = True
        elif 'Rejected' in decision:
            doc.add_paragraph('DECISION: REJECTED').bold = True
        else:
            doc.add_paragraph('DECISION: CONDITIONAL APPROVAL').bold = True
        
        # Loan terms
        doc.add_heading('Recommended Loan Terms', level=2)
        loan_amount = recommendation.get('loan_amount', 0)
        interest_rate = recommendation.get('interest_rate', 0)
        tenure = recommendation.get('tenure_months', 0)
        
        doc.add_paragraph(f"Loan Amount: ₹{loan_amount:,.0f}")
        doc.add_paragraph(f"Interest Rate: {interest_rate}%")
        doc.add_paragraph(f"Tenure: {tenure} months")
        
        # Conditions
        doc.add_heading('Conditions & Covenants', level=2)
        conditions = recommendation.get('conditions', [])
        if conditions:
            for condition in conditions:
                doc.add_paragraph(f"• {condition}", style='List Bullet')
    
    def _add_word_compliance_notes(self, doc: Any, cam_content: CAMContent) -> None:
        """Add compliance notes to Word document"""
        
        doc.add_heading('Compliance & Regulatory Notes', level=2)
        
        compliance_notes = cam_content.compliance_notes
        if compliance_notes:
            for note in compliance_notes:
                doc.add_paragraph(f"• {note}", style='List Bullet')
        else:
            doc.add_paragraph('No specific compliance notes.')
    
    def create_cam_content(self, borrower_info: Dict, industry_analysis: Dict,
                          financial_analysis: Dict, risk_assessment: Dict,
                          research_insights: Dict, recommendation: Dict,
                          five_cs_analysis: Dict, compliance_notes: List[str]) -> CAMContent:
        """
        Create CAM content structure from various analysis components
        """
        
        return CAMContent(
            borrower_info=borrower_info,
            industry_analysis=industry_analysis,
            financial_analysis=financial_analysis,
            risk_assessment=risk_assessment,
            research_insights=research_insights,
            recommendation=recommendation,
            five_cs_analysis=five_cs_analysis,
            compliance_notes=compliance_notes,
            generated_at=datetime.now()
        )
    
    def generate_sample_cam(self) -> Dict[str, str]:
        """Generate a sample CAM for testing purposes"""
        
        # Sample data
        borrower_info = {
            'company_name': 'Tech Innovations Pvt Ltd',
            'legal_structure': 'Private Limited',
            'industry': 'Technology',
            'year_established': '2015',
            'registered_office': 'Bangalore, Karnataka',
            'promoters': ['John Doe', 'Jane Smith'],
            'authorized_capital': 10000000,
            'paid_up_capital': 5000000,
            'business_description': 'Leading software development company specializing in AI and machine learning solutions.'
        }
        
        industry_analysis = {
            'overview': 'The technology sector in India is growing rapidly with increasing demand for digital transformation.',
            'market_position': 'Mid-tier player with strong growth potential',
            'risks': ['High competition', 'Technology obsolescence', 'Talent retention challenges']
        }
        
        financial_analysis = {
            'key_metrics': {
                'annual_revenue': 50000000,
                'net_profit': 8000000,
                'total_assets': 30000000,
                'total_liabilities': 12000000,
                'debt_to_equity': 0.67
            },
            'performance_analysis': 'Strong revenue growth of 25% YoY with improving profitability margins.',
            'ratios': {
                'current_ratio': 2.1,
                'debt_service_coverage': 1.8,
                'return_on_equity': 0.26
            }
        }
        
        risk_assessment = {
            'overall_score': 72,
            'risk_category': 'Medium',
            'default_probability': 0.08,
            'risk_factors': ['High competition in technology sector', 'Dependence on key personnel'],
            'positive_factors': ['Strong financial performance', 'Experienced management team']
        }
        
        research_insights = {
            'news_sentiment': 'Positive',
            'litigation_cases': 0,
            'promoter_risk': 'Low',
            'esg_score': 75
        }
        
        recommendation = {
            'decision': 'Approved',
            'loan_amount': 15000000,
            'interest_rate': 11.5,
            'tenure_months': 48,
            'conditions': [
                'Quarterly financial statements submission',
                'Maintain debt-to-equity ratio below 1.5',
                'No change in promoters without lender consent'
            ]
        }
        
        five_cs_analysis = {
            'character': {
                'analysis': 'Strong management team with good track record and reputation.',
                'score': 8
            },
            'capacity': {
                'analysis': 'Good cash flow generation and debt servicing capacity.',
                'score': 7
            },
            'capital': {
                'analysis': 'Adequate capital base with reasonable leverage.',
                'score': 7
            },
            'collateral': {
                'analysis': 'Limited tangible collateral available.',
                'score': 5
            },
            'conditions': {
                'analysis': 'Favorable industry conditions with growth prospects.',
                'score': 8
            }
        }
        
        compliance_notes = [
            'All statutory filings up to date',
            'No regulatory violations observed',
            'GST compliance verified',
            'Bank account statements reconciled'
        ]
        
        # Create CAM content
        cam_content = self.create_cam_content(
            borrower_info, industry_analysis, financial_analysis,
            risk_assessment, research_insights, recommendation,
            five_cs_analysis, compliance_notes
        )
        
        # Generate CAM
        return self.generate_cam(cam_content, output_format='both', filename='sample_cam')

# Usage example
if __name__ == "__main__":
    # Initialize CAM generator
    generator = CAMGenerator()
    
    # Generate sample CAM
    output_files = generator.generate_sample_cam()
    
    print("Sample CAM Generated:")
    for format_type, file_path in output_files.items():
        print(f"{format_type.upper()}: {file_path}")
