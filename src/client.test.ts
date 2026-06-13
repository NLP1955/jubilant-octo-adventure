import { HiggsfieldConnector } from './client.js';
import {
  AuthenticationError,
  BadInputError,
  NotEnoughCreditsError,
  TimeoutError,
} from './errors.js';

const FAKE_CREDS = 'key123:secret456';

const makeCompletedJobSetResponse = (id = 'job-001') => ({
  id,
  jobs: [
    {
      id: `${id}-0`,
      status: 'completed',
      results: {
        raw: { url: 'https://cdn.higgsfield.ai/out/raw.mp4' },
        min: { url: 'https://cdn.higgsfield.ai/out/min.mp4' },
      },
    },
  ],
});

const makeQueuedJobSetResponse = (id = 'job-002') => ({
  id,
  jobs: [{ id: `${id}-0`, status: 'queued' }],
});

function mockFetch(responses: Array<{ status: number; body: unknown }>) {
  let call = 0;
  global.fetch = jest.fn(async () => {
    const { status, body } = responses[Math.min(call++, responses.length - 1)];
    return {
      ok: status >= 200 && status < 300,
      status,
      text: async () => JSON.stringify(body),
      json: async () => body,
    } as unknown as Response;
  });
}

afterEach(() => {
  jest.restoreAllMocks();
  delete process.env['HF_CREDENTIALS'];
  delete process.env['HF_API_KEY'];
  delete process.env['HF_API_SECRET'];
});

describe('HiggsfieldConnector – authentication', () => {
  it('throws AuthenticationError when no credentials are provided', () => {
    expect(() => new HiggsfieldConnector()).toThrow(AuthenticationError);
  });

  it('accepts combined credentials string', () => {
    expect(() => new HiggsfieldConnector({ credentials: FAKE_CREDS })).not.toThrow();
  });

  it('accepts separate apiKey + apiSecret', () => {
    expect(
      () => new HiggsfieldConnector({ apiKey: 'key123', apiSecret: 'secret456' }),
    ).not.toThrow();
  });

  it('picks up HF_CREDENTIALS from env', () => {
    process.env['HF_CREDENTIALS'] = FAKE_CREDS;
    expect(() => new HiggsfieldConnector()).not.toThrow();
  });

  it('picks up HF_API_KEY + HF_API_SECRET from env', () => {
    process.env['HF_API_KEY'] = 'k';
    process.env['HF_API_SECRET'] = 's';
    expect(() => new HiggsfieldConnector()).not.toThrow();
  });
});

describe('HiggsfieldConnector – textToImage', () => {
  it('returns a completed JobSet immediately when API responds completed', async () => {
    mockFetch([{ status: 200, body: makeCompletedJobSetResponse() }]);
    const client = new HiggsfieldConnector({ credentials: FAKE_CREDS });
    const result = await client.textToImage({ prompt: 'a sunset over the ocean' });

    expect(result.isCompleted).toBe(true);
    expect(result.jobs[0].status).toBe('completed');
    expect(result.jobs[0].results?.raw.url).toContain('cdn.higgsfield.ai');
  });

  it('polls until job completes', async () => {
    const id = 'job-poll-001';
    mockFetch([
      { status: 200, body: makeQueuedJobSetResponse(id) },
      { status: 200, body: makeQueuedJobSetResponse(id) },
      { status: 200, body: makeCompletedJobSetResponse(id) },
    ]);

    const client = new HiggsfieldConnector({
      credentials: FAKE_CREDS,
      pollInterval: 1,
    });
    const result = await client.textToImage({ prompt: 'a mountain at dawn' });

    expect(result.isCompleted).toBe(true);
    expect(global.fetch).toHaveBeenCalledTimes(3);
  });

  it('throws TimeoutError when job does not complete in time', async () => {
    const id = 'job-timeout';
    mockFetch([{ status: 200, body: makeQueuedJobSetResponse(id) }]);

    const client = new HiggsfieldConnector({
      credentials: FAKE_CREDS,
      pollInterval: 10,
      timeout: 5,
    });

    await expect(
      client.textToImage({ prompt: 'a forest' }),
    ).rejects.toThrow(TimeoutError);
  });
});

describe('HiggsfieldConnector – imageToVideo', () => {
  it('submits and returns completed job', async () => {
    mockFetch([{ status: 200, body: makeCompletedJobSetResponse('vid-001') }]);

    const client = new HiggsfieldConnector({ credentials: FAKE_CREDS });
    const result = await client.imageToVideo({
      model: 'higgsfield-v1',
      prompt: 'pan right slowly',
      input_images: [{ type: 'image_url', image_url: 'https://example.com/img.jpg' }],
    });

    expect(result.id).toBe('vid-001');
    expect(result.isCompleted).toBe(true);
  });
});

describe('HiggsfieldConnector – error handling', () => {
  it('throws AuthenticationError on 401', async () => {
    mockFetch([{ status: 401, body: { message: 'Unauthorized' } }]);
    const client = new HiggsfieldConnector({ credentials: FAKE_CREDS });
    await expect(client.textToImage({ prompt: 'test' })).rejects.toThrow(AuthenticationError);
  });

  it('throws BadInputError on 400', async () => {
    mockFetch([{ status: 400, body: { message: 'Bad prompt' } }]);
    const client = new HiggsfieldConnector({ credentials: FAKE_CREDS });
    await expect(client.textToImage({ prompt: '' })).rejects.toThrow(BadInputError);
  });

  it('throws NotEnoughCreditsError on 402', async () => {
    mockFetch([{ status: 402, body: { message: 'Insufficient credits' } }]);
    const client = new HiggsfieldConnector({ credentials: FAKE_CREDS });
    await expect(client.textToImage({ prompt: 'test' })).rejects.toThrow(NotEnoughCreditsError);
  });
});

describe('HiggsfieldConnector – checkJobSet', () => {
  it('returns current job status without polling', async () => {
    mockFetch([{ status: 200, body: makeQueuedJobSetResponse('jcheck-001') }]);
    const client = new HiggsfieldConnector({ credentials: FAKE_CREDS });
    const result = await client.checkJobSet('jcheck-001');

    expect(result.isQueued).toBe(true);
    expect(result.isCompleted).toBe(false);
    expect(global.fetch).toHaveBeenCalledTimes(1);
  });
});

describe('HiggsfieldConnector – utility methods', () => {
  it('getMotions returns motion list', async () => {
    const motions = [{ id: 'm1', name: 'Pan Left' }];
    mockFetch([{ status: 200, body: motions }]);
    const client = new HiggsfieldConnector({ credentials: FAKE_CREDS });
    const result = await client.getMotions();
    expect(result).toEqual(motions);
  });

  it('getSoulStyles returns style list', async () => {
    const styles = [{ id: 's1', name: 'Anime' }];
    mockFetch([{ status: 200, body: styles }]);
    const client = new HiggsfieldConnector({ credentials: FAKE_CREDS });
    const result = await client.getSoulStyles();
    expect(result).toEqual(styles);
  });
});
