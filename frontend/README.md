# UFDR Analyzer Frontend

A React-based frontend for the UFDR (Universal Forensic Data Reader) Analysis System. This application provides a clean, intuitive interface for forensic investigators to upload UFDR files, analyze data using AI, and generate comprehensive reports.

## Features

- **File Upload**: Upload UFDR files with case information
- **AI Analyzer**: Chat interface for querying forensic data
- **Report Generator**: Generate and download PDF forensic reports
- **Responsive Design**: Works on desktop and mobile devices
- **Modern UI**: Clean white and orange theme

## Getting Started

### Prerequisites

- Node.js (v16 or higher)
- npm or yarn
- Backend API running on http://localhost:8000

### Installation

1. Install dependencies:
```bash
npm install
```

2. Start the development server:
```bash
npm start
```

3. Open [http://localhost:3000](http://localhost:3000) to view it in the browser.

### Available Scripts

- `npm start` - Runs the app in development mode
- `npm build` - Builds the app for production
- `npm test` - Launches the test runner
- `npm run eject` - Ejects from Create React App (one-way operation)

## Usage

### 1. Upload UFDR File
- Navigate to the Upload page
- Enter case number and investigator name
- Drag and drop or select a UFDR file
- Click "Upload & Process" to analyze the file

### 2. AI Analyzer
- After uploading a file, navigate to AI Analyzer
- Ask questions about the forensic data
- Get instant AI-powered responses
- Examples:
  - "Find WhatsApp messages about meetings"
  - "Who sent verification codes?"
  - "Show me suspicious communications"

### 3. Generate Reports
- Navigate to Report Generator
- Click "Generate Report" for comprehensive analysis
- Click "Download PDF" to get a professional report
- Reports include criminal risk assessment and recommendations

## API Integration

The frontend communicates with the backend API at `http://localhost:8000/api/v1/`:

- `POST /upload-ufdr` - Upload and process UFDR files
- `GET /quick-query` - Quick AI-powered queries
- `POST /generate-comprehensive-report` - Generate detailed reports
- `POST /generate-pdf-report` - Generate PDF reports

## Color Theme

The application uses a white and orange color scheme:
- Primary Orange: `#ff6b35`
- Secondary Orange: `#ff8c5a`
- Background White: `#ffffff`
- Light Gray: `#fafafa`

## Project Structure

```
src/
├── components/          # Reusable components
│   ├── Header.js       # Top navigation header
│   └── Sidebar.js      # Side navigation menu
├── pages/              # Main application pages
│   ├── UploadPage.js   # File upload interface
│   ├── AIAnalyzer.js   # Chat interface for queries
│   └── ReportGenerator.js # Report generation
├── App.js              # Main application component
├── App.css             # Global styles
└── index.js            # Application entry point
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is part of the UFDR Analysis System for forensic investigation purposes.