import api from "./api";

export type Role = "ADMIN" | "STAFF" | "CITIZEN";

export interface User {
  id: number;
  name: string;
  email: string;
  phone?: string | null;
  role: Role;
  village?: string | null;
  district?: string | null;
  is_active: boolean;
  created_at: string;
}

import type { DetectionResult } from "./logic";
export type { DetectionResult };

export interface DetectionItem {
  class_name: string;
  confidence: number;
  box: { x1: number; y1: number; x2: number; y2: number };
}

export interface NotificationItem {
  id: number;
  title: string;
  body?: string | null;
  kind?: string | null;
  report_id?: number | null;
  is_read: boolean;
  created_at: string;
}

export interface StatusHistory {
  current: string;
  allowed_next: string[];
  history: Array<{ old: string | null; new: string; by: number | null; remarks: string | null; at: string }>;
}

export interface WasteReport {
  id: number;
  user_id: number;
  image_path: string;
  waste_type: string | null;
  is_waste?: boolean | null;
  confidence: number | null;
  latitude: number;
  longitude: number;
  village?: string | null;
  district?: string | null;
  description?: string | null;
  status: string;
  priority: string;
  gps_accuracy?: number | null;
  address?: string | null;
  town?: string | null;
  state?: string | null;
  country?: string | null;
  severity?: string | null;
  priority_score?: number | null;
  object_count?: number;
  detection_summary?: string | null;
  model_version?: string | null;
  confidence_level?: string | null;
  is_possible_duplicate?: boolean;
  hotspot_id?: number | null;
  created_at: string;
  updated_at: string;
  detections: Array<{ id: number; class_name: string; confidence: number; x1: number; y1: number; x2: number; y2: number }>;
}

export const authApi = {
  register: (data: { name: string; email: string; password: string; phone?: string; village?: string; district?: string }) =>
    api.post<User>("/api/auth/register", data), // server always creates a CITIZEN
  login: (email: string, password: string) =>
    api.post<{ access_token: string; token_type: string }>("/api/auth/login", { email, password }),
  me: () => api.get<User>("/api/auth/me"),
};

export const detectionApi = {
  predict: (form: FormData) =>
    api.post<DetectionResult>("/api/detection/predict", form, { headers: { "Content-Type": "multipart/form-data" } }),
};

export const reportsApi = {
  create: (form: FormData) =>
    api.post<WasteReport>("/api/reports", form, { headers: { "Content-Type": "multipart/form-data" } }),
  list: () => api.get<WasteReport[]>("/api/reports"),
  get: (id: number) => api.get<WasteReport>(`/api/reports/${id}`),
  history: (id: number) => api.get<StatusHistory>(`/api/reports/${id}/history`),
};

export const notificationsApi = {
  list: () => api.get<NotificationItem[]>("/api/notifications"),
  read: (id: number) => api.post<NotificationItem>(`/api/notifications/${id}/read`),
  readAll: () => api.post("/api/notifications/read-all"),
};

export const wasteTypesApi = {
  list: () => api.get<Array<{ id: number; name: string; label: string; is_active: boolean }>>("/api/waste-types"),
};

export const profileApi = {
  update: (data: Partial<{ name: string; phone: string; village: string; district: string }>) =>
    api.put<User>("/api/users/me", data),
};
