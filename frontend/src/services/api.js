import axios from 'axios';

// All calls go through the Vite /api proxy (see vite.config.js) -> FastAPI on :8000
const api = axios.create({ baseURL: '/api', withCredentials: true });

export const loginCitizen = (accountId, password) => api.post('/auth/citizen/login', { account_id: accountId, password }).then(r => r.data);
export const loginAdmin = (accountId, password) => api.post('/auth/admin/login', { account_id: accountId, password }).then(r => r.data);
export const loginWorker = (accountId, password) => api.post('/auth/worker/login', { account_id: accountId, password }).then(r => r.data);
export const registerCitizen = (details) => api.post('/auth/citizen/register', details).then(r => r.data);
export const getSession = () => api.get('/auth/me').then(r => r.data);
export const logoutPortal = () => api.post('/auth/logout').then(r => r.data);

export const getSummary = () => api.get('/dashboard/summary').then(r => r.data);
export const getAreas = () => api.get('/dashboard/areas').then(r => r.data);
export const getInsights = () => api.get('/dashboard/insights').then(r => r.data.insights || []);
export const getClusters = () => api.get('/dashboard/clusters').then(r => r.data.features || []);
export const getPublicComplaints = () => api.get('/complaints/public').then(r => r.data);
export const getComplaints = (params) => api.get('/complaints/', {
  params,
  paramsSerializer: { indexes: null },
}).then(r => r.data);
// formData: image (required), description, latitude, longitude, auto_detect, manual_type
export const createComplaint = (formData) => api.post('/complaints/', formData).then(r => r.data);
export const updateComplaintStatus = (complaintId, status) => api.patch(`/complaints/${complaintId}`, { status }).then(r => r.data);
export const getComplaintWorkUpdates = (complaintId) => api.get(`/complaints/${complaintId}/work-updates`).then(r => r.data);
export const addComplaintWorkUpdate = (complaintId, formData) => api.post(`/complaints/${complaintId}/work-updates`, formData).then(r => r.data);
export const getResolutionConfirmation = (complaintId) => api.get(`/complaints/${complaintId}/resolution-confirmation`).then(r => r.data);
export const uploadCitizenResolutionEvidence = (complaintId, photo) => {
  const formData = new FormData();
  formData.append('photo', photo);
  return api.post(`/complaints/${complaintId}/resolution-confirmation/evidence`, formData).then(r => r.data);
};
export const submitResolutionConfirmation = (complaintId, response) => api.post(`/complaints/${complaintId}/resolution-confirmation`, { response }).then(r => r.data);
export const getImpactPriority = (complaintId) => api.get(`/complaints/${complaintId}/impact-priority`).then(r => r.data);

export const getWorkforceSummary = () => api.get('/workforce/admin/summary').then(r => r.data);
export const getWorkers = () => api.get('/workforce/admin/workers').then(r => r.data);
export const createWorker = (details) => api.post('/workforce/admin/workers', details).then(r => r.data);
export const getWorkerProfile = (workerId) => api.get(`/workforce/admin/workers/${encodeURIComponent(workerId)}`).then(r => r.data);
export const updateWorkerAccountStatus = (workerId, accountStatus) => api.patch(`/workforce/admin/workers/${encodeURIComponent(workerId)}/status`, { account_status: accountStatus }).then(r => r.data);
export const assignComplaintToWorker = (complaintId, details) => api.post(`/workforce/admin/complaints/${complaintId}/assignments`, details).then(r => r.data);
export const verifyWorkerCompletion = (complaintId, note) => api.post(`/workforce/admin/complaints/${complaintId}/verify-completion`, { note }).then(r => r.data);
export const getWorkerDashboard = () => api.get('/workforce/my').then(r => r.data);
export const getComplaintWorkforceProgress = (complaintId) => api.get(`/workforce/complaints/${complaintId}/progress`).then(r => r.data);
export const addWorkerProgressUpdate = (assignmentId, formData) => api.post(`/workforce/assignments/${assignmentId}/updates`, formData).then(r => r.data);

export default api;
