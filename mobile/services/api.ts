import axios from "axios";
import Storage from "expo-sqlite/kv-store";
import { API_BASE_URL } from "../constants/config";

export class ApiNotConfiguredError extends Error {
  constructor() {
    super(
      "EXPO_PUBLIC_API_URL is not set. Add it to mobile/.env -- see mobile/README.md. " +
        "This app never falls back to localhost."
    );
    this.name = "ApiNotConfiguredError";
  }
}

const api = axios.create({
  baseURL: API_BASE_URL || undefined,
  timeout: 30000,
});

api.interceptors.request.use(async (config) => {
  if (!API_BASE_URL) throw new ApiNotConfiguredError();
  const token = await Storage.getItem("ww_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export default api;
