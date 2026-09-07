import { useLocalSearchParams } from 'expo-router';
import { ScrollView, StyleSheet, useWindowDimensions, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { DesignLabAnalyzing } from '../design-lab/DesignLabAnalyzing';
import { palette } from '../design-lab/design-lab-theme';
export default function DesignLabAnalyzingPreview(){const{viewport,debug}=useLocalSearchParams<{viewport?:string;debug?:string}>();const{width}=useWindowDimensions();const layoutWidth=viewport==='390'?390:viewport==='360'?360:width;const mobile=layoutWidth<700;return <SafeAreaView style={styles.safe}><ScrollView contentContainerStyle={styles.scroll}><View style={[styles.shell,mobile&&{width:Math.max(layoutWidth-40,280),paddingHorizontal:0}]}><DesignLabAnalyzing mobile={mobile} url="http://localhost:8082/design-lab-fixtures/01-confirmed-high.html" motionDebug={debug==='1'}/></View></ScrollView></SafeAreaView>}
const styles=StyleSheet.create({safe:{flex:1,backgroundColor:palette.ground},scroll:{minHeight:'100%'},shell:{maxWidth:1220,width:'100%',alignSelf:'center',paddingHorizontal:34}});
