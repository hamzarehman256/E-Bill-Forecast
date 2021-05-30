import React from 'react'
import Background from '../components/Background'
import Logo from '../components/Logo'
import Header from '../components/Header'
import Paragraph from '../components/Paragraph'
import Button from '../components/Button'
import { logoutUser } from '../api/auth-api'

const CheckBill = () => (
  <Background>
    {/* <Logo />
    <Header>Let’s start</Header> */}
    <Paragraph>
      Check Bill
    </Paragraph>
    {/* <Button mode="outlined" onPress={logoutUser}>
      Logout
    </Button> */}
  </Background>
)

export default CheckBill
