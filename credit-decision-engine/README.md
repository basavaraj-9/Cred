# AI Powered Credit Decisioning Engine

A comprehensive, production-grade credit decisioning system that automates the creation of Credit Appraisal Memos (CAM) and provides intelligent lending recommendations using AI and machine learning.

## 🚀 Features

### Core Modules
- **📄 Document Parser**: Extract financial data from PDFs, Excel files, and CSVs with OCR support
- **🔍 Financial Consistency Analyzer**: Detect circular trading, revenue inflation, and cash flow anomalies
- **🌐 Research Agent**: Automated web research for litigation, news sentiment, and sector analysis
- **⚡ Risk Scoring Engine**: ML-based credit scoring with explainable AI
- **📊 Recommendation Engine**: Generate loan decisions with interest rates and conditions
- **📋 CAM Generator**: Automated Credit Appraisal Memo generation in Word and PDF formats

### Key Capabilities
- Real-time risk assessment (0-100 scale)
- Five Cs of Credit analysis (Character, Capacity, Capital, Collateral, Conditions)
- Multi-document processing and analysis
- Explainable AI decisions with risk factor breakdown
- Sector-specific risk modeling
- Regulatory compliance features

## 🏗️ Architecture

### Backend (Python + FastAPI)
- **FastAPI**: Modern, fast web framework for APIs
- **PostgreSQL**: Robust database for data persistence
- **Redis**: Caching and session management
- **Scikit-learn**: Machine learning models
- **pdfplumber + Tesseract**: Document processing and OCR
- **python-docx + reportlab**: Report generation

### Frontend (React + TailwindCSS)
- **React 18**: Modern UI framework
- **TailwindCSS**: Utility-first CSS framework
- **Axios**: HTTP client for API calls
- **Lucide React**: Beautiful icons
- **React Router**: Client-side routing

### Infrastructure
- **Docker**: Containerization for easy deployment
- **Nginx**: Reverse proxy and load balancing
- **Docker Compose**: Multi-container orchestration

## 📁 Project Structure

```
credit-decision-engine/
├── backend/                    # FastAPI backend
│   ├── main.py               # Application entry point
│   ├── routes/               # API endpoints
│   │   ├── upload.py         # Document upload endpoints
│   │   ├── risk.py           # Risk analysis endpoints
│   │   ├── research.py       # Research endpoints
│   │   └── cam.py            # CAM generation endpoints
│   ├── services/             # Business logic
│   │   ├── document_parser.py
│   │   ├── gst_bank_analyzer.py
│   │   ├── research_agent.py
│   │   ├── risk_engine.py
│   │   └── recommendation_engine.py
│   ├── models/               # Data models
│   └── database/             # Database configuration
├── frontend/                  # React frontend
│   ├── src/
│   │   ├── pages/            # Main application pages
│   │   ├── components/       # Reusable components
│   │   └── api/              # API integration
├── ml_models/                 # Machine learning components
│   ├── train_model.py         # Model training script
│   └── scoring_pipeline.py   # Production scoring pipeline
├── cam_generator/             # Report generation
├── datasets/                  # Sample data
├── docker/                    # Docker configuration
└── README.md
```

## 🚀 Quick Start

### Prerequisites
- Docker and Docker Compose
- Python 3.11+ (for local development)
- Node.js 18+ (for frontend development)

### Using Docker Compose (Recommended)

1. **Clone the repository**
```bash
git clone <repository-url>
cd credit-decision-engine
```

2. **Start all services**
```bash
cd docker
docker-compose up -d
```

3. **Access the application**
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/docs

### Local Development Setup

#### Backend Setup

1. **Install Python dependencies**
```bash
cd backend
pip install -r requirements.txt
```

2. **Set up PostgreSQL database**
```bash
# Create database
createdb credit_decision_db

# Run schema
psql credit_decision_db < database/schema.sql
```

3. **Start the backend server**
```bash
cd backend
python main.py
```

#### Frontend Setup

1. **Install Node.js dependencies**
```bash
cd frontend
npm install
```

2. **Start the development server**
```bash
npm start
```

## 📊 Usage Guide

### 1. Document Upload
- Navigate to the Upload page
- Upload financial documents (PDF, Excel, CSV)
- Supported documents:
  - Annual reports
  - Bank statements
  - GST returns
  - Legal notices
  - Sanction letters

### 2. Risk Analysis
- View comprehensive risk assessment on Dashboard
- Risk score (0-100) with category classification
- Component-wise risk breakdown
- Financial metrics and ratios

### 3. Research Insights
- Automated company and sector research
- News sentiment analysis
- Litigation history check
- Promoter risk assessment

### 4. CAM Generation
- Generate Credit Appraisal Memo
- Download in Word and PDF formats
- Complete Five Cs analysis
- Professional report formatting

## 🔧 Configuration

### Environment Variables

#### Backend
```bash
DATABASE_URL=postgresql://user:password@localhost/credit_decision_db
REDIS_URL=redis://localhost:6379
CORS_ORIGINS=http://localhost:3000
```

#### Frontend
```bash
REACT_APP_API_URL=http://localhost:8000/api
```

## 🤖 Machine Learning Models

### Training the Model
```bash
cd ml_models
python train_model.py
```

### Using the Scoring Pipeline
```python
from ml_models.scoring_pipeline import CreditScoringPipeline

pipeline = CreditScoringPipeline()
result = pipeline.predict_default_probability(
    financial_data, risk_analysis, research_data, officer_input
)
```

## 📈 API Endpoints

### Document Management
- `POST /api/upload-documents` - Upload and parse documents
- `POST /api/analyze-company` - Analyze company financial data

### Risk Analysis
- `POST /api/consistency-analysis` - GST vs Bank consistency check
- `POST /api/risk-score` - Calculate comprehensive risk score
- `POST /api/recommendation` - Generate lending recommendation

### Research
- `POST /api/research-insights` - Perform company research
- `GET /api/sector-outlook/{sector}` - Get sector analysis
- `GET /api/litigation-check/{company}` - Check litigation history

### CAM Generation
- `POST /api/generate-cam` - Generate Credit Appraisal Memo
- `GET /api/download-cam/{filename}` - Download CAM files

## 🔒 Security Features

- Input validation and sanitization
- Rate limiting on API endpoints
- CORS configuration
- File upload restrictions
- SQL injection prevention
- XSS protection

## 📊 Monitoring & Logging

- Structured logging with correlation IDs
- Health check endpoints
- Performance metrics
- Error tracking
- Audit logs for compliance

## 🧪 Testing

### Backend Tests
```bash
cd backend
pytest tests/
```

### Frontend Tests
```bash
cd frontend
npm test
```

## 🚀 Deployment

### Production Deployment

1. **Configure environment variables**
2. **Set up SSL certificates**
3. **Update nginx configuration**
4. **Deploy with Docker Compose**
```bash
docker-compose -f docker/docker-compose.yml up -d
```

### Scaling Considerations
- Load balancing with multiple backend instances
- Database connection pooling
- Redis clustering for caching
- CDN for static assets

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For support and questions:
- Create an issue in the repository
- Check the API documentation at `/docs`
- Review the troubleshooting guide

## 🗺️ Roadmap

### Phase 1 (Current)
- ✅ Core credit decisioning engine
- ✅ Document processing and OCR
- ✅ Risk scoring and recommendation
- ✅ CAM generation

### Phase 2 (Planned)
- 🔄 Advanced fraud detection
- 🔄 Real-time market data integration
- 🔄 Multi-language support
- 🔄 Mobile application

### Phase 3 (Future)
- 📋 AI-powered chatbot for queries
- 📋 Advanced sector risk prediction
- 📋 Integration with banking systems
- 📋 Regulatory reporting automation

## 📊 Performance Metrics

- **Document Processing**: < 30 seconds per document
- **Risk Analysis**: < 5 seconds
- **CAM Generation**: < 10 seconds
- **API Response Time**: < 2 seconds (95th percentile)
- **System Uptime**: 99.9%

---

**Built with ❤️ for the future of credit decisioning**
