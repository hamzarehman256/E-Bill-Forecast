import {
    LineChart
  } from "react-native-chart-kit";
  import { Dimensions, Text, View } from "react-native";
import { ScrollView } from 'react-native-gesture-handler';
const screenWidth = Dimensions.get("window").width;
import React, {useState} from 'react'



const forecast = ( {navigation} ) => {

  
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
      labels: ["KW/h"],
      datasets: [
        {
          data: [2, 4, 3, 2.5, 2.8, 2.1, 1.8, 2.1, 2],
          color: (opacity = 1) => `rgba(134, 65, 244, ${opacity})`, 
          strokeWidth: 2 
        }
      ],
      legend: ["Predicted Units Consumed"] 
    };
  
  
  
    return (
      
        <React.Fragment>
        <View>
      <LineChart
      data={data}
      width={screenWidth}
      height={256}
      verticalLabelRotation={30}
      chartConfig={chartConfig}
      bezier
    />
    </View>
    
    <View>
            <Text style={{alignItems: 'center', textAlign: 'center'}}>Predicted Units Consumption: 48 </Text>
        </View>
    
    </React.Fragment>
    
   
    );
  };
  
  
  export default forecast
  