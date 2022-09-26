import { Stopwatch } from 'react-native-stopwatch-timer'
import React from "react";
import { TouchableHighlight, View, Text } from "react-native"

let currentTime = '00:00:00';
function getTime() {
    return timeStringToFloat(currentTime);
}

function timeStringToFloat(time) {
    let hoursMinutes = time.split(/[.:]/);
    let hours = parseInt(hoursMinutes[0], 10);
    let minutes = hoursMinutes[1] ? parseInt(hoursMinutes[1], 10) : 0;
    return (hours + minutes / 60).toFixed(2)
}

const PrimaryButton = ({title, clickHandler}) => {
    return (
        <TouchableHighlight onPress={clickHandler} style={{backgroundColor: '#1b1d23', padding: 10, borderRadius: 10}}>
        <Text style={{fontSize: 20, color: 'white'}}>{title}</Text>
        </TouchableHighlight>
    )
}

export default class TimaryStopwatch extends React.Component {
    static namespaceURI = 'https://www.usetimary.com/hyperview/';
    static localName = 'stopwatch';
    static getFormInputValues = (element): Array<[string, string]> => {
        return [["hours", getTime()]]
    };

    constructor(props) {
        super(props);
        this.state = {
            stopwatchRunning: false,
            stopwatchReset: false,
            startBtnShow: true,
            resumeBtnShow: false,
            pauseBtnShow: false,
            stopBtnShow: false,
            resetBtnShow: false,
        };
        this.start = this.start.bind(this);
        this.resume = this.resume.bind(this);
        this.pause = this.pause.bind(this);
        this.stop = this.stop.bind(this);
        this.reset = this.reset.bind(this);
    }

    start() {
        currentTime = 0;
        this.setState({stopwatchRunning: true, stopwatchReset: false, startBtnShow: false, pauseBtnShow: true, stopBtnShow: true, resetBtnShow: true})
    }
    resume() {
        this.setState({stopwatchRunning: true, resumeBtnShow: false, pauseBtnShow: true, stopBtnShow: true, resetBtnShow: true})
    }
    pause() {
        this.setState({stopwatchRunning: false, resumeBtnShow: true, pauseBtnShow: false, stopBtnShow: true, resetBtnShow: true})
    }
    stop() {
        this.setState({stopwatchRunning: false, resumeBtnShow: true, pauseBtnShow: false, stopBtnShow: false, resetBtnShow: true})
    }
    reset() {
        currentTime = 0;
        this.setState({stopwatchRunning: false, stopwatchReset: true, startBtnShow: true, resumeBtnShow: false, pauseBtnShow: false, stopBtnShow: false, resetBtnShow: false})
    }

    getFormattedTime(time) {
        currentTime = time;
    };

    render() {
        return (
            <View style={{width: '100%', marginTop: 30}}>
            <Stopwatch
            start={this.state.stopwatchRunning}
            reset={this.state.stopwatchReset}
            options={options}
            getTime={this.getFormattedTime}
            />
            <View style={{display: 'flex', flexDirection:"row", justifyContent: 'space-evenly', marginVertical: 30}}>
            {this.state.startBtnShow && <PrimaryButton title="Start" clickHandler={this.start} />}
            {this.state.resumeBtnShow && <PrimaryButton title="Resume" clickHandler={this.resume} />}
            {this.state.pauseBtnShow && <PrimaryButton title="Pause" clickHandler={this.pause} />}
            {this.state.stopBtnShow && <PrimaryButton title="Stop" clickHandler={this.stop} />}
            {this.state.resetBtnShow && <PrimaryButton title="Reset" clickHandler={this.reset} />}
            </View>

            </View>
        );
    }
}

const options = {
    container: {
        display: 'flex',
        flexDirection: 'row',
        justifyContent: 'center',
    },
    text: {
        fontSize: 60,
        color: '#FFF',
        textAlign: 'center',
    }
};
