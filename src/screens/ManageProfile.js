import React from 'react'
import Background from '../components/Background'
import Logo from '../components/Logo'
import Header from '../components/Header'
import Paragraph from '../components/Paragraph'
import Button from '../components/Button'
import { logoutUser } from '../api/auth-api'

const ManageProfile = ( {navigation} ) => (
  <Background>
    {/* <Logo />
    <Header>Let’s start</Header> */}
    <Paragraph>
      Manage Profile
    </Paragraph>
    {/* <Button mode="outlined" onPress={() => navigation.navigate('Check Bill')}>
      Check BIll
    </Button> */}
  </Background>
)

export default ManageProfile
