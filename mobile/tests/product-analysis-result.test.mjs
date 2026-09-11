import assert from 'node:assert/strict';
import test from 'node:test';
import { readFile, readdir } from 'node:fs/promises';

const [homepage, productResult, designResult, sharedView, sharedModel, sharedGeometry, designGeometry, api, contextHook, backendContext] = await Promise.all([
  '../src/product-ui/ProductAnalyze.web.tsx',
  '../src/product-ui/ProductAnalysisResult.web.tsx',
  '../src/design-lab/DesignLabResult.tsx',
  '../src/result-ui/AnalysisResultView.web.tsx',
  '../src/result-ui/analysis-result-model.ts',
  '../src/result-ui/AnalysisResultGeometry.web.tsx',
  '../src/design-lab/DesignLabGeometry.tsx',
  '../src/lib/api.ts',
  '../src/lib/use-analysis-result-context.ts',
  '../../backend/app/intelligence/analysis_result_context.py',
].map((path) => readFile(new URL(path, import.meta.url), 'utf8')));
const productUiFiles = await readdir(new URL('../src/product-ui/', import.meta.url));
const resultBranch = homepage.match(/if \(phase === 'result' && result\) \{[\s\S]*?(?=\n\s*if \(busy\))/)?.[0] ?? '';

test('Design Lab and production delegate to one shared result renderer', () => {
  for (const adapter of [designResult, productResult]) {
    assert.match(adapter, /import \{ AnalysisResultView \} from '\.\.\/result-ui\/AnalysisResultView\.web'/);
    assert.match(adapter, /<AnalysisResultView/);
    assert.doesNotMatch(adapter, /StyleSheet|createStyles|function SourceStrip|function RelatedRail|function Summary/);
  }
  assert.equal((sharedView.match(/StyleSheet\.create/g) ?? []).length, 1);
  for (const renderer of ['SourceStrip', 'RelatedRail', 'Summary', 'ArticlePrimary', 'EvidenceBlock', 'Details']) assert.match(sharedView, new RegExp(`function ${renderer}`));
});

test('shared renderer preserves the approved safe dossier and primary geometry', () => {
  assert.match(sharedView, /dossier:\{flexDirection:'row',alignItems:'flex-start',gap:48,width:'100%',minWidth:0\}/);
  assert.match(sharedView, /mainColumn:\{flexGrow:68,flexShrink:1,flexBasis:0,minWidth:0\}/);
  assert.match(sharedView, /sideColumn:\{flexGrow:32,flexShrink:1,flexBasis:0,minWidth:0,paddingTop:42\}/);
  assert.doesNotMatch(sharedView, /mainColumn:\{[^}]*width:'68%'|sideColumn:\{[^}]*width:'32%'/);
  assert.match(sharedView, /primary:\{flexDirection:'row',gap:40,width:'100%',marginTop:42,alignItems:'flex-start',minWidth:0\}/);
  assert.match(sharedView, /merit:\{width:'34%',flexGrow:0,flexShrink:0,paddingLeft:2,minWidth:0\}/);
  assert.match(sharedView, /score:\{[^}]*fontSize:100,lineHeight:106[^}]*letterSpacing:-5/);
  assert.match(sharedView, /meritRail:\{height:3,width:170,marginTop:4\}/);
  assert.match(sharedView, /claim:\{[^}]*fontSize:43,lineHeight:51,letterSpacing:-1\.3[^}]*marginTop:12,maxWidth:1000\}/);
  assert.match(sharedView, /summaryItem:\{width:'47%'/);
});

test('shared renderer keeps Design Lab typography behavior without a result font override', () => {
  assert.doesNotMatch(sharedView, /fontFamily|productFonts|resultFonts|SportabaseBarlow/);
  assert.doesNotMatch(productResult, /fontFamily|productFonts|resultFonts|ProductResultFonts|useProductResultFonts|SportabaseBarlow/);
  assert.doesNotMatch(designResult, /fontFamily|resultFonts|SportabaseBarlow/);
  assert.equal(productUiFiles.some((file) => /result.*fonts?/i.test(file)), false);
});

test('article Merit and Evidence remain distinct and Evidence always has a branch', () => {
  assert.match(productResult, /data\.merit_score/);
  assert.match(productResult, /getAnalysisMeritBand/);
  assert.match(sharedView, />Merit<\/Text>/);
  assert.match(productResult, /Informational value, not truth probability\./);
  assert.match(sharedView, />Evidence status<\/Text>/);
  assert.match(productResult, /Checking intelligence…/);
  assert.match(productResult, /No linked evidence intelligence is available in this analysis response\./);
  for (const label of ['Corroboration', 'Independence', 'Sources located', 'Verification pairs', 'Merit impact']) assert.match(productResult, new RegExp(label));
  assert.doesNotMatch(productResult, /Independent sources|independent source count/i);
});

test('context hydration supports loading, populated, empty, error, and retry without rerunning analysis', () => {
  assert.match(api, /export function getAnalysisResultContext\(url: string\)/);
  assert.match(api, /\/intelligence\/result-context\?url=/);
  assert.match(homepage, /useAnalysisResultContext\(url, phase === 'result' && result !== null\)/);
  assert.match(homepage, /onRetryContext=\{resultContext\.retry\}/);
  assert.match(contextHook, /getAnalysisResultContext\(sourceUrl\)/);
  assert.match(contextHook, /setAttempt\(\(value\) => value \+ 1\)/);
  assert.doesNotMatch(contextHook, /runProductAnalysis|\/analyze/);
  assert.doesNotMatch(sharedView, /runProductAnalysis/);
  assert.match(sharedView, /Loading reporting context…/);
  assert.match(sharedView, /No verified related-report data is available in this analysis response\./);
  assert.match(sharedView, /Reporting context could not be loaded\./);
  assert.match(sharedView, /Retry intelligence/);
  assert.match(sharedView, /No verified story-evolution data is available in this analysis response\./);
});

test('shared rail renders real relationship labels including verified Official stakeholder', () => {
  assert.match(sharedView, /item\.relationship/);
  assert.match(sharedView, /relationshipMark/);
  assert.match(backendContext, /relationship = "Official stakeholder"/);
  assert.match(backendContext, /relationship = "Independent reporting"/);
  assert.match(backendContext, /relationship = "Related reporting"/);
  assert.match(backendContext, /verification_status = 'verified'/);
});

test('video uses the same renderer while scores and verdict remain separate', () => {
  assert.match(productResult, /label: 'Evidence score', value: String\(data\.evidence_score\)/);
  assert.match(productResult, /label: 'Logic score', value: String\(data\.logic_score\)/);
  assert.match(productResult, /label: 'Verdict', value: data\.localized_verdict/);
  assert.match(sharedView, /model\.videoMetrics/);
  assert.doesNotMatch(productResult, /compositeScore|credibility_score/);
});

test('Design Lab and production share the same contained result geometry', () => {
  assert.match(designGeometry, /import \{ AnalysisResultGeometry/);
  assert.match(designGeometry, /if \(mode === 'result'\) return <AnalysisResultGeometry/);
  assert.match(homepage, /import \{ AnalysisResultGeometry/);
  assert.match(resultBranch, /<AnalysisResultGeometry compact=\{mobile\}/);
  assert.doesNotMatch(resultBranch, /ProductWatermark|approvedHome/);
  assert.equal(productUiFiles.includes('ProductResultGeometry.web.tsx'), false);
  assert.match(sharedGeometry, /testID="analysis-result-geometry"/);
  assert.match(sharedGeometry, /viewportLayer: \{ position: 'absolute', top: 0, right: 0, bottom: 0, left: 0, zIndex: 0, overflow: 'hidden', pointerEvents: 'none' \}/);
  assert.match(sharedGeometry, /if \(reduceMotion\)/);
});

test('production adapter is isolated from Design Lab fixtures and modules', () => {
  for (const source of [productResult, homepage, sharedView, sharedModel, sharedGeometry]) {
    assert.doesNotMatch(source, /from ['"][^'"]*design-lab/i);
    assert.doesNotMatch(source, /mock-results|fixtureByPath|discovery-data|DesignLabResult|design-lab-theme/);
  }
});
