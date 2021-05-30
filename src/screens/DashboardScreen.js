import React, { useState } from 'react'
import Background from '../components/Background'
import Logo from '../components/Logo'
import Header from '../components/Header'
import Paragraph from '../components/Paragraph'
import Button from '../components/Button'
import { logoutUser } from '../api/auth-api'
import { Text, View, Switch, StyleSheet } from 'react-native';

export default function DashboardScreen ( {navigation} ) {

  return (
  <Background>
    <View style={styles.container}>
      <View style={styles.buttonContainer}>
    <Button mode="outlined" onPress={() => navigation.navigate('Home Control')}>Home Control</Button>
    </View>
    <View style={styles.buttonContainer}>
    <Button mode="outlined" onPress={() => navigation.navigate('Usage')}>Usage</Button>
    </View>
    </View>
    <View style={styles.containerr}>
    <View style={styles.buttonContainer}>
    <Button mode="outlined" onPress={() => navigation.navigate('Reports')}>Reports</Button>
    </View>
    <View style={styles.buttonContainer}>
    <Button mode="outlined" onPress={() => navigation.navigate('Bill Forecast')}>Bill Forecast</Button>
    </View>
    </View>
  </Background>
);
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    paddingTop: 80,
    width: '100%',
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'center',
  },
  containerr: {
    flex: 6,
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'center',
  },
  buttonContainer: {
    flex: 1,
}
})


