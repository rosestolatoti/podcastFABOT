import React from 'react';
import useJobStore from '../store/jobStore';
import MiniJobCard from './MiniJobCard';
import './ActiveJobsBar.css';

function ActiveJobsBar() {
  const { activeJobs } = useJobStore();
  
  if (activeJobs.length === 0) return null;
  
  return (
    <div className="active-jobs-bar">
      <div className="active-jobs-label">
        <span className="active-jobs-icon">📦</span>
        <span>Jobs Ativos ({activeJobs.length})</span>
      </div>
      <div className="active-jobs-list">
        {activeJobs.map(job => (
          <MiniJobCard key={job.id} job={job} />
        ))}
      </div>
    </div>
  );
}

export default ActiveJobsBar;
