import axios from 'axios';

export const apiClient = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
});

// Auth interceptor: attach JWT from localStorage if present
apiClient.interceptors.request.use(config => {
  const token = localStorage.getItem('flowforge_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});
