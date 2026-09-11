import { analyzeArticle, analyzeVideo, resolveContent, type ArticleAnalyzeResponse, type VideoAnalyzeResponse } from './api';
import { resolveSportabaseApiOrigin } from './deployment-config';
import { fetchYouTubeTranscript, fetchYouTubeVideoTitle, type YouTubeTranscriptResult } from './youtube-transcript';

export type ProductAnalysisResult = { kind: 'article'; data: ArticleAnalyzeResponse } | { kind: 'video'; data: VideoAnalyzeResponse };
export type ProductAnalysisPhase = 'resolving' | 'analyzing';
type Dependencies = {
  validateApi: () => string;
  resolve: typeof resolveContent;
  article: typeof analyzeArticle;
  video: typeof analyzeVideo;
  transcript: (url: string) => Promise<YouTubeTranscriptResult>;
  videoTitle: (url: string) => Promise<string>;
};

const productionDependencies: Dependencies = { validateApi: resolveSportabaseApiOrigin, resolve: resolveContent, article: analyzeArticle, video: analyzeVideo, transcript: fetchYouTubeTranscript, videoTitle: fetchYouTubeVideoTitle };

export function normalizedAnalysisUrl(raw: string) {
  let parsed: URL;
  try { parsed = new URL(raw.trim()); } catch { throw new Error('Enter a complete article or YouTube URL.'); }
  if (parsed.protocol !== 'https:' && parsed.protocol !== 'http:') throw new Error('Use an http or https URL.');
  return parsed.toString();
}

function isYouTubeUrl(raw: string) {
  const host = new URL(raw).hostname.toLowerCase().replace(/^www\./, '');
  return host === 'youtube.com' || host.endsWith('.youtube.com') || host === 'youtu.be';
}

async function analyzeYouTube(url: string, dependencies: Dependencies, onAnalyze: () => void): Promise<ProductAnalysisResult> {
  const [transcript, title] = await Promise.all([dependencies.transcript(url), dependencies.videoTitle(url)]);
  onAnalyze();
  const data = await dependencies.video({ title, transcript: transcript.transcript, url, transcript_metadata: { segment_count: transcript.segmentCount, character_count: transcript.characterCount, language: transcript.language || undefined, extraction_method: 'youtube-transcript' } });
  return { kind: 'video', data };
}

export async function runProductAnalysis(rawUrl: string, dependencies: Dependencies = productionDependencies, onPhase?: (phase: ProductAnalysisPhase) => void): Promise<ProductAnalysisResult> {
  const url = normalizedAnalysisUrl(rawUrl);
  dependencies.validateApi();
  onPhase?.('resolving');
  if (isYouTubeUrl(url)) return analyzeYouTube(url, dependencies, () => onPhase?.('analyzing'));
  const resolved = await dependencies.resolve(url);
  if (resolved.mode === 'video' || resolved.source === 'youtube') return analyzeYouTube(resolved.normalized_url || url, dependencies, () => onPhase?.('analyzing'));
  onPhase?.('analyzing');
  const data = await dependencies.article({ title: resolved.title, url: resolved.normalized_url || url, text: resolved.content });
  return { kind: 'article', data };
}
