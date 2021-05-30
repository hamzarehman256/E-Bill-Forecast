import 'react-native-gesture-handler';

import * as React from 'react';
import { Button, View, Text, TouchableOpacity, Image } from 'react-native';

import { NavigationContainer } from '@react-navigation/native';
import { createStackNavigator } from '@react-navigation/stack';
import { createDrawerNavigator } from '@react-navigation/drawer';
import {
  DrawerContentScrollView,
  DrawerItemList,
  DrawerItem,
} from '@react-navigation/drawer';
import DashboardScreen from './DashboardScreen';
import ManageProfile from './ManageProfile';
import CheckBill from './CheckBill';
import { logoutUser } from '../api/auth-api';
import HomeControl from './HomeControl';
import UsageScreen from './UsageScreen';
import ReportScreen from './ReportScreen';
import BillForecast from './BillForecast';
import forecast from './forecast';

const Stack = createStackNavigator();
const Drawer = createDrawerNavigator();

const NavigationDrawerStructure = (props)=> {
  const toggleDrawer = () => {
    props.navigationProps.toggleDrawer();
  };

  return (
    <View style={{ flexDirection: 'row' }}>
      <TouchableOpacity onPress={()=> toggleDrawer()}>
        <Image
          source={{uri: 'https://raw.githubusercontent.com/AboutReact/sampleresource/master/drawerWhite.png'}}
          style={{ width: 35, height: 35, marginLeft: 10 }}
        />
      </TouchableOpacity>
    </View>
  );
}

function firstScreenStack({ navigation }) {
  return (
      <Stack.Navigator initialRouteName="Dashboard">
        <Stack.Screen
          name="Dashboard"
          component={DashboardScreen}
          options={{
            title: 'Dashboard',
            headerLeft: ()=> <NavigationDrawerStructure navigationProps={navigation} />,
            headerStyle: {
              backgroundColor: '#f4511e', //Set Header color
            },
            headerTintColor: '#fff', //Set Header text color
            headerTitleStyle: {
              fontWeight: 'bold', //Set Header text style
            },
          }}
        />

      <Stack.Screen
        name="Home Control"
        component={HomeControl}
        options={{
          title: 'Home Control', //Set Header Title
        }}/>
        <Stack.Screen
        name="Usage"
        component={UsageScreen}
        options={{
          title: 'Usage Screen', //Set Header Title
        }}/>
        <Stack.Screen
        name="Reports"
        component={ReportScreen}
        options={{
          title: 'Reports Screen', //Set Header Title
        }}/>
        <Stack.Screen
        name="Bill Forecast"
        component={BillForecast}
        options={{
          title: 'Bill Forecast', //Set Header Title
        }}/>
        <Stack.Screen
        name="forecast"
        component={forecast}
        options={{
          title: 'forecast', //Set Header Title
        }}/>
      </Stack.Navigator>
  );
}

function secondScreenStack({ navigation }) {
  return (
    <Stack.Navigator
      initialRouteName="Manage Profile"
      screenOptions={{
        headerLeft: ()=> <NavigationDrawerStructure navigationProps={navigation} />,
        headerStyle: {
          backgroundColor: '#f4511e', //Set Header color
        },
        headerTintColor: '#fff', //Set Header text color
        headerTitleStyle: {
          fontWeight: 'bold', //Set Header text style
        }
      }}>
      <Stack.Screen
        name="Manage Profile"
        component={ManageProfile}
        options={{
          title: 'Profile', //Set Header Title
          
        }}/>
         {/* <Stack.Screen
        name="Home Control"
        component={HomeControl}
        options={{
          title: 'Home Control', //Set Header Title
        }}/> */}
      {/* <Stack.Screen
        name="Home Control"
        component={HomeControl}
        options={{
          title: 'Home Control', //Set Header Title
        }}/> */}
    </Stack.Navigator>
  );
}


function thirdScreenStack({ navigation }) {
  return (
    <Stack.Navigator
      initialRouteName="Check Bill"
      screenOptions={{
        headerLeft: ()=> <NavigationDrawerStructure navigationProps={navigation} />,
        headerStyle: {
          backgroundColor: '#f4511e', //Set Header color
        },
        headerTintColor: '#fff', //Set Header text color
        headerTitleStyle: {
          fontWeight: 'bold', //Set Header text style
        }
      }}>
      <Stack.Screen
        name="Check Bill"
        component={CheckBill}
        options={{
          title: 'Check Bill', //Set Header Title
          
        }}/>
        {/* <Stack.Screen
        name="Home Control"
        component={HomeControl}
        options={{
          title: 'Home Control', //Set Header Title
        }}/> */}
        {/* <Stack.Screen
        name="Manage Profile"
        component={ManageProfile}
        options={{
          title: 'Profile', //Set Header Title
        }}/> */}
    </Stack.Navigator>
  );
}

function CustomDrawerContent(props) {
  return (
    <DrawerContentScrollView {...props}>
      <DrawerItemList {...props} />
      <DrawerItem label="Logout" onPress={logoutUser} />
    </DrawerContentScrollView>
  );
}

const Dashboard = () => { 
  return (
    <NavigationContainer independent={true}>
      <Drawer.Navigator
        drawerContent={props => <CustomDrawerContent {...props} />}
        drawerContentOptions={{
          activeTintColor: '#e91e63',
          itemStyle: { marginVertical: 5 },
        }}>
        <Drawer.Screen
          name="Dashboard"
          options={{ drawerLabel: 'Dashboard' }}
          component={firstScreenStack} />
        <Drawer.Screen
          name="Manage Profile"
          options={{ drawerLabel: 'Manage Profile' }}
          component={secondScreenStack} />
          <Drawer.Screen
          name="Check Bill"
          options={{ drawerLabel: 'Check Bill' }}
          component={thirdScreenStack} />
          {/* <Stack.Screen
        name="Home Control"
        component={HomeControl}
        options={{
          title: 'Home Control', //Set Header Title
        }}/> */}
      </Drawer.Navigator>
    </NavigationContainer>
  );
}

export default Dashboard;