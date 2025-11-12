// src/App.js
import React, { useState, useEffect } from 'react';
import JobResultModal from './JobResultModal';
import { apiFetch } from './api';

function App() {
  const [jobs, setJobs] = useState([]);
  const [selectedJobs, setSelectedJobs] = useState([]);
  const [selectedJobResult, setSelectedJobResult] = useState(null);

  // Select all checkbox
  const handleSelectAllClick = (event) => {
    if (event.target.checked) {
      const allJobIds = jobs.map((job) => job.job_id);
      setSelectedJobs(allJobIds);
    } else {
      setSelectedJobs([]);
    }
  };

  // Individual checkbox click
  const handleCheckboxClick = (event, jobId) => {
    event.stopPropagation();
    if (event.target.checked) {
      setSelectedJobs((prevSelected) => [...prevSelected, jobId]);
    } else {
      setSelectedJobs((prevSelected) => prevSelected.filter((id) => id !== jobId));
    }
  };

  // Row click → fetch job result if succeeded
  const handleRowClick = (job) => {
    if (job.status === 'succeeded') {
      apiFetch(`/jobs/${job.job_id}/result`)
        .then((response) => {
          if (!response.ok) throw new Error(`HTTP ${response.status}`);
          return response.json();
        })
        .then((data) => setSelectedJobResult(data))
        .catch((error) => console.error('Error fetching job result:', error));
    }
  };

  const handleCloseModal = () => {
    setSelectedJobResult(null);
  };

  // Delete selected jobs
  const handleDeleteClick = () => {
    if (selectedJobs.length === 0) return;

    apiFetch(`/jobs`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ job_ids: selectedJobs }),
    })
      .then((response) => {
        if (response.ok) {
          setJobs((prevJobs) => prevJobs.filter((job) => !selectedJobs.includes(job.job_id)));
          setSelectedJobs([]);
        } else {
          console.error('Failed to delete jobs');
        }
      })
      .catch((error) => console.error('Error deleting jobs:', error));
  };

  // Periodically refresh job list
  useEffect(() => {
    const fetchData = () => {
      apiFetch('/jobs')
        .then((response) => response.json())
        .then((data) => setJobs(data.jobs || []))
        .catch((error) => console.error('Error fetching jobs:', error));
    };

    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="container mx-auto p-4">
      <h1 className="text-2xl font-bold mb-4">LangId Job Dashboard</h1>

      <div className="mb-4">
        <button
          className="bg-red-500 hover:bg-red-700 text-white font-bold py-2 px-4 rounded disabled:opacity-50"
          disabled={selectedJobs.length === 0}
          onClick={handleDeleteClick}
        >
          Delete Selected
        </button>
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-full bg-white">
          <thead>
            <tr>
              <th className="py-2 px-4 border-b">
                <input
                  type="checkbox"
                  onChange={handleSelectAllClick}
                  checked={selectedJobs.length === jobs.length && jobs.length > 0}
                />
              </th>
              <th className="py-2 px-4 border-b">Job ID</th>
              <th className="py-2 px-4 border-b">Status</th>
              <th className="py-2 px-4 border-b">Progress</th>
              <th className="py-2 px-4 border-b">Created At</th>
              <th className="py-2 px-4 border-b">Updated At</th>
              <th className="py-2 px-4 border-b">Error</th>
            </tr>
          </thead>
          <tbody>
            {jobs.map((job) => (
              <tr
                key={job.job_id}
                onClick={() => handleRowClick(job)}
                className={
                  job.status === 'succeeded'
                    ? 'cursor-pointer hover:bg-gray-100'
                    : ''
                }
              >
                <td className="py-2 px-4 border-b">
                  <input
                    type="checkbox"
                    checked={selectedJobs.includes(job.job_id)}
                    onClick={(event) => event.stopPropagation()}
                    onChange={(event) => handleCheckboxClick(event, job.job_id)}
                  />
                </td>
                <td className="py-2 px-4 border-b">{job.job_id}</td>
                <td className="py-2 px-4 border-b">{job.status}</td>
                <td className="py-2 px-4 border-b">{job.progress}</td>
                <td className="py-2 px-4 border-b">{job.created_at}</td>
                <td className="py-2 px-4 border-b">{job.updated_at}</td>
                <td className="py-2 px-4 border-b">{job.error}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {selectedJobResult && (
        <JobResultModal jobResult={selectedJobResult} onClose={handleCloseModal} />
      )}
    </div>
  );
}

export default App;