import React, {useState, useEffect} from 'react'
import {View, Text} from 'react-native';
import Background from '../components/Background'
import Logo from '../components/Logo'
import Header from '../components/Header'
import Paragraph from '../components/Paragraph'
import Button from '../components/Button'
import { logoutUser } from '../api/auth-api'
import {
  LineChart
} from "react-native-chart-kit";
import { Dimensions } from "react-native";
import { ScrollView } from 'react-native-gesture-handler';
const screenWidth = Dimensions.get("window").width;

const ReportScreen = ( {navigation} ) => {


  const [alerts, setAlerts] = useState([])
  const [ampere, setAmpere] = useState([])
  const [power, setPower] = useState([])

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

  const data1 = {
    labels: ["Amp"],
    datasets: [
      {
        data: [0.20, 0.45, 0.28, 0.80, 1.9, 4.3, 0.10, 0.32, 0.21, 0.14, 0.10, 0.16, 0.18, 0.15, 0.20],
        color: (opacity = 1) => `rgba(134, 65, 244, ${opacity})`, 
        strokeWidth: 2 
      }
    ],
    legend: ["Current"] 
  };

  const data2 = {
    labels: ["Watt"],
    datasets: [
      {
        data: [20, 45, 28, 20, 24, 143, 19, 15, 18, 20, 16, 14, 12, 10, 8],
        color: (opacity = 1) => `rgba(134, 65, 244, ${opacity})`, 
        strokeWidth: 2 
      }
    ],
    legend: ["Power"] 
  };
  

  useEffect(() => {
      function getAlerts() {
        var count = 0;
        fetch("http://192.168.43.6:8123/api/states/sensor.voltage", {
          method: "GET",
          headers: new Headers({
             'Authorization': 'Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiIwMTI0NjA5ODc2MTI0YTQ1YTk4MDFlODE4ZGQ5YmY2MSIsImlhdCI6MTYxMzc0NTc3MCwiZXhwIjoxOTI5MTA1NzcwfQ.RHzgHe6BpmtihYkcrhwX-fTUGYKorPWB1YuPa3Dj_g8',
             'Accept': 'application/json',
            'Content-Type': 'application/json'
          }),
        })
          .then(response => response.json())
          .then(response => {
            setAlerts(response);
            console.log("This is Response " + response);
          })
          .catch(err => {
            console.log("This is Error in Usage : " + err);
          });
          fetch("http://192.168.43.6:8123/api/states/sensor.ampere", {
            method: "GET",
            headers: new Headers({
               'Authorization': 'Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiIwMTI0NjA5ODc2MTI0YTQ1YTk4MDFlODE4ZGQ5YmY2MSIsImlhdCI6MTYxMzc0NTc3MCwiZXhwIjoxOTI5MTA1NzcwfQ.RHzgHe6BpmtihYkcrhwX-fTUGYKorPWB1YuPa3Dj_g8',
               'Accept': 'application/json',
              'Content-Type': 'application/json'
            }),
          })
            .then(response => response.json())
            .then(response => {
              setAmpere(response);
              console.log("This is Response " + response);
            })
            .catch(err => {
              console.log("This is Error in Usage : " + err);
            });

            fetch("http://192.168.43.6:8123/api/states/sensor.power", {
            method: "GET",
            headers: new Headers({
               'Authorization': 'Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiIwMTI0NjA5ODc2MTI0YTQ1YTk4MDFlODE4ZGQ5YmY2MSIsImlhdCI6MTYxMzc0NTc3MCwiZXhwIjoxOTI5MTA1NzcwfQ.RHzgHe6BpmtihYkcrhwX-fTUGYKorPWB1YuPa3Dj_g8',
               'Accept': 'application/json',
              'Content-Type': 'application/json'
            }),
          })
            .then(response => response.json())
            .then(response => {
              setPower(response); 
              //console.log("Power : " + JSON.stringify(response.state))
              var pw = JSON.stringify(response.state);
              pw = pw.substring(1, pw.length - 1)
              var t = parseFloat(pw);
              console.log(t);
              
              if(t > 500 && count  == 0){
                console.log("Inside If True Condition");
                fetch('https://exp.host/--/api/v2/push/send', {
                method: 'POST',
                headers: {
                  Accept: 'application/json',
                  'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                  "to": "ExponentPushToken[8qtK5PBKmP-6oaOunl9Kg-]",
                  "title":"hello",
                  "body": "world"
                })
              });
              }
            })
            .catch(err => {
              console.log("This is Error in Usage : " + err);
            });
        
      }
        // fetch(getEndpoint('api/alerts/all'))
        //   .then(result => result.json())
        //   .then(result => setAlerts(result))
        
        getAlerts()
      const interval = setInterval(() => getAlerts(), 900)
      return () => {
        clearInterval(interval);
      }
  }, [])

  

  return(
    <ScrollView>
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
<LineChart
  data={data1}
  width={screenWidth}
  height={256}
  verticalLabelRotation={30}
  chartConfig={chartConfig}
  bezier
/>
</View>

<View>
<LineChart
  data={data2}
  width={screenWidth}
  height={256}
  verticalLabelRotation={30}
  chartConfig={chartConfig}
  bezier
/>
</View>
</React.Fragment>
</ScrollView>




  // <Background>
  //   <Paragraph>Voltage : {alerts.state}</Paragraph>
  //   <Paragraph>Ampere : {ampere.state}</Paragraph>
  //   <Paragraph>Power : {power.state}</Paragraph>
    
  // </Background>
  )
}

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

export default ReportScreen
