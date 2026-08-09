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
