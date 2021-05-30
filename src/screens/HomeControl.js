import React, {useState} from 'react'
import Background from '../components/Background'
import Logo from '../components/Logo'
import Header from '../components/Header'
import Paragraph from '../components/Paragraph'
//import Button from '../components/Button'
import { Text, View, Switch, StyleSheet, Button } from 'react-native';
import { logoutUser } from '../api/auth-api'

export default function HomeControl ( {navigation} ) {

    const [isEnabled, setIsEnabled] = useState(false);
    const toggleSwitch = () => {
  
  
      if(isEnabled){
        fetch("http://192.168.43.6:8123/api/services/switch/turn_off", {
          method: "POST",
          headers: new Headers({
             'Authorization': 'Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiIwMTI0NjA5ODc2MTI0YTQ1YTk4MDFlODE4ZGQ5YmY2MSIsImlhdCI6MTYxMzc0NTc3MCwiZXhwIjoxOTI5MTA1NzcwfQ.RHzgHe6BpmtihYkcrhwX-fTUGYKorPWB1YuPa3Dj_g8',
             'Accept': 'application/json',
            'Content-Type': 'application/json'
          }),
          body: JSON.stringify({
            "entity_id": "switch.light"
          })
        })
          .then(response => response.json())
          .then(response => {
            console.log("This is Response " + response);
          })
          .catch(err => {
            console.log("This is Error" + err);
          });
      }
      else{
        fetch("http://192.168.43.6:8123/api/services/switch/turn_on", {
          method: "POST",
          headers: new Headers({
             'Authorization': 'Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiIwMTI0NjA5ODc2MTI0YTQ1YTk4MDFlODE4ZGQ5YmY2MSIsImlhdCI6MTYxMzc0NTc3MCwiZXhwIjoxOTI5MTA1NzcwfQ.RHzgHe6BpmtihYkcrhwX-fTUGYKorPWB1YuPa3Dj_g8',
             'Accept': 'application/json',
            'Content-Type': 'application/json'
          }),
          body: JSON.stringify({
            "entity_id": "switch.light"
          })
        })
          .then(response => response.json())
          .then(response => {
            console.log("This is Response " + response);
          })
          .catch(err => {
            console.log("This is Error" + err);
          });
      }
  
        
  
      setIsEnabled(previousState => !previousState);
    }
    return (
      
    <Background>
      
      {/* <Logo />
      <Header>Let’s start</Header> */}
      <Text>{isEnabled ? 'Switch is ON' : 'Switch is OFF'}</Text>
      <Switch
          trackColor={{ false: '#767577', true: '#81b0ff' }}
          thumbColor={isEnabled ? '#f5dd4b' : '#f4f3f4'}
          ios_backgroundColor="#3e3e3e"
          onValueChange={toggleSwitch}
          value={isEnabled}
        />
      {/* <Button mode="outlined" onPress={() => navigation.navigate('Manage Profile')}>
        Second Screen
      </Button> */}
    </Background>
  );
  }
