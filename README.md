# UFDR AI Analyzer

An advanced AI-powered forensic analysis system for processing Universal Forensic Data Reader (UFDR) files. Features intelligent query processing, dynamic data visualization, and comprehensive forensic investigation capabilities.

## 🚀 Features

### Core Capabilities
- **UFDR File Processing**: Upload and analyze forensic data from mobile devices
- **AI-Powered Natural Language Queries**: Ask questions in plain English about forensic data
- **Dynamic Response Generation**: LLM-driven responses with expandable data blocks
- **Comprehensive Reporting**: Generate detailed forensic investigation reports
- **PDF Export**: Download professional reports for case documentation
- **Modern Web Interface**: Clean, responsive React-based frontend with interactive data blocks

### Advanced Analysis Features
- **Intelligent Query Processing**: Scalable LLM-based responses for any query type
- **Full Message Content Display**: Complete chat messages and detailed record information
- **Expandable Data Blocks**: Click-to-expand interface for detailed forensic data
- **Communication Analysis**: Detect suspicious patterns and relationships
- **Timeline Analysis**: Chronological event mapping
- **Network Mapping**: Identify key players and communication hubs
- **Evidence Detection**: Highlight potential criminal activities

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   React.js      │    │   FastAPI       │    │   Databases     │
│   Frontend      │◄──►│   Backend       │◄──►│                 │
│                 │    │                 │    │ • PostgreSQL    │
│ • Interactive   │    │ • UFDR Parser   │    │ • Qdrant        │
│   Data Blocks   │    │ • AI Service    │    │ • Neo4j         │
│ • Query UI      │    │ • Data Processor│    │ • Redis         │
│ • Report Gen    │    │ • Schema Service│    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Key Components
- **AI Service**: LLM-powered query processing with dynamic response generation
- **Data Processor**: UFDR file parsing and data extraction
- **Schema Service**: Dynamic schema detection and management
- **Vector Service**: Semantic search and embeddings
- **Case Manager**: Case lifecycle and data organization

## 📊 Data Flow Pipeline

### 1. File Upload & Processing
```
UFDR File Upload
       ↓
   File Validation (.ufdr only)
       ↓
   Temporary File Storage
       ↓
   UFDR Parser (Multi-format support)
       ↓
   Data Extraction & Normalization
```

### 2. Case Environment Setup
```
Case Number + Investigator
       ↓
   Case Manager
       ↓
   Create Case-Specific Environment:
   • PostgreSQL Schema (case_{safe_name})
   • Qdrant Collection (case_{safe_name})
   • Neo4j Namespace (case_{safe_name})
```

### 3. Data Storage Pipeline
```
Parsed UFDR Data
       ↓
   ┌─────────────────────────────────────┐
   │         Multi-Database Storage      │
   ├─────────────────────────────────────┤
   │ PostgreSQL: Structured Data         │
   │ • UFDR Reports                      │
   │ • Chat Records                      │
   │ • Call Records                      │
   │ • Contacts                          │
   │ • Media Files                       │
   ├─────────────────────────────────────┤
   │ Qdrant: Vector Embeddings           │
   │ • Semantic Search Vectors          │
   │ • Content Embeddings                │
   │ • Metadata Vectors                  │
   ├─────────────────────────────────────┤
   │ Neo4j: Relationship Graph           │
   │ • Person Nodes                      │
   │ • Communication Relationships       │
   │ • Network Analysis                  │
   └─────────────────────────────────────┘
```

### 4. AI Query Processing
```
Natural Language Query
       ↓
   AI Service (Query Analysis)
       ↓
   ┌─────────────────────────────────────┐
   │        Intelligent Routing          │
   ├─────────────────────────────────────┤
   │ SQL-Only: Simple data queries       │
   │ Semantic-Only: Complex analysis     │
   │ Hybrid: Combined approach           │
   └─────────────────────────────────────┘
       ↓
   ┌─────────────────────────────────────┐
   │         Data Retrieval              │
   ├─────────────────────────────────────┤
   │ PostgreSQL: Structured queries      │
   │ Qdrant: Semantic similarity         │
   │ Neo4j: Relationship analysis        │
   └─────────────────────────────────────┘
       ↓
   LLM Response Generation
       ↓
   Structured Data Rendering
```

### 5. Report Generation
```
Report Request
       ↓
   Data Aggregation (All Sources)
       ↓
   AI Analysis & Risk Assessment
       ↓
   ┌─────────────────────────────────────┐
   │         Report Types                │
   ├─────────────────────────────────────┤
   │ • Comprehensive Analysis            │
   │ • Criminal Risk Assessment         │
   │ • Key Findings                     │
   │ • Recommendations                  │
   │ • PDF Export                        │
   └─────────────────────────────────────┘
```

## 🛠️ Technology Stack

### Backend
- **FastAPI**: Modern Python web framework
- **SQLAlchemy**: Database ORM and migrations
- **Pydantic**: Data validation and serialization
- **Google Gemini**: LLM for natural language processing
- **Qdrant**: Vector database for semantic search
- **Neo4j**: Graph database for relationships
- **Redis**: Caching and session management

### Frontend
- **React 18**: Modern JavaScript framework
- **React Router**: Client-side routing
- **Axios**: HTTP client for API communication
- **Lucide React**: Modern icon library
- **CSS3**: Custom styling and animations

### AI & ML
- **Google Gemini 2.5 Pro**: Large language model
- **BAAI/bge-large-en-v1.5**: Local embedding model
- **FastEmbed**: Efficient embedding generation
- **Vector Search**: Semantic similarity matching

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Node.js 16+
- Docker & Docker Compose

### Easy Setup (Windows)

1. **Clone the repository**
```bash
git clone <repository-url>
cd ufdr-ai-analyzer
```

2. **Install Python dependencies**
```bash
pip install -r requirements.txt
```

3. **Start the system**
```bash
docker-compose up -d
python backend/main.py
```

4. **Start Frontend (in new terminal)**
```bash
cd frontend
npm install
npm start
```

This will:
- Start the backend server on http://localhost:8000
- Start the frontend on http://localhost:3000
- Start all required databases (PostgreSQL, Qdrant, Neo4j, Redis)

## 📋 Usage

### Web Interface
1. Open http://localhost:3000 in your browser
2. Upload a UFDR file with case information
3. Use the AI Analyzer to ask questions like:
   - "Find WhatsApp messages about meetings"
   - "Who sent verification codes?"
   - "Show me suspicious communications"
4. Generate and download comprehensive PDF reports

### Sample Queries
- **Evidence Count**: "How many evidences are there?" → Shows detailed breakdown by category
- **Message Analysis**: "Show me all WhatsApp messages" → Displays expandable blocks with full message content
- **Meeting Analysis**: "Find messages about meetings" → Shows relevant chat records with complete messages
- **Security Threats**: "Show me verification codes" → Displays verification-related communications
- **Suspicious Activity**: "Analyze suspicious communications" → Provides pattern analysis and insights
- **Network Analysis**: "Show me communication patterns" → Maps relationships and connections
- **Call Records**: "Show me all call records" → Displays call details with duration and type
- **Media Files**: "What media files are there?" → Shows file details with sizes and types

## 🔧 API Endpoints

### Core Endpoints
- **Health Check**: `GET /api/v1/health`
- **Upload File**: `POST /api/v1/upload-ufdr`
- **Query Data**: `GET /api/v1/quick-query?q=<query>`
- **Generate Report**: `POST /api/v1/generate-comprehensive-report`
- **Download PDF**: `POST /api/v1/generate-pdf-report`

### Case Management
- **List Cases**: `GET /api/v1/case/list`
- **Case Info**: `GET /api/v1/case/{case_number}/info`
- **Case Counts**: `GET /api/v1/case/{case_number}/counts`
- **Clear Case**: `DELETE /api/v1/case/{case_number}/data`

### Advanced Features
- **Semantic Search**: `GET /api/v1/search/semantic`
- **Graph Network**: `GET /api/v1/graph/network/{case_id}`
- **Schema Management**: `GET /api/v1/schema/summary/{case_number}`
- **Data Cleanup**: `POST /api/v1/data/remove-duplicates/{case_number}`

## 🗄️ Database Architecture

### PostgreSQL (Structured Data)
Each case gets a dedicated schema: `case_{safe_case_name}`

**Tables:**
- `ufdr_reports` - Case metadata and file information
- `chat_records` - Message data with full content
- `call_records` - Call logs with duration and type
- `contacts` - Contact information and relationships
- `media_files` - File metadata and storage paths

### Qdrant (Vector Database)
Case-specific collections: `case_{safe_case_name}`

**Features:**
- 768-dimensional embeddings using BAAI/bge-large-en-v1.5
- Semantic similarity search
- Metadata filtering
- Content-based retrieval

### Neo4j (Graph Database)
Case-specific namespaces with labeled nodes

**Graph Structure:**
- Person nodes with contact information
- Communication relationships with strength scoring
- Network analysis and path finding
- Relationship pattern detection

### Redis (Caching)
- Query result caching
- Session management
- Performance optimization

## 🔒 Security & Data Management

### Case Isolation
- **Complete Separation**: No data leakage between cases
- **Schema Isolation**: Dedicated database schemas per case
- **Collection Isolation**: Separate vector collections
- **Namespace Isolation**: Case-specific graph namespaces

### Data Protection
- **SQL Injection Prevention**: Parameterized queries
- **Input Validation**: Strict file type and content validation
- **Access Control**: Case-based data access
- **Audit Trails**: Comprehensive logging and tracking

## 🎯 Use Cases

### 1. Criminal Investigations
- **Communication Analysis**: Message content and patterns
- **Network Mapping**: Relationship identification
- **Evidence Collection**: Automated evidence gathering
- **Timeline Analysis**: Chronological event reconstruction

### 2. Digital Forensics
- **Device Analysis**: Hardware and software information
- **Data Recovery**: Deleted message and file recovery
- **Metadata Analysis**: File and communication metadata
- **Pattern Recognition**: Suspicious activity detection

### 3. Law Enforcement
- **Case Management**: Organized investigation workflows
- **Report Generation**: Professional documentation
- **Evidence Presentation**: Court-ready materials
- **Collaboration**: Multi-investigator case sharing

## 🔧 Configuration

### Environment Variables
Create a `.env` file with the following configuration:

```env
# Database Configuration
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=ufdr_analysis
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password

# Qdrant Configuration
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=your_api_key

# Neo4j Configuration
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password

# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=your_password

# AI Configuration
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=models/gemini-2.5-pro

# Application Configuration
APP_HOST=0.0.0.0
APP_PORT=8000
DEBUG=True
LOG_LEVEL=INFO
```

## 🚀 Deployment

### Production Deployment

1. **Update environment variables for production**
2. **Build the frontend:**
   ```bash
   cd frontend
   npm run build
   ```
3. **Deploy using Docker:**
   ```bash
   docker-compose -f docker-compose.prod.yml up -d
   ```

### Security Considerations
- Use strong passwords for all databases
- Enable SSL/TLS for all connections
- Implement proper authentication and authorization
- Regularly update dependencies
- Monitor system logs and access

## 🐛 Troubleshooting

### Common Issues

1. **Database Connection Errors**
   - Ensure Docker containers are running
   - Check database credentials in `.env`
   - Verify network connectivity

2. **API Key Errors**
   - Verify Gemini API key configuration
   - Check API quotas and limits
   - Ensure proper permissions

3. **File Upload Issues**
   - Check file format (must be .ufdr)
   - Verify file size limits
   - Ensure proper file structure

### Logs
- Backend logs: Check console output when running `python backend/main.py`
- Database logs: `docker-compose logs <service-name>`
- Frontend logs: Check browser console

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For support and questions:
- Create an issue in the repository
- Check the documentation
- Review the troubleshooting section

## 🙏 Acknowledgments

- Azure OpenAI for embedding generation
- Google Gemini for natural language processing
- Qdrant for vector database capabilities
- Neo4j for graph database functionality
- FastAPI for the backend framework
- React and Ant Design for the frontend

---

**UFDR AI Analyzer** - Advanced forensic analysis powered by AI