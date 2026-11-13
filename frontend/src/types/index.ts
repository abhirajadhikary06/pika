export interface User {
  id: string;
  email: string;
  full_name: string;
  avatar_url?: string | null;
  is_active: boolean;
  is_verified?: boolean;
  last_login_at?: string | null;
  created_at: string;
  updated_at: string;
  version: number;
}

export interface Workspace {
  id: string;
  name: string;
  slug: string;
  description?: string | null;
  owner_id: string;
  is_active: boolean;
  settings: Record<string, unknown>;
  role?: string;
  created_at: string;
  updated_at: string;
  version: number;
}

export interface Membership {
  id: string;
  workspace_id: string;
  user_id: string;
  role: "owner" | "admin" | "agent" | "viewer";
  is_active: boolean;
  joined_at: string;
  user?: User;
}

export type TicketStatus = "open" | "in_progress" | "pending" | "resolved" | "closed";
export type TicketPriority = "low" | "medium" | "high" | "urgent";
export type TicketType = "question" | "incident" | "problem" | "task";

export interface Ticket {
  id: string;
  workspace_id: string;
  number: number;
  title: string;
  description?: string | null;
  status: TicketStatus;
  priority: TicketPriority;
  type: TicketType;
  tags: string[];
  created_by_id?: string | null;
  assignee_id?: string | null;
  due_at?: string | null;
  resolved_at?: string | null;
  closed_at?: string | null;
  first_response_at?: string | null;
  client_id?: string | null;
  version: number;
  created_at: string;
  updated_at: string;
  created_by?: User | null;
  assignee?: User | null;
  comments?: Comment[];
  internal_notes?: Comment[];
  activities?: Activity[];
  attachments?: Attachment[];
}

export interface Comment {
  id: string;
  ticket_id: string;
  author_id?: string | null;
  body: string;
  is_internal: boolean;
  client_id?: string | null;
  version: number;
  created_at: string;
  updated_at: string;
  author?: User | null;
  attachments?: Attachment[];
}

export interface Attachment {
  id: string;
  ticket_id: string;
  comment_id?: string | null;
  original_filename: string;
  content_type: string;
  size_bytes: number;
  is_processed: boolean;
  created_at: string;
}

export interface Activity {
  id: string;
  workspace_id: string;
  ticket_id: string;
  actor_id?: string | null;
  action: string;
  details: Record<string, unknown>;
  created_at: string;
  actor?: User | null;
}

export interface Notification {
  id: string;
  user_id: string;
  workspace_id?: string | null;
  ticket_id?: string | null;
  type: string;
  title: string;
  body?: string | null;
  data: Record<string, unknown>;
  is_read: boolean;
  read_at?: string | null;
  created_at: string;
}

export interface WorkspaceStats {
  total: number;
  open: number;
  my_open: number;
  unassigned: number;
  by_status: Record<string, number>;
  by_priority: Record<string, number>;
}

export interface PaginatedMeta {
  page: number;
  per_page: number;
  total: number;
  unread_count?: number;
}

export interface ApiResponse<T> {
  data?: T;
  message?: string;
  meta?: PaginatedMeta;
  error?: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
}
