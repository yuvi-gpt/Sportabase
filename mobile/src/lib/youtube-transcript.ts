import { YoutubeTranscript } from 'youtube-transcript';

export type YouTubeTranscriptSegment = {
  text: string;
  duration: number;
  offset: number;
  lang?: string;
};

export type YouTubeTranscriptResult = {
  transcript: string;
  segments: YouTubeTranscriptSegment[];
  segmentCount: number;
  characterCount: number;
  language: string;
};

export async function fetchYouTubeTranscript(
  url: string,
): Promise<YouTubeTranscriptResult> {
  const rawSegments =
    await YoutubeTranscript.fetchTranscript(url);

  const segments = rawSegments
    .map((segment) => {
      return {
        text: String(
          segment.text ?? '',
        )
          .replace(/\s+/g, ' ')
          .trim(),
        duration: Number(
          segment.duration ?? 0,
        ),
        offset: Number(
          segment.offset ?? 0,
        ),
        lang: String(
          segment.lang ?? '',
        ).trim(),
      };
    })
    .filter((segment) => {
      return segment.text.length > 0;
    });

  const transcript = segments
    .map((segment) => segment.text)
    .join('\n')
    .trim();

  if (!transcript) {
    throw new Error(
      'No usable transcript was returned for this video.',
    );
  }

  return {
    transcript,
    segments,
    segmentCount: segments.length,
    characterCount: transcript.length,
    language:
      segments.find((segment) => {
        return Boolean(segment.lang);
      })?.lang ?? '',
  };
}

type YouTubeOEmbedResponse = {
  title?: string;
};

export async function fetchYouTubeVideoTitle(
  url: string,
): Promise<string> {
  const controller = new AbortController();

  const timeout = setTimeout(() => {
    controller.abort();
  }, 8000);

  try {
    const endpoint =
      'https://www.youtube.com/oembed' +
      `?url=${encodeURIComponent(url)}` +
      '&format=json';

    const response = await fetch(endpoint, {
      headers: {
        Accept: 'application/json',
      },
      signal: controller.signal,
    });

    if (!response.ok) {
      throw new Error(
        `YouTube title request returned HTTP ${response.status}.`,
      );
    }

    const payload =
      (await response.json()) as YouTubeOEmbedResponse;

    const title = String(
      payload.title ?? '',
    )
      .replace(/\s+/g, ' ')
      .trim();

    if (!title) {
      throw new Error(
        'YouTube returned an empty video title.',
      );
    }

    return title.slice(0, 300);
  } finally {
    clearTimeout(timeout);
  }
}
