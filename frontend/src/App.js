import React, { useState } from 'react';
import './App.css';

function App() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploadResponse, setUploadResponse] = useState(null);
  const [extractedData, setExtractedData] = useState(null);
  const [fileIdForQuery, setFileIdForQuery] = useState('');

  const handleFileChange = (event) => {
    setSelectedFile(event.target.files[0]);
    setUploadResponse(null); // Reset previous response
    setExtractedData(null); // Reset previous data
  };

  const handleUpload = async () => {
    if (!selectedFile) {
      alert("Please select a file first!");
      return;
    }

    const formData = new FormData();
    formData.append('file', selectedFile);

    try {
      const response = await fetch('/api/upload_document/', { // Assuming backend is proxied or on same domain
        method: 'POST',
        body: formData,
      });
      const result = await response.json();
      setUploadResponse(result);
      if (result.file_id) {
        setFileIdForQuery(result.file_id);
      }
    } catch (error) {
      console.error("Error uploading file:", error);
      setUploadResponse({ message: `Error uploading file: ${error.message}` });
    }
  };

  const handleFetchExtraction = async () => {
    if (!fileIdForQuery) {
      alert("No file ID to query. Please upload a document first.");
      return;
    }
    try {
      const response = await fetch(`/api/get_extracted_text/${fileIdForQuery}`);
      const result = await response.json();
      setExtractedData(result);
    } catch (error) {
      console.error("Error fetching extracted data:", error);
      setExtractedData({ message: `Error fetching data: ${error.message}` });
    }
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>Med-Assist Document Processor</h1>
        
        <div>
          <h2>1. Upload Document</h2>
          <input type="file" onChange={handleFileChange} />
          <button onClick={handleUpload} disabled={!selectedFile}>Upload</button>
          {uploadResponse && (
            <div>
              <p><strong>Upload Status:</strong> {uploadResponse.message}</p>
              {uploadResponse.file_id && <p>File ID: {uploadResponse.file_id}</p>}
            </div>
          )}
        </div>

        {uploadResponse && uploadResponse.file_id && (
          <div>
            <h2>2. Fetch Extracted Information</h2>
            <p>Using File ID: {fileIdForQuery}</p>
            <button onClick={handleFetchExtraction}>Fetch Extraction</button>
            {extractedData && (
              <div>
                <h3>Extraction Result:</h3>
                <pre>{JSON.stringify(extractedData, null, 2)}</pre>
              </div>
            )}
          </div>
        )}
      </header>
    </div>
  );
}

export default App;