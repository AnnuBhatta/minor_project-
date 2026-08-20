import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "/api",
  timeout: 10000,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

let refreshRequest;

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    const refresh = localStorage.getItem("refresh_token");

    if (
      error.response?.status === 401
      && !originalRequest?._retry
      && !originalRequest?.url?.includes('/auth/refresh/')
      && refresh
    ) {
      originalRequest._retry = true;
      try {
        refreshRequest ??= api.post("/auth/refresh/", { refresh });
        const { data } = await refreshRequest;
        localStorage.setItem("access_token", data.access);
        originalRequest.headers.Authorization = `Bearer ${data.access}`;
        return api(originalRequest);
      } catch {
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
        localStorage.removeItem("user");
      } finally {
        refreshRequest = undefined;
      }
    }

    return Promise.reject(error);
  },
);

export default api;
