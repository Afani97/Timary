/**
 * Copyright (c) Garuda Labs, Inc.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 *
 */

import HyperviewScreen from './HyperviewScreen';
import {NavigationContainer} from '@react-navigation/native';
import React from 'react';
import { createStackNavigator } from '@react-navigation/stack';
import {ENTRY_POINT_URL, HOME_URL, MAIN_STACK_NAME, MODAL_STACK_NAME} from './constants';
import * as SecureStore from 'expo-secure-store';



const Stack = createStackNavigator();

export default () => {
    const [authToken, setAuthToken] = React.useState(null)
    React.useEffect( () => {
        setTimeout(async () => {
            try {
                const value = await SecureStore.getItemAsync("token")
                if (value !== null) {
                    setAuthToken(value)
                }
            } catch(e) {
                // error reading value
                console.log("error reading value")
            }
        }, 1000)
    }, [])



    return (
        <NavigationContainer>
        <Stack.Navigator screenOptions={{ headerShown: false }}>
        {authToken !== null ? (

            <Stack.Group>
            <Stack.Screen
            component={HyperviewScreen}
            initialParams={{url: HOME_URL, token: authToken}}
            name={`AUTH_${MAIN_STACK_NAME}`}
            />
            </Stack.Group>

        ) : (
            <Stack.Group>
            <Stack.Screen
            component={HyperviewScreen}
            initialParams={{url: ENTRY_POINT_URL}}
            name={MAIN_STACK_NAME}
            />
            </Stack.Group>

        )
        }
        <Stack.Group screenOptions={{presentation: 'modal'}}>
        <Stack.Screen
        component={HyperviewScreen}
        name={MODAL_STACK_NAME}
        />
        </Stack.Group>
        </Stack.Navigator>
        </NavigationContainer>


    )
}
