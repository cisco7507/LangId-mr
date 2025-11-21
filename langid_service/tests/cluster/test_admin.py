
import pytest
from datetime import datetime, timedelta
from langid_service.app.database import SessionLocal
from langid_service.app.models.models import Job, JobStatus

# 7.3 admin jobs tests

def test_admin_jobs_local_only(client, mock_cluster_config, mock_db_session):
    # Create local jobs directly in DB to avoid overhead
    session = mock_db_session()
    job1 = Job(id="node-a-1", status=JobStatus.queued, created_at=datetime.now(), input_path="fake")
    job2 = Job(id="node-a-2", status=JobStatus.running, created_at=datetime.now(), input_path="fake")
    # Remote job shouldn't be here anyway in local store, but let's ensure we only get what's in DB
    session.add(job1)
    session.add(job2)
    session.commit()
    session.close()
    
    resp = client.get("/admin/jobs")
    assert resp.status_code == 200
    data = resp.json()
    assert data["server"] == "node-a"
    ids = [j["job_id"] for j in data["jobs"]]
    assert "node-a-1" in ids
    assert "node-a-2" in ids

def test_admin_jobs_filter_status(client, mock_cluster_config, mock_db_session):
    session = mock_db_session()
    # Clean up previous tests if sharing DB (sqlite file)
    session.query(Job).delete()
    
    job1 = Job(id="node-a-s1", status=JobStatus.running, created_at=datetime.now(), input_path="fake")
    job2 = Job(id="node-a-s2", status=JobStatus.succeeded, created_at=datetime.now(), input_path="fake")
    session.add_all([job1, job2])
    session.commit()
    session.close()
    
    resp = client.get("/admin/jobs?status=running")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["jobs"]) == 1
    assert data["jobs"][0]["job_id"] == "node-a-s1"

def test_admin_jobs_filter_since(client, mock_cluster_config, mock_db_session):
    session = mock_db_session()
    session.query(Job).delete()
    
    now = datetime.now()
    old = now - timedelta(hours=2)
    
    job1 = Job(id="node-a-old", status=JobStatus.succeeded, created_at=old, input_path="fake")
    job2 = Job(id="node-a-new", status=JobStatus.succeeded, created_at=now, input_path="fake")
    session.add_all([job1, job2])
    session.commit()
    session.close()
    
    since_ts = (now - timedelta(hours=1)).isoformat()
    resp = client.get(f"/admin/jobs?since={since_ts}")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["jobs"]) == 1
    assert data["jobs"][0]["job_id"] == "node-a-new"
