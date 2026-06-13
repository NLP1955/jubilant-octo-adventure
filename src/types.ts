export interface HiggsfieldConfig {
  /** Combined credentials as "KEY_ID:KEY_SECRET" or set via HF_CREDENTIALS env var */
  credentials?: string;
  /** API key ID (alternative to combined credentials) */
  apiKey?: string;
  /** API key secret (alternative to combined credentials) */
  apiSecret?: string;
  /** API base URL (default: https://platform.higgsfield.ai) */
  baseURL?: string;
  /** Request timeout in milliseconds (default: 120000) */
  timeout?: number;
  /** Job polling interval in milliseconds (default: 2000) */
  pollInterval?: number;
}

export type AspectRatio =
  | '1:1'
  | '16:9'
  | '9:16'
  | '4:3'
  | '3:4'
  | '21:9'
  | '9:21';

export interface TextToImageInput {
  prompt: string;
  aspect_ratio?: AspectRatio;
  /** Safety tolerance 0-6, higher = more permissive (default: 2) */
  safety_tolerance?: number;
  seed?: number;
}

export interface ImageInput {
  type: 'image_url';
  image_url: string;
}

export interface ImageToVideoInput {
  model: string;
  prompt: string;
  input_images: ImageInput[];
  seed?: number;
  /** Motion intensity 0-1 */
  motion?: number;
  aspect_ratio?: AspectRatio;
}

export interface SpeechToVideoInput {
  /** URL of a portrait image to animate */
  image_url: string;
  /** Audio file URL to drive lip sync */
  audio_url?: string;
  /** Text to speak (requires TTS) */
  text?: string;
  /** Voice ID for TTS */
  voice_id?: string;
}

export interface SoulStyleInput {
  prompt: string;
  soul_id: string;
  style?: string;
  aspect_ratio?: AspectRatio;
  seed?: number;
}

export type JobStatus =
  | 'queued'
  | 'in_progress'
  | 'completed'
  | 'failed'
  | 'nsfw';

export interface JobResult {
  url: string;
}

export interface Job {
  id: string;
  status: JobStatus;
  results?: {
    raw: JobResult;
    min: JobResult;
  };
  error?: string;
}

export interface JobSet {
  id: string;
  isCompleted: boolean;
  isQueued: boolean;
  isInProgress: boolean;
  isFailed: boolean;
  isNsfw: boolean;
  jobs: Job[];
}

export interface SoulId {
  id: string;
  name?: string;
  image_url: string;
  created_at?: string;
}

export interface SoulIdListResponse {
  items: SoulId[];
  total: number;
  page: number;
  page_size: number;
}

export interface Motion {
  id: string;
  name: string;
  description?: string;
}

export interface SoulStyle {
  id: string;
  name: string;
  preview_url?: string;
}

export interface PollOptions {
  /** Override connector-level poll interval (ms) */
  pollInterval?: number;
  /** Maximum time to wait for completion (ms), default: connector timeout */
  maxWait?: number;
}
