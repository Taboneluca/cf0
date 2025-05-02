// Common types used across the application

export interface User {
  id: string;
  email: string;
  name?: string;
  created_at: string;
}

export interface ApiResponse<T> {
  data?: T;
  error?: string;
  status: number;
}

export interface WorkbookData {
  id: string;
  name: string;
  created_at: string;
  updated_at: string;
  owner_id: string;
  content?: any;
}

// Add any other common types here 