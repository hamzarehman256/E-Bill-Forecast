import React, {useState} from 'react'
import {SafeAreaView,
  Text,
  View,
  StyleSheet,
  Button,
  ActivityIndicator, } from 'react-native';
  import {
    LineChart
  } from "react-native-chart-kit";
  import { Dimensions } from "react-native";
import { ScrollView } from 'react-native-gesture-handler';
const screenWidth = Dimensions.get("window").width;
import Background from '../components/Background'
import Logo from '../components/Logo'
import Header from '../components/Header'
import Paragraph from '../components/Paragraph'
// import Button from '../components/Button'
import { logoutUser } from '../api/auth-api'

const BillForecast = ( {navigation} ) => {

  const [loading, setLoading] = useState(false);


  const chartConfig = {
    backgroundGradientFrom: "#1E2923",
    backgroundGradientFromOpacity: 0,
    backgroundGradientTo: "#08130D",
    backgroundGradientToOpacity: 0.5,
    color: (opacity = 1) => `rgba(26, 255, 146, ${opacity})`,
    strokeWidth: 2, // optional, default 3
    barPercentage: 0.5,
    useShadowColorFromDataset: false // optional
  };
  const data = {
    labels: ["Volts"],
    datasets: [
      {
        data: [215, 224, 228, 218, 219, 214, 205, 211, 220, 223, 207, 217, 206, 203, 232],
        color: (opacity = 1) => `rgba(134, 65, 244, ${opacity})`, 
        strokeWidth: 2 
      }
    ],
    legend: ["Voltage"] 
  };

  const startLoading = () => {
    setLoading(true);
    setTimeout(() => {
      setLoading(false);
      navigation.navigate("forecast");
    }, 3000);
    
  };

  return (
    <SafeAreaView style={{ flex: 1 }}>
      <View style={styles.container}>
        {loading ? (
          <ActivityIndicator
            //visibility of Overlay Loading Spinner
            visible={loading}
            textStyle={styles.spinnerTextStyle}
          />
        ) : (
          <>
            
            <Button style={{ textAlign: 'center', fontSize: 20 }} title="Forecast" onPress={startLoading}></Button>
          </>
        )}
      </View>
    
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
    textAlign: 'center',
    paddingTop: 30,
    backgroundColor: '#ecf0f1',
    padding: 8,
  },
  spinnerTextStyle: {
    color: '#FFF',
  },
});


export default BillForecast
