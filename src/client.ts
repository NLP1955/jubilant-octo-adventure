import {
  HiggsfieldConfig,
  TextToImageInput,
  ImageToVideoInput,
  SpeechToVideoInput,
  SoulStyleInput,
  JobSet,
  SoulId,
  SoulIdListResponse,
  Motion,
  SoulStyle,
  PollOptions,
} from './types.js';
import {
  AuthenticationError,
  BadInputError,
  HiggsfieldError,
  NotEnoughCreditsError,
  TimeoutError,
  ValidationError,
} from './errors.js';

const DEFAULT_BASE_URL = 'https://platform.higgsfield.ai';
const DEFAULT_TIMEOUT = 120_000;
const DEFAULT_POLL_INTERVAL = 2_000;

export class HiggsfieldConnector {
  private readonly baseURL: string;
  private readonly timeout: number;
  private readonly pollInterval: number;
  private readonly authHeader: string;

  constructor(config: HiggsfieldConfig = {}) {
    this.baseURL = (config.baseURL ?? DEFAULT_BASE_URL).replace(/\/$/, '');
    this.timeout = config.timeout ?? DEFAULT_TIMEOUT;
    this.pollInterval = config.pollInterval ?? DEFAULT_POLL_INTERVAL;
    this.authHeader = this.resolveAuth(config);
  }

  private resolveAuth(config: HiggsfieldConfig): string {
    const combined =
      config.credentials ??
      process.env['HF_CREDENTIALS'];

    if (combined) {
      return `Bearer ${Buffer.from(combined).toString('base64')}`;
    }

    const key = config.apiKey ?? process.env['HF_API_KEY'];
    const secret = config.apiSecret ?? process.env['HF_API_SECRET'];

    if (key && secret) {
      return `Bearer ${Buffer.from(`${key}:${secret}`).toString('base64')}`;
    }

    throw new AuthenticationError(
      'Higgsfield credentials are required. Provide credentials, apiKey+apiSecret, ' +
        'or set HF_CREDENTIALS / HF_API_KEY + HF_API_SECRET environment variables.',
    );
  }

  private async request<T>(
    method: 'GET' | 'POST',
    path: string,
    body?: unknown,
  ): Promise<T> {
    const url = `${this.baseURL}${path}`;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeout);

    let response: Response;
    try {
      response = await fetch(url, {
        method,
        headers: {
          Authorization: this.authHeader,
          'Content-Type': 'application/json',
          Accept: 'application/json',
        },
        body: body !== undefined ? JSON.stringify(body) : undefined,
        signal: controller.signal,
      });
    } catch (err: unknown) {
      if (err instanceof Error && err.name === 'AbortError') {
        throw new HiggsfieldError(`Request to ${path} timed out after ${this.timeout}ms`);
      }
      throw err;
    } finally {
      clearTimeout(timer);
    }

    const text = await response.text();
    let json: unknown;
    try {
      json = JSON.parse(text);
    } catch {
      json = text;
    }

    if (!response.ok) {
      this.throwForStatus(response.status, json);
    }

    return json as T;
  }

  private throwForStatus(status: number, body: unknown): never {
    const message =
      typeof body === 'object' && body !== null && 'message' in body
        ? String((body as Record<string, unknown>)['message'])
        : JSON.stringify(body);

    switch (status) {
      case 401:
      case 403:
        throw new AuthenticationError(message);
      case 400:
        throw new BadInputError(message, body);
      case 402:
        throw new NotEnoughCreditsError(message);
      case 422:
        throw new ValidationError(message, body);
      default:
        throw new HiggsfieldError(message, status, body);
    }
  }

  private mapJobSet(raw: Record<string, unknown>): JobSet {
    const jobs = (raw['jobs'] as Array<Record<string, unknown>> | undefined) ?? [];
    const statuses = jobs.map((j) => j['status'] as string);
    return {
      id: raw['id'] as string,
      isCompleted: statuses.length > 0 && statuses.every((s) => s === 'completed'),
      isQueued: statuses.some((s) => s === 'queued'),
      isInProgress: statuses.some((s) => s === 'in_progress'),
      isFailed: statuses.some((s) => s === 'failed'),
      isNsfw: statuses.some((s) => s === 'nsfw'),
      jobs: jobs.map((j) => ({
        id: j['id'] as string,
        status: j['status'] as JobSet['jobs'][0]['status'],
        results: j['results'] as JobSet['jobs'][0]['results'],
        error: j['error'] as string | undefined,
      })),
    };
  }

  private async poll(
    jobSetId: string,
    opts: PollOptions = {},
  ): Promise<JobSet> {
    const interval = opts.pollInterval ?? this.pollInterval;
    const maxWait = opts.maxWait ?? this.timeout;
    const start = Date.now();

    while (true) {
      const raw = await this.request<Record<string, unknown>>(
        'GET',
        `/v1/jobs/${jobSetId}`,
      );
      const jobSet = this.mapJobSet(raw);

      if (jobSet.isCompleted || jobSet.isFailed || jobSet.isNsfw) {
        return jobSet;
      }

      const elapsed = Date.now() - start;
      if (elapsed + interval > maxWait) {
        throw new TimeoutError(jobSetId, maxWait);
      }

      await new Promise((resolve) => setTimeout(resolve, interval));
    }
  }

  private async submitAndPoll(
    endpoint: string,
    input: unknown,
    opts: PollOptions = {},
  ): Promise<JobSet> {
    const raw = await this.request<Record<string, unknown>>('POST', endpoint, { input });
    const jobSet = this.mapJobSet(raw);

    if (jobSet.isCompleted || jobSet.isFailed || jobSet.isNsfw) {
      return jobSet;
    }

    return this.poll(jobSet.id, opts);
  }

  // ── Text-to-Image ──────────────────────────────────────────────────────────

  async textToImage(
    input: TextToImageInput,
    opts?: PollOptions,
  ): Promise<JobSet> {
    return this.submitAndPoll('/v1/text2image', input, opts);
  }

  async textToImageSoul(
    input: TextToImageInput,
    opts?: PollOptions,
  ): Promise<JobSet> {
    return this.submitAndPoll('/v1/text2image/soul', input, opts);
  }

  // ── Image-to-Video ─────────────────────────────────────────────────────────

  async imageToVideo(
    input: ImageToVideoInput,
    opts?: PollOptions,
  ): Promise<JobSet> {
    return this.submitAndPoll('/v1/image2video/dop', input, opts);
  }

  // ── Speech / Lip Sync ──────────────────────────────────────────────────────

  async speechToVideo(
    input: SpeechToVideoInput,
    opts?: PollOptions,
  ): Promise<JobSet> {
    return this.submitAndPoll('/v1/speak/higgsfield', input, opts);
  }

  // ── Soul style ─────────────────────────────────────────────────────────────

  async generateWithSoulStyle(
    input: SoulStyleInput,
    opts?: PollOptions,
  ): Promise<JobSet> {
    return this.submitAndPoll('/v1/generate/soul-style', input, opts);
  }

  // ── Soul IDs ───────────────────────────────────────────────────────────────

  async createSoulId(
    data: { image_url: string; name?: string },
    opts?: PollOptions,
  ): Promise<SoulId> {
    return this.request<SoulId>('POST', '/v1/soul-ids', data);
  }

  async listSoulIds(page = 1, pageSize = 20): Promise<SoulIdListResponse> {
    return this.request<SoulIdListResponse>(
      'GET',
      `/v1/soul-ids?page=${page}&page_size=${pageSize}`,
    );
  }

  // ── Utility ────────────────────────────────────────────────────────────────

  async getMotions(): Promise<Motion[]> {
    return this.request<Motion[]>('GET', '/v1/motions');
  }

  async getSoulStyles(): Promise<SoulStyle[]> {
    return this.request<SoulStyle[]>('GET', '/v1/soul-styles');
  }

  /** Upload a local image buffer to the Higgsfield CDN. */
  async uploadImage(
    buffer: Buffer,
    format: 'jpeg' | 'png' | 'webp' = 'jpeg',
  ): Promise<{ url: string }> {
    const url = `${this.baseURL}/v1/upload`;
    const formData = new FormData();
    const blob = new Blob([buffer], { type: `image/${format}` });
    formData.append('file', blob, `upload.${format}`);

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeout);

    let response: Response;
    try {
      response = await fetch(url, {
        method: 'POST',
        headers: { Authorization: this.authHeader },
        body: formData,
        signal: controller.signal,
      });
    } finally {
      clearTimeout(timer);
    }

    const json = await response.json() as Record<string, unknown>;
    if (!response.ok) {
      this.throwForStatus(response.status, json);
    }
    return json as { url: string };
  }

  /** Poll an existing job set by ID. */
  async getJobSet(id: string, opts?: PollOptions): Promise<JobSet> {
    return this.poll(id, opts);
  }

  /** Fetch the current status of a job set without polling. */
  async checkJobSet(id: string): Promise<JobSet> {
    const raw = await this.request<Record<string, unknown>>('GET', `/v1/jobs/${id}`);
    return this.mapJobSet(raw);
  }
}
