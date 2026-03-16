import axios from 'axios';
import { toast } from 'sonner';

export const apiClient = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
});

// Attach JWT token to every request
apiClient.interceptors.request.use(config => {
  const token = localStorage.getItem('flowforge_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Surface API errors as toasts
apiClient.interceptors.response.use(
  response => response,
  error => {
    const status = error.response?.status;
    const detail = error.response?.data?.detail;

    if (status === 401) {
      localStorage.removeItem('flowforge_token');
      toast.error('Session expired — please reload the page.');
    } else if (status === 403) {
      toast.error('Permission denied.');
    } else if (status === 404) {
      toast.error(typeof detail === 'string' ? detail : 'Resource not found.');
    } else if (status === 409) {
      toast.error(typeof detail === 'string' ? detail : 'Conflict — resource already exists.');
    } else if (status === 422) {
      const msg = Array.isArray(detail)
        ? detail.map((d: { msg: string }) => d.msg).join('; ')
        : typeof detail === 'string'
          ? detail
          : 'Validation error.';
      toast.error(msg);
    } else if (status >= 500) {
      toast.error('Server error — check the logs.');
    } else {
      toast.error(typeof detail === 'string' ? detail : `Request failed (${status}).`);
    }

    return Promise.reject(error);
  }
);
