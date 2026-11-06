import api from "./api";

export const authApi = {
  login: (email, password) => api.post("/api/auth/login", { email, password }),
  me: () => api.get("/api/auth/me"),
};

export const reportsApi = {
  list: (params) => api.get("/api/reports", { params: { limit: 500, ...params } }),
  get: (id) => api.get(`/api/reports/${id}`),
  update: (id, data) => api.put(`/api/reports/${id}`, data),
  reclassify: (id, is_waste, remarks) => api.post(`/api/reports/${id}/reclassify`, { is_waste, remarks }),
  assign: (id, staff_id, remarks) => api.post(`/api/reports/${id}/assign`, { staff_id, remarks }),
  setStatus: (id, status, remarks) => api.put(`/api/reports/${id}/status`, { status, remarks }),
  complete: (id, formData) =>
    api.post(`/api/reports/${id}/complete`, formData, {
      headers: { "Content-Type": "multipart/form-data" },
    }),
  before: (id, formData) =>
    api.post(`/api/reports/${id}/before-image`, formData, { headers: { "Content-Type": "multipart/form-data" } }),
  cleanup: (id) => api.get(`/api/reports/${id}/cleanup-verification`),
  decideCleanup: (id, approve, remarks) => api.post(`/api/reports/${id}/cleanup-verification`, { approve, remarks }),
  history: (id) => api.get(`/api/reports/${id}/history`),
  exportFile: (kind, params) => api.get(`/api/reports/export/${kind}`, { params, responseType: "blob" }),
  exportPdf: (params) => api.get("/api/reports/export/pdf", { params, responseType: "blob" }),
};

export const adminApi = {
  listUsers: (role) => api.get("/api/admin/users", { params: role ? { role } : {} }),
  verifyReport: (id, data) => api.post(`/api/admin/reports/${id}/verify`, data),
  addToTraining: (id) => api.post(`/api/admin/reports/${id}/add-to-training`),
  auditLog: (params) => api.get("/api/admin/audit-log", { params: params || {} }),
  createUser: (data) => api.post("/api/admin/users", data),
  updateUser: (id, data) => api.put(`/api/admin/users/${id}`, data),
  settings: () => api.get("/api/admin/settings"),
  saveSettings: (values) => api.put("/api/admin/settings", values),
  saveScoring: (cfg) => api.put("/api/admin/scoring-config", cfg),
  models: () => api.get("/api/admin/models"),
  activateModel: (version) => api.post(`/api/admin/models/${encodeURIComponent(version)}/activate`),
};

export const dashboardApi = {
  stats: () => api.get("/api/dashboard/stats"),
  cards: () => api.get("/api/dashboard/cards"),
  analytics: () => api.get("/api/dashboard/analytics"),
  recent: (since) => api.get("/api/dashboard/recent", { params: { since } }),
  hotspots: (minReports) => api.get("/api/dashboard/hotspots", { params: minReports ? { min_reports: minReports } : {} }),
  cleanlinessScore: (by = "village") => api.get("/api/dashboard/cleanliness-score", { params: { by } }),
};

export const trainingApi = {
  currentModel: () => api.get("/api/training/model"),
  history: () => api.get("/api/training/model/history"),
  dataset: () => api.get("/api/training/dataset"),
  images: () => api.get("/api/training/images"),
};

export const wasteTypesApi = {
  list: (activeOnly = true) => api.get("/api/waste-types", { params: { active_only: activeOnly } }),
  create: (data) => api.post("/api/waste-types", data),
  activate: (id) => api.put(`/api/waste-types/${id}/activate`),
  deactivate: (id) => api.put(`/api/waste-types/${id}/deactivate`),
};

export const profileApi = {
  update: (data) => api.put("/api/users/me", data),
  changePassword: (data) => api.post("/api/users/me/change-password", data),
};

export const staffApi = {
  summary: () => api.get("/api/staff/summary"),
};

export const hotspotsApi = {
  list: () => api.get("/api/hotspots"),
  history: (id) => api.get(`/api/hotspots/${id}/history`),
};

export const duplicatesApi = {
  list: (decision = "PENDING") => api.get("/api/duplicates", { params: decision ? { decision } : {} }),
  decide: (id, decision) => api.post(`/api/duplicates/${id}/decision`, { decision }),
};

export const notificationsApi = {
  list: (unreadOnly = false) => api.get("/api/notifications", { params: { unread_only: unreadOnly } }),
  read: (id) => api.post(`/api/notifications/${id}/read`),
  readAll: () => api.post("/api/notifications/read-all"),
};

export const analyticsApi = {
  summary: (days = 30) => api.get("/api/analytics/summary", { params: { days } }),
};
