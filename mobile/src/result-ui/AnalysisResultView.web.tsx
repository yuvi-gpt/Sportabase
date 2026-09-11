import { LinearGradient } from 'expo-linear-gradient';
import { type ReactNode, useEffect, useMemo, useRef, useState } from 'react';
import { Animated, Linking, Pressable, StyleSheet, Text, View } from 'react-native';

import type {
  AnalysisDetailSection,
  AnalysisEvidenceViewModel,
  AnalysisRelatedReport,
  AnalysisResultPalette,
  AnalysisResultViewModel,
} from './analysis-result-model';

export const RESULT_REVEAL_MS = 520;

function rise(enter: Animated.Value, delay: number) {
  return {
    opacity: enter.interpolate({ inputRange: [0, delay, Math.min(1, delay + .34)], outputRange: [0, 0, 1] }),
    transform: [{ translateY: enter.interpolate({ inputRange: [0, delay, Math.min(1, delay + .34)], outputRange: [8, 8, 0] }) }],
  };
}

function SourceStrip({ mobile, model, styles }: { mobile: boolean; model: AnalysisResultViewModel; styles: ReturnType<typeof createStyles> }) {
  const open = () => { if (model.sourceUrl) void Linking.openURL(model.sourceUrl); };
  return <View style={[styles.sourceStrip, mobile && styles.sourceStripMobile]}>
    {model.sourceItems.map((item, index) => <View key={`${item.label}-${index}`} style={styles.sourceItem}><Text style={[styles.sourceText, item.primary && styles.sourcePrimary]}>{item.label}</Text></View>)}
    {model.sourceUrl ? <Pressable accessibilityRole="link" onPress={open} style={styles.sourceLink}><Text numberOfLines={1} style={styles.sourceLinkText}>{model.sourceLinkLabel || 'View source'} ↗</Text></Pressable> : null}
  </View>;
}

function RelatedRow({ accent, item, styles }: { accent: string; item: AnalysisRelatedReport; styles: ReturnType<typeof createStyles> }) {
  const content = <>
    <View style={styles.relatedTop}><Text style={styles.relatedSource}>{item.source}</Text><Text style={styles.relatedTime}>{item.time}</Text></View>
    <Text style={styles.relatedHeadline}>{item.headline}</Text>
    <View style={styles.relationshipRow}><View style={[styles.relationshipMark, { backgroundColor: accent }]} /><Text style={[styles.relationship, { color: accent }]}>{item.relationship}</Text><Text style={styles.sourceType}>{item.sourceType}</Text>{item.url ? <Text style={styles.external}>↗</Text> : null}</View>
  </>;
  return item.url
    ? <Pressable accessibilityRole="link" onPress={() => void Linking.openURL(item.url!)} style={({ pressed }) => [styles.relatedRow, pressed && styles.pressed]}>{content}</Pressable>
    : <View style={styles.relatedRow}>{content}</View>;
}

function RelatedRail({ accent, model, styles }: { accent: string; model: AnalysisResultViewModel; styles: ReturnType<typeof createStyles> }) {
  const loading = model.railState === 'loading';
  const failed = model.railState === 'error';
  return <View style={styles.rail} testID="analysis-related-rail">
    <Text style={styles.sectionLabel}>Who else is reporting this?</Text>
    <Text style={styles.railIntro}>Reports concerning the same claim, people and event window.</Text>
    {loading ? <Text style={styles.railEmpty}>Loading reporting context…</Text> : null}
    {failed ? <View><Text style={styles.railEmpty}>Reporting context could not be loaded.</Text>{model.onRetryContext ? <Pressable accessibilityRole="button" onPress={model.onRetryContext} style={({ pressed }) => [styles.retry, pressed && styles.pressed]}><Text style={styles.retryText}>Retry intelligence</Text></Pressable> : null}</View> : null}
    {!loading && !failed && model.relatedReports.length ? <View style={styles.relatedList}>{model.relatedReports.map((item) => <RelatedRow key={item.id} item={item} accent={accent} styles={styles} />)}</View> : null}
    {!loading && !failed && !model.relatedReports.length ? <Text style={styles.railEmpty}>No verified related-report data is available in this analysis response.</Text> : null}
    <View style={styles.evolution}>
      <Text style={styles.sectionLabel}>Story evolution</Text>
      <Text style={styles.railIntro}>A local preview of how the reporting landscape is changing.</Text>
      {loading ? <Text style={styles.railEmpty}>Loading story evolution…</Text> : null}
      {failed ? <Text style={styles.railEmpty}>Story evolution could not be loaded.</Text> : null}
      {!loading && !failed && model.evolution.map((item, index) => <View key={item.id} style={styles.evolutionRow}><View style={styles.evolutionTrack}><View style={[styles.evolutionDot, { borderColor: accent }]} />{index < model.evolution.length - 1 ? <View style={styles.evolutionLine} /> : null}</View><View style={styles.evolutionCopy}><Text style={styles.evolutionLabel}>{item.label}</Text><Text style={styles.evolutionDetail}>{item.detail}</Text></View></View>)}
      {!loading && !failed && !model.evolution.length ? <Text style={styles.railEmpty}>No verified story-evolution data is available in this analysis response.</Text> : null}
    </View>
  </View>;
}

function EvidenceBlock({ evidence, mobile, styles }: { evidence: AnalysisEvidenceViewModel; mobile: boolean; styles: ReturnType<typeof createStyles> }) {
  return <View style={[styles.intelligence, mobile && styles.full]} testID="analysis-evidence-block">
    <Text style={[styles.label, { color: evidence.accent }]}>Evidence status</Text>
    <View style={styles.statusRow}><View style={[styles.statusMark, { borderColor: evidence.accent }]} /><Text style={[styles.status, mobile && styles.statusMobile]}>{evidence.status}</Text></View>
    {evidence.detail ? <Text style={styles.intelligenceDetail}>{evidence.detail}</Text> : null}
    {evidence.metrics.length ? <View style={styles.metrics}>{evidence.metrics.map((metric) => <View key={metric.label} style={styles.metricRow}><Text style={styles.metricLabel}>{metric.label}</Text><Text style={styles.metricValue}>{metric.value}</Text></View>)}</View> : null}
    {evidence.signal ? <Text style={styles.intelligenceSignal}>{evidence.signal}</Text> : null}
  </View>;
}

function ArticlePrimary({ enter, mobile, model, styles }: { enter: Animated.Value; mobile: boolean; model: AnalysisResultViewModel; styles: ReturnType<typeof createStyles> }) {
  const merit = model.merit!;
  const evidence = model.evidence!;
  return <Animated.View style={[styles.primary, mobile && styles.primaryMobile, rise(enter, .18)]} testID="analysis-article-primary">
    <View style={[styles.merit, mobile && styles.full]} testID="analysis-merit-block"><Text style={styles.label}>Merit</Text><Text style={[styles.score, mobile && styles.scoreMobile]}>{merit.score}</Text><LinearGradient colors={[...merit.colors]} start={{ x: 0, y: .5 }} end={{ x: 1, y: .5 }} style={styles.meritRail} /><Text style={[styles.band, { color: merit.colors[1] }]}>{merit.band}</Text><Text style={styles.disclaimer}>{merit.disclaimer}</Text></View>
    <EvidenceBlock evidence={evidence} mobile={mobile} styles={styles} />
  </Animated.View>;
}

function VideoPrimary({ enter, mobile, model, styles }: { enter: Animated.Value; mobile: boolean; model: AnalysisResultViewModel; styles: ReturnType<typeof createStyles> }) {
  return <Animated.View style={[styles.videoScores, mobile && styles.videoScoresMobile, rise(enter, .18)]} testID="analysis-video-primary">{(model.videoMetrics || []).map((metric) => <View key={metric.label} style={styles.videoMetric}><Text style={styles.label}>{metric.label}</Text><Text style={[metric.label === 'Verdict' ? styles.verdict : styles.videoScore, mobile && (metric.label === 'Verdict' ? styles.verdictMobile : styles.videoScoreMobile)]}>{metric.value}{metric.maximum ? <Text style={styles.scoreMaximum}>{metric.maximum}</Text> : null}</Text><Text style={styles.metricNote}>{metric.note}</Text></View>)}</Animated.View>;
}

function Summary({ accent, enter, mobile, model, styles }: { accent: string; enter: Animated.Value; mobile: boolean; model: AnalysisResultViewModel; styles: ReturnType<typeof createStyles> }) {
  return <Animated.View style={[styles.summary, rise(enter, .35)]}><Text style={styles.sectionLabel}>{model.summaryLabel}</Text>{model.summary.length ? <View style={[styles.summaryGrid, mobile && styles.summaryMobile]}>{model.summary.map((item, index) => <Animated.View key={`${index}-${item}`} style={[styles.summaryItem, mobile && styles.summaryItemMobile, { opacity: enter.interpolate({ inputRange: [0, .41 + index * .04, Math.min(1, .64 + index * .04)], outputRange: [0, 0, 1] }) }]}><Text style={[styles.summaryNumber, { color: accent }]}>{String(index + 1).padStart(2, '0')}</Text><Text style={styles.summaryText}>{item}</Text></Animated.View>)}</View> : <Text style={styles.summaryEmpty}>No summary points are available in this analysis response.</Text>}</Animated.View>;
}

function MobileDetailSection({ accent, detail, onPress, open, styles }: { accent: string; detail: AnalysisDetailSection; onPress: () => void; open: boolean; styles: ReturnType<typeof createStyles> }) {
  return <View style={styles.mobileSection}><Pressable accessibilityRole="button" accessibilityState={{ expanded: open }} onPress={onPress} style={({ pressed }) => [styles.mobileTrigger, pressed && styles.pressed]}><View style={styles.mobileTitleWrap}><Text style={styles.detailMobileTitle}>{detail.title}</Text><Text numberOfLines={1} style={styles.preview}>{detail.preview}</Text></View><Text style={[styles.chevron, { color: accent }, open && styles.chevronOpen]}>⌄</Text></Pressable>{open ? <View style={styles.body}>{detail.paragraphs.map((paragraph, index) => <Text key={`${index}-${paragraph}`} style={styles.paragraph}>{paragraph}</Text>)}</View> : null}</View>;
}

function Details({ accent, enter, mobile, model, styles }: { accent: string; enter: Animated.Value; mobile: boolean; model: AnalysisResultViewModel; styles: ReturnType<typeof createStyles> }) {
  const [openMobile, setOpenMobile] = useState<string | null>(null);
  if (!model.details.length) return null;
  return <Animated.View style={rise(enter, .56)}>{mobile ? <View style={styles.mobileDetails}><Text style={styles.sectionLabel}>Analysis details</Text>{model.details.map((detail) => <MobileDetailSection key={detail.key} detail={detail} open={openMobile === detail.key} accent={accent} onPress={() => setOpenMobile(openMobile === detail.key ? null : detail.key)} styles={styles} />)}</View> : <View style={styles.desktopWrap}><Text style={styles.detailSectionLabel}>Analysis details</Text><View style={styles.columns}>{model.details.map((detail) => <View key={detail.key} style={styles.column}><View style={[styles.accentRule, { backgroundColor: accent }]} /><Text style={styles.desktopTitle}>{detail.title}</Text>{detail.paragraphs.map((paragraph, index) => <Text key={`${index}-${paragraph}`} style={styles.desktopParagraph}>{paragraph}</Text>)}</View>)}</View></View>}</Animated.View>;
}

export function AnalysisResultView({ header, mobile, model, onSettled, palette, reduceMotion = false }: { header?: ReactNode; mobile: boolean; model: AnalysisResultViewModel; onSettled?: () => void; palette: AnalysisResultPalette; reduceMotion?: boolean }) {
  const styles = useMemo(() => createStyles(palette), [palette]);
  const enter = useRef(new Animated.Value(reduceMotion ? 1 : 0)).current;
  useEffect(() => {
    if (reduceMotion) { enter.stopAnimation(); enter.setValue(1); onSettled?.(); return; }
    const animation = Animated.timing(enter, { toValue: 1, duration: RESULT_REVEAL_MS, useNativeDriver: false });
    animation.start(({ finished }) => { if (finished) onSettled?.(); });
    return () => animation.stop();
  }, [enter, onSettled, reduceMotion]);
  const accent = model.evidence?.accent || palette.teal;
  const primary = model.mode === 'article'
    ? <ArticlePrimary enter={enter} mobile={mobile} model={model} styles={styles} />
    : <VideoPrimary enter={enter} mobile={mobile} model={model} styles={styles} />;
  const summary = <Summary accent={accent} enter={enter} mobile={mobile} model={model} styles={styles} />;
  const details = <Details accent={accent} enter={enter} mobile={mobile} model={model} styles={styles} />;
  const rail = <Animated.View style={rise(enter, .45)}><RelatedRail accent={accent} model={model} styles={styles} /></Animated.View>;
  return <View style={[styles.page, mobile && styles.pageMobile]} testID={`${model.mode}-analysis-result`}>
    {header ? <Animated.View style={rise(enter, 0)}>{header}</Animated.View> : null}
    <Animated.View style={[styles.intro, mobile && styles.introMobile, rise(enter, .05)]}><Text style={[styles.type, { color: accent }]}>{model.contentType}</Text><Text accessibilityRole="header" aria-level={1} style={[styles.claim, mobile && styles.claimMobile]}>{model.claim}</Text><SourceStrip model={model} mobile={mobile} styles={styles} /></Animated.View>
    {mobile ? <>{primary}{summary}{rail}{details}</> : <View style={styles.dossier}><View style={styles.mainColumn}>{primary}{summary}{details}</View><View style={styles.sideColumn}>{rail}</View></View>}
  </View>;
}

const createStyles = (palette: AnalysisResultPalette) => StyleSheet.create({
  page:{position:'relative',width:'100%',minWidth:0},pageMobile:{maxWidth:'100%',overflow:'hidden'},intro:{maxWidth:1030,minWidth:0,paddingTop:38},introMobile:{paddingTop:26},type:{fontSize:13,lineHeight:18,fontWeight:'800',letterSpacing:1.1,textTransform:'uppercase'},claim:{color:palette.text,fontSize:43,lineHeight:51,letterSpacing:-1.3,fontWeight:'800',marginTop:12,maxWidth:1000},claimMobile:{fontSize:30,lineHeight:36,letterSpacing:-.7,marginTop:9,width:'100%',maxWidth:'100%',flexShrink:1},sourceStrip:{flexDirection:'row',alignItems:'center',flexWrap:'wrap',marginTop:22,borderTopWidth:1,borderBottomWidth:1,borderColor:palette.line,minHeight:46,minWidth:0},sourceStripMobile:{marginTop:18,paddingVertical:8},sourceItem:{paddingRight:13,marginRight:13,borderRightWidth:1,borderRightColor:palette.line},sourceText:{color:palette.muted,fontSize:12,lineHeight:20},sourcePrimary:{color:palette.secondary,fontWeight:'800'},sourceLink:{minHeight:36,justifyContent:'center',paddingHorizontal:6,minWidth:0,maxWidth:'100%'},sourceLinkText:{color:palette.teal,fontSize:12,fontWeight:'800'},
  dossier:{flexDirection:'row',alignItems:'flex-start',gap:48,width:'100%',minWidth:0},mainColumn:{flexGrow:68,flexShrink:1,flexBasis:0,minWidth:0},sideColumn:{flexGrow:32,flexShrink:1,flexBasis:0,minWidth:0,paddingTop:42},primary:{flexDirection:'row',gap:40,width:'100%',marginTop:42,alignItems:'flex-start',minWidth:0},primaryMobile:{flexDirection:'column',gap:30,marginTop:28,paddingTop:24,borderTopWidth:1,borderTopColor:palette.line},merit:{width:'34%',flexGrow:0,flexShrink:0,paddingLeft:2,minWidth:0},full:{width:'100%'},label:{color:palette.muted,textTransform:'uppercase',letterSpacing:1.1,fontSize:12,fontWeight:'800'},score:{color:palette.text,fontSize:100,lineHeight:106,fontWeight:'900',letterSpacing:-5,marginTop:6,fontVariant:['tabular-nums']},scoreMobile:{fontSize:80,lineHeight:88,letterSpacing:-3.5},meritRail:{height:3,width:170,marginTop:4},band:{fontSize:12,fontWeight:'900',letterSpacing:1,textTransform:'uppercase',marginTop:10},disclaimer:{color:palette.muted,fontSize:13,lineHeight:19,marginTop:12,maxWidth:230},intelligence:{flex:1,minWidth:0},statusRow:{flexDirection:'row',alignItems:'center',gap:12,marginTop:11,marginBottom:17},statusMark:{width:16,height:16,borderRadius:9,borderWidth:3},status:{color:palette.text,fontSize:25,lineHeight:31,fontWeight:'800'},statusMobile:{fontSize:24,lineHeight:30},intelligenceDetail:{color:palette.muted,fontSize:13,lineHeight:19,marginBottom:14},metrics:{borderTopWidth:1,borderTopColor:palette.line},metricRow:{minHeight:42,flexDirection:'row',alignItems:'center',justifyContent:'space-between',gap:14,borderBottomWidth:1,borderBottomColor:palette.line},metricLabel:{color:palette.secondary,fontSize:13,flex:1},metricValue:{color:palette.text,fontSize:13,fontWeight:'700',textAlign:'right',maxWidth:'56%'},intelligenceSignal:{color:palette.muted,fontSize:11,lineHeight:17,marginTop:11},
  videoScores:{flexDirection:'row',gap:40,width:'100%',marginTop:42,alignItems:'flex-start',minWidth:0},videoScoresMobile:{flexDirection:'column',gap:30,marginTop:28,paddingTop:24,borderTopWidth:1,borderTopColor:palette.line},videoMetric:{flex:1,minWidth:0},videoScore:{color:palette.text,fontSize:62,lineHeight:70,fontWeight:'900',letterSpacing:-3,marginTop:10,fontVariant:['tabular-nums']},videoScoreMobile:{fontSize:54,lineHeight:62},scoreMaximum:{color:palette.muted,fontSize:17,fontWeight:'700',letterSpacing:0},verdict:{color:palette.text,fontSize:30,lineHeight:36,fontWeight:'800',marginTop:17},verdictMobile:{fontSize:27,lineHeight:33},metricNote:{color:palette.muted,fontSize:13,lineHeight:19,marginTop:10},
  summary:{borderTopWidth:1,borderTopColor:palette.line,marginTop:44,paddingTop:27},sectionLabel:{color:palette.muted,textTransform:'uppercase',letterSpacing:1.05,fontSize:11,fontWeight:'900',marginBottom:17},summaryGrid:{flexDirection:'row',flexWrap:'wrap',columnGap:30,rowGap:22},summaryMobile:{flexDirection:'column',gap:0},summaryItem:{width:'47%',flexDirection:'row',gap:13,paddingTop:12,borderTopWidth:1,borderTopColor:palette.line},summaryItemMobile:{width:'100%',paddingVertical:15},summaryNumber:{fontSize:11,fontWeight:'900',letterSpacing:.5,paddingTop:3},summaryText:{color:palette.secondary,fontSize:15,lineHeight:23,flex:1},summaryEmpty:{color:palette.muted,fontSize:13,lineHeight:19,paddingTop:12,borderTopWidth:1,borderTopColor:palette.line},
  rail:{borderLeftWidth:1,borderLeftColor:palette.line,paddingLeft:28},railIntro:{color:palette.muted,fontSize:12,lineHeight:18,marginTop:-8,marginBottom:8},railEmpty:{color:palette.muted,fontSize:12,lineHeight:18,paddingVertical:17,borderTopWidth:1,borderTopColor:palette.line},retry:{alignSelf:'flex-start',borderWidth:1,borderColor:palette.line,paddingHorizontal:12,paddingVertical:8,marginBottom:14},retryText:{color:palette.secondary,fontSize:12,fontWeight:'800'},relatedList:{marginTop:4},relatedRow:{paddingVertical:17,borderTopWidth:1,borderTopColor:palette.line},pressed:{opacity:.62},relatedTop:{flexDirection:'row',justifyContent:'space-between',gap:10},relatedSource:{color:palette.text,fontSize:13,fontWeight:'800',flex:1},relatedTime:{color:palette.muted,fontSize:11},relatedHeadline:{color:palette.secondary,fontSize:14,lineHeight:20,fontWeight:'600',marginTop:7},relationshipRow:{flexDirection:'row',alignItems:'center',gap:7,marginTop:10,flexWrap:'wrap'},relationshipMark:{width:5,height:5,borderRadius:3},relationship:{fontSize:10,fontWeight:'900',textTransform:'uppercase',letterSpacing:.45},sourceType:{color:palette.muted,fontSize:10},external:{color:palette.muted,fontSize:12,marginLeft:'auto'},evolution:{marginTop:36,paddingTop:24,borderTopWidth:1,borderTopColor:palette.line},evolutionRow:{flexDirection:'row',gap:11,minHeight:53},evolutionTrack:{width:12,alignItems:'center'},evolutionDot:{width:8,height:8,borderRadius:4,borderWidth:2,backgroundColor:palette.ground},evolutionLine:{width:1,flex:1,backgroundColor:palette.line},evolutionCopy:{flex:1,paddingBottom:14},evolutionLabel:{color:palette.secondary,fontSize:11,fontWeight:'800',textTransform:'uppercase',letterSpacing:.5},evolutionDetail:{color:palette.muted,fontSize:12,lineHeight:18,marginTop:3},
  mobileDetails:{marginTop:42,borderBottomWidth:1,borderBottomColor:palette.line},mobileSection:{borderTopWidth:1,borderTopColor:palette.line},mobileTrigger:{minHeight:82,flexDirection:'row',alignItems:'center',gap:14,paddingVertical:15},mobileTitleWrap:{flex:1,gap:5},detailMobileTitle:{color:palette.text,fontSize:16,lineHeight:22,fontWeight:'800',textTransform:'uppercase',letterSpacing:.6},preview:{color:palette.muted,fontSize:13,lineHeight:18},chevron:{fontSize:24,transform:[{rotate:'0deg'}]},chevronOpen:{transform:[{rotate:'180deg'}]},body:{paddingRight:8,paddingBottom:24,gap:10},paragraph:{color:palette.secondary,fontSize:15,lineHeight:23},desktopWrap:{borderTopWidth:1,borderTopColor:palette.line,marginTop:42,paddingTop:28},detailSectionLabel:{color:palette.muted,textTransform:'uppercase',letterSpacing:1.1,fontSize:12,fontWeight:'800'},columns:{flexDirection:'row',gap:64,marginTop:26},column:{flex:1,maxWidth:510,minWidth:0},accentRule:{width:38,height:2,marginBottom:16},desktopTitle:{color:palette.text,fontSize:19,fontWeight:'800',marginBottom:12},desktopParagraph:{color:palette.secondary,fontSize:16,lineHeight:25,marginBottom:9},
});
