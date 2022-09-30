/**
 * Copyright (c) Garuda Labs, Inc.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 *
 */

import React, {PureComponent} from 'react';
import HandleBack from './HandleBack';
import Hyperview from 'hyperview';
import moment from 'moment';
import {MAIN_STACK_NAME, MODAL_STACK_NAME} from './constants';
import Toast from "react-native-toast-message";
import {Linking} from "react-native";
import TimaryStopwatch from "./TimaryStopwatch";
import * as SecureStore from 'expo-secure-store';
import * as Haptics from "expo-haptics";


const storeData = async (value) => {
    try {
        await SecureStore.setItemAsync("token", value)
    } catch (e) {
        // saving error
    }
}

const removeData = async (key) => {
    try {
        await SecureStore.deleteItemAsync(key)
    } catch(e) {
        // remove error
    }
}

const NAMESPACE_URI = 'https://usetimary.com/hyperview/';

const loginBehavior =  {
    action: 'login',
    callback: (element) => {
        const token = element.getAttributeNS(NAMESPACE_URI, 'token');
        if (token) {
            Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
            storeData(token)
        }
    },
};

const linkBehavior =  {
    action: 'link',
    callback: (element) => {
        const url = element.getAttributeNS(NAMESPACE_URI, 'url');
        if (url) {
            Linking.openURL(url);
        }
    },
};

const logoutBehavior =  {
    action: 'logout',
    callback: (element) => {
        Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning);
        removeData("token")
    }
};

const toastBehavior =  {
    action: 'toast',
    callback: (element) => {
        const type = element.getAttributeNS(NAMESPACE_URI, 'type');
        const message = element.getAttributeNS(NAMESPACE_URI, 'message');
        if (type && message) {
            Toast.show({
                type: type,
                text1: message,
                visibilityTime: 2000,
                onShow: () => {
                    let hapticFeedback = Haptics.NotificationFeedbackType.Warning;
                    if (type === "success") {
                        hapticFeedback = Haptics.NotificationFeedbackType.Success;
                    } else if (type === "error") {
                        hapticFeedback = Haptics.NotificationFeedbackType.Error;
                    }
                    Haptics.notificationAsync(hapticFeedback);
                }
            });
        }
    },
};

export default class HyperviewScreen extends PureComponent {
    constructor(props) {
        super(props);
        let authToken = this.props.route.params?.token;
        if (authToken) {
            this.state = {
                token: authToken
            }
        }
    }

    goBack = () => {
        this.props.navigation.pop();
    }

    closeModal = () => {
        this.props.navigation.pop();
    }

    push = (params) => {
        // If we're in a modal stack, push the next screen on the modal stack.
        // If we're in the main stack, push the next screen in the main stack.
        // Modal stacks will have modal param set.
        const modal = this.props.route.params?.modal ?? false;
        let main_route_name = this.state?.token ? `AUTH_${MAIN_STACK_NAME}` : MAIN_STACK_NAME
        this.props.navigation.push(
            modal ? MODAL_STACK_NAME : main_route_name,
            {
                modal,
                    ...params,
            }
        );
    }

    navigate = (params, key) => {
        let route_name = this.state?.token ? `AUTH_${MAIN_STACK_NAME}` : MAIN_STACK_NAME
        this.props.navigation.navigate({ key, params, routeName: route_name });
    }

    openModal = (params) => {
        this.props.navigation.push(MODAL_STACK_NAME, params);
    }

    formatDate = (date, format) => moment(date).format(format);

    /**
   * fetch function used by Hyperview screens. By default, it adds
   * header to prevent caching requests.
   */
    fetchWrapper = async (input, init = {headers: {}}) => {
        let token_headers = {}
        if (this.state?.token) {
            token_headers["Authorization"] = `Token ${this.state?.token}`
        } else {
            let auth_token = await this.getAuthToken()
            if (auth_token) {
                token_headers["Authorization"] = `Token ${auth_token}`
                this.setState({token: auth_token})
            }
        }
        return fetch(input, {
                ...init,
            mode: "cors",
            headers: {
                // Don't cache requests for the demo
                'Cache-Control': 'no-cache, no-store, must-revalidate',
                Expires: 0,
                Pragma: 'no-cache',
                    ...init.headers,
                    ...token_headers
            }
        });
    }

    getAuthToken = async () => {
        try {
            const value = await SecureStore.getItemAsync("token")

            if (value !== null) {
                return value
            }
        } catch(e) {
            // error reading value
            console.log("error reading value")
        }
    }

    render() {
        let entrypointUrl = this.props.route.params?.url;
        return (
            <HandleBack>
            <Hyperview
            back={this.goBack}
            behaviors={[loginBehavior, linkBehavior, logoutBehavior, toastBehavior]}
            components={[TimaryStopwatch]}
            closeModal={this.closeModal}
            entrypointUrl={entrypointUrl}
            fetch={this.fetchWrapper}
            formatDate={this.formatDate}
            navigate={this.navigate}
            navigation={this.props.navigation}
            openModal={this.openModal}
            push={this.push}
            route={this.props.route}
            />
            </HandleBack>);
    }
}
