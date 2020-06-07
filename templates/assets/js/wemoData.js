
var myCharts = {};


function createDevices(devices){
    for(var k in devices){
        console.log(devices[k]);

        var newData = $(".wemoData").first().clone();
        $(newData).prop('id', "Wemo-" + devices[k].name.replace(" ", "_"));
        $(newData).find('span[name ="WemoName"]').text(devices[k].name);
        $(newData).find('td[name ="WemoStatus"]').text(devices[k].status);
        $(newData).find('td[name ="WemoPower"]').text(devices[k].todaykww +" kWh");

        $(newData).find('canvas').prop("id", "WemoChart-" + devices[k].name.replace(" ", "_"));
        newData.appendTo(".wemoDataRow");
        var ctx = document.getElementById("WemoChart-" + devices[k].name.replace(" ", "_"));
        
        var historyLabel = [];
        for(i = 0; i < devices[k].history.dateValue.length; i++){
            var date = new Date(devices[k].history.dateValue[i]);
            historyLabel.push(i);
            // historyLabel.push(devices[k].history.dateValue[i]);
        }
        
        var myChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: historyLabel,
                datasets: [{
                    data: devices[k].history.data,
                    backgroundColor: [
                        'rgba(54,185,204,1)',
                    ],
                    borderColor: [
                        'rgba(255,0,0,1)',
                    ],
                    borderWidth: 1
                }]
            }, options: {
                legend: {
                    display: false
                }, 
                elements: {
                    point:{
                        radius: 0
                    }
                },
                scales: {
                    yAxes: [{
                      scaleLabel: {
                        display: true,
                        labelString: 'Watts'
                      }
                    }],
                    xAxes: [{
                      scaleLabel: {
                        display: true,
                        labelString: 'Time'
                      }
                    }]
                }
            }
        });
        myCharts["WemoChart-" + devices[k].name.replace(" ", "_")] = myChart;
        myChart.update();
    }
    $(".wemoData").first().remove()
}

function updateDevices(devices){
    for(var k in devices){
        
        $(document).find('canvas').prop("id", "WemoChart-" + k.replace(" ", "_"));

        var ctx = myCharts["WemoChart-" + k.replace(" ", "_")];

        ctx.data.labels.push(devices[k].dateValue)
        ctx.data.datasets[0].data.push(devices[k].data)

        ctx.update();
    }

}

function init(){
	var deviceInfo;
    var devices;
    var i = 1;
    

//     devices = [{"currentPower":1835,"history":[1,2,3,4,121],"name":"Kitchen","ontoday":4360,"status":"Standby","todaykww":0.15},{"currentPower":894805,"history":[1,2,3,4,5],"name":"Living Room","ontoday":8920,"status":"On","todaykww":1.13},{"currentPower":42525,"history":[1,2,3,4,5],"name":"Entertainment Center","ontoday":30338,"status":"On","todaykww":0.88},{"currentPower":3085,"history":[1,2,3,4,5],"name":"Bedroom","ontoday":397,"status":"Standby","todaykww":0.02},{"currentPower":187265,"history":[1,2,3,4,5],"name":"Desktop Computer","ontoday":36732,"status":"On","todaykww":1.82}];

//     updateDevices(devices);
    
    $.getJSON('/_deviceInfo',
        function(data){
                    deviceInfo = data.result;

                    devices = deviceInfo.devices
                    createDevices(devices);
    });
}


function getDevices(){

}

var intervalID = setInterval(update_values, 1000);

var temp;
var c;

var jsonData;

// var ctx = document.getElementById("myChart");
// var myChart = new Chart(ctx, {
//     type: 'line',
//     data: {
//         labels: [c],
//         datasets: [{
//             label: 'KW Power Usage',
//             data: [temp],
//             backgroundColor: [
//                 'rgba(102,255,153,1)',
//             ],
//             borderColor: [
//                 'rgba(255,0,0,1)',
//             ],
//             borderWidth: 1
//         }]
//     },
//     options: {
//         scales: {
//             yAxes: [{
//                 tickets: {
//                     beginAtZero: true
//                 }
//             }]
//         }
//     }
// })

function initChart(){
    myChart.data.labels = temp.datetime;
    myChart.data.datasets.forEach((dataset) => {
        dataset.data = temp.data;
    });
    myChart.update();
    updateChart();
}

function getHistory(){

    var initData;

    $.getJSON('/_dataHistory',
        function(data){
                    console.log(data.result)
                    temp = data.result;
                    console.log(temp.data);
                    console.log(temp.datetime);
                    initChart();
        });

}

function updateChart(){
    myChart.data.labels.push(temp.datetime);
    myChart.data.datasets.forEach((dataset) => {
        dataset.data.push(temp.data);
    });
    myChart.update();
}

function update_values(){
    $.getJSON('/_data',
        function(data){
        temp = data.result;
        updateDevices(temp.deviceData);
        });
};
