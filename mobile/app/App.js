/**
 * Copyright (c) Garuda Labs, Inc.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 *
 */

import './src/gesture-handler';
import React from 'react';
import { LogBox } from 'react-native';
import Navigator from './src/Navigator';
import Toast, { SuccessToast, ErrorToast } from 'react-native-toast-message';

const toastConfig = {
    success: (props) => (
        <SuccessToast
        {...props}
        text1Style={{
            fontSize: 17,
        }}
        text2Style={{
            fontSize: 15
        }}
        />
    ),
    error: (props) => (
        <ErrorToast
        {...props}
        text1Style={{
            fontSize: 17
        }}
        text2Style={{
            fontSize: 15
        }}
        />
    ),
};

LogBox.ignoreAllLogs()

export default function App() {
    return (
        <>
        <Navigator />
        <Toast config={toastConfig} />
        </>
    )
}
