# UFDR Analysis System

An AI-based Universal Forensic Extraction Device Report (UFDR) analysis system that enables investigating officers to query forensic data using natural language and get intelligent insights through a hybrid approach combining vector databases, SQL databases, and graph databases.

## Features

- **Multi-format UFDR Parsing**: Supports XML, JSON, CSV, and XLSX formats
- **Hybrid Database Architecture**: 
  - PostgreSQL for structured data storage
  - Qdrant for semantic vector search
  - Neo4j for relationship analysis
  - Redis for caching
- **Natural Language Queries**: Query forensic data using plain English
- **AI-Powered Analysis**: Uses Azure OpenAI for embeddings and Google Gemini for query processing
- **Connection Analysis**: Discover relationships between contacts and communications
- **Interactive Dashboard**: Real-time analytics and visualizations
- **Comprehensive Reporting**: Generate investigation reports automatically

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   React.js      │    │   FastAPI       │    │   Databases     │
│   Frontend      │◄──►│   Backend       │◄──►│                 │
│                 │    │                 │    │ • PostgreSQL    │
│ • Dashboard     │    │ • UFDR Parser   │    │ • Qdrant        │
│ • Query UI      │    │ • AI Service    │    │ • Neo4j         │
│ • Analytics     │    │ • Data Processor│    │ • Redis         │
│ • Connections   │    │ • API Routes    │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Prerequisites

- Python 3.8+
- Node.js 16+
- Docker and Docker Compose
- Azure OpenAI API access
- Google Gemini API access

## Quick Start

### 1. Clone the Repository

```bash
git clone <repository-url>
cd ufdr-analysis-system
```

### 2. Environment Setup

Copy the `.env` file and update with your API keys and database credentials:

```bash
cp .env .env.local
```

Update the following in `.env.local`:
```env
# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT=your_azure_openai_endpoint
AZURE_OPENAI_API_KEY=your_azure_openai_api_key

# Google Gemini Configuration
GEMINI_API_KEY=your_gemini_api_key

# Database passwords (update as needed)
POSTGRES_PASSWORD=your_secure_password
NEO4J_PASSWORD=your_secure_password
REDIS_PASSWORD=your_secure_password
```

### 3. Start Database Services

```bash
docker-compose up -d
```

This will start:
- PostgreSQL on port 5432
- Qdrant on port 6333
- Neo4j on port 7474 (web) and 7687 (bolt)
- Redis on port 6379

### 4. Install Backend Dependencies

```bash
cd backend
pip install -r ../requirements.txt
```

### 5. Start Backend Server

```bash
python main.py
```

The API will be available at `http://localhost:8000`

### 6. Install Frontend Dependencies

```bash
cd ../frontend
npm install
```

### 7. Start Frontend Development Server

```bash
npm start
```

The web application will be available at `http://localhost:3000`

## Usage

### 1. Upload UFDR Files

1. Navigate to the "Upload UFDR" page
2. Enter case number and investigator name
3. Upload your UFDR file (XML, JSON, CSV, or XLSX)
4. Wait for processing to complete

### 2. Query Data

1. Go to the "Query Data" page
2. Enter natural language queries like:
   - "Show me chat records containing crypto addresses"
   - "List all communications with foreign numbers"
   - "Find deleted messages from the last 30 days"
3. View results in multiple formats (report, vector results, SQL/Cypher queries)

### 3. Analyze Connections

1. Visit the "Connections" page
2. Enter a phone number to analyze
3. Set the search depth (1-5 degrees of separation)
4. Explore the connection network and relationships

### 4. View Analytics

1. Check the "Analytics" page for:
   - Data distribution charts
   - Activity timelines
   - Application usage statistics
   - Top active contacts

## API Documentation

Once the backend is running, visit `http://localhost:8000/docs` for interactive API documentation.

### Key Endpoints

- `POST /api/v1/upload-ufdr` - Upload and process UFDR files
- `POST /api/v1/query` - Execute natural language queries
- `GET /api/v1/connections/{phone_number}` - Find connections for a phone number
- `GET /api/v1/search/semantic` - Perform semantic search
- `GET /api/v1/analytics/summary` - Get analytics summary

## Configuration

### Database Configuration

Update database settings in `.env`:

```env
# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=ufdr_analysis
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password

# Qdrant
QDRANT_HOST=localhost
QDRANT_PORT=6333

# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
```

### AI Service Configuration

```env
# Azure OpenAI
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your_api_key
AZURE_EMBEDDING_MODEL=text-embedding-ada-002
AZURE_CHAT_MODEL=gpt-4

# Google Gemini
GEMINI_API_KEY=your_gemini_api_key
```

## Development

### Backend Development

```bash
cd backend
pip install -r ../requirements.txt
python main.py
```

### Frontend Development

```bash
cd frontend
npm install
npm start
```

### Running Tests

```bash
# Backend tests
cd backend
python -m pytest

# Frontend tests
cd frontend
npm test
```

## Deployment

### Production Deployment

1. Update environment variables for production
2. Build the frontend:
   ```bash
   cd frontend
   npm run build
   ```
3. Deploy using Docker:
   ```bash
   docker-compose -f docker-compose.prod.yml up -d
   ```

### Security Considerations

- Use strong passwords for all databases
- Enable SSL/TLS for all connections
- Implement proper authentication and authorization
- Regularly update dependencies
- Monitor system logs and access

## Troubleshooting

### Common Issues

1. **Database Connection Errors**
   - Ensure Docker containers are running
   - Check database credentials in `.env`
   - Verify network connectivity

2. **API Key Errors**
   - Verify Azure OpenAI and Gemini API keys
   - Check API quotas and limits
   - Ensure proper permissions

3. **File Upload Issues**
   - Check file format (XML, JSON, CSV, XLSX)
   - Verify file size limits
   - Ensure proper file structure

### Logs

- Backend logs: Check console output when running `python main.py`
- Database logs: `docker-compose logs <service-name>`
- Frontend logs: Check browser console

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support and questions:
- Create an issue in the repository
- Check the documentation
- Review the troubleshooting section

## Acknowledgments

- Azure OpenAI for embedding generation
- Google Gemini for natural language processing
- Qdrant for vector database capabilities
- Neo4j for graph database functionality
- FastAPI for the backend framework
- React and Ant Design for the frontend