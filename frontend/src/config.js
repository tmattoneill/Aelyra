import axios from 'axios';

// API configuration
export const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || '';

// Create axios instance with base URL
export const api = axios.create({
  baseURL: API_BASE_URL
});