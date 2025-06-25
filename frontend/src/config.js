import axios from 'axios';

// API configuration
export const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || (process.env.NODE_ENV === 'production' ? '' : 'http://127.0.0.1:5988');

// Create axios instance with base URL
export const api = axios.create({
  baseURL: API_BASE_URL
});