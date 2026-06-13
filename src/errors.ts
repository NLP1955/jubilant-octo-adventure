export class HiggsfieldError extends Error {
  constructor(
    message: string,
    public readonly statusCode?: number,
    public readonly body?: unknown,
  ) {
    super(message);
    this.name = 'HiggsfieldError';
  }
}

export class AuthenticationError extends HiggsfieldError {
  constructor(message = 'Invalid or missing Higgsfield credentials') {
    super(message, 401);
    this.name = 'AuthenticationError';
  }
}

export class BadInputError extends HiggsfieldError {
  constructor(message: string, body?: unknown) {
    super(message, 400, body);
    this.name = 'BadInputError';
  }
}

export class ValidationError extends HiggsfieldError {
  constructor(message: string, body?: unknown) {
    super(message, 422, body);
    this.name = 'ValidationError';
  }
}

export class NotEnoughCreditsError extends HiggsfieldError {
  constructor(message = 'Insufficient Higgsfield credits') {
    super(message, 402);
    this.name = 'NotEnoughCreditsError';
  }
}

export class TimeoutError extends HiggsfieldError {
  constructor(jobId: string, elapsed: number) {
    super(`Job ${jobId} did not complete within ${elapsed}ms`);
    this.name = 'TimeoutError';
  }
}
